#!/usr/bin/env python3
"""
Unit tests for Apollo.io live adapter.

Tests contact enrichment, email verification, and company search without real credentials.
"""

import pytest
from unittest.mock import Mock, patch
import httpx

from cuga.adapters.sales.apollo_live import ApolloLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "api_key": "test_apollo_api_key_456",
        },
        metadata={"trace_id": "test-trace-apollo"},
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create Apollo.io adapter with mocked HTTP client."""
    with patch('cuga.adapters.sales.apollo_live.SafeClient'):
        adapter = ApolloLiveAdapter(mock_config)
        adapter.client = Mock()
        return adapter


class TestApolloAdapter:
    """Test Apollo.io adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        with patch('cuga.adapters.sales.apollo_live.SafeClient'):
            adapter = ApolloLiveAdapter(mock_config)
            
            assert adapter.config == mock_config
            assert adapter.trace_id == "test-trace-apollo"
            assert adapter.api_key == "test_apollo_api_key_456"
    
    def test_validate_config_missing_api_key(self):
        """Test config validation catches missing API key."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={},
            metadata={"trace_id": "test"},
        )
        
        with pytest.raises(ValueError, match="api_key"):
            ApolloLiveAdapter(invalid_config)
    
    def test_get_mode(self, mock_adapter):
        """Test adapter mode is LIVE."""
        assert mock_adapter.get_mode() == AdapterMode.LIVE
    
    def test_validate_connection_success(self, mock_adapter):
        """Test connection validation with successful response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_adapter.client.get.return_value = mock_response
        
        result = mock_adapter.validate_connection()
        
        assert result is True
    
    def test_validate_connection_failure(self, mock_adapter):
        """Test connection validation with failed response."""
        mock_adapter.client.get.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=Mock(status_code=401)
        )
        
        result = mock_adapter.validate_connection()
        
        assert result is False
    
    def test_fetch_accounts_success(self, mock_adapter):
        """Test fetching companies with successful API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organizations": [
                {
                    "id": "org_789",
                    "name": "Example Corp",
                    "website_url": "example.com",
                    "industry": "Software",
                    "estimated_num_employees": 1000,
                    "annual_revenue": 100000000,
                }
            ]
        }
        mock_adapter.client.post.return_value = mock_response
        
        accounts = mock_adapter.fetch_accounts({"limit": 10})
        
        assert len(accounts) == 1
        assert accounts[0]["id"] == "org_789"
        assert accounts[0]["name"] == "Example Corp"
        assert accounts[0]["domain"] == "example.com"
        assert accounts[0]["employee_count"] == 1000
    
    def test_fetch_accounts_with_filters(self, mock_adapter):
        """Test fetch accounts applies filters correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"organizations": []}
        mock_adapter.client.post.return_value = mock_response
        
        filters = {
            "industry": "Technology",
            "revenue_min": 1000000,
            "revenue_max": 50000000,
            "employees_min": 100,
            "employees_max": 500,
            "limit": 20
        }
        
        mock_adapter.fetch_accounts(filters)
        
        call_args = mock_adapter.client.post.call_args
        json_data = call_args[1]["json"]
        
        assert "q_organization_industry" in str(json_data)
        assert json_data["per_page"] == 20
    
    def test_fetch_contacts_success(self, mock_adapter):
        """Test fetching contacts for an account."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "people": [
                {
                    "id": "person_123",
                    "first_name": "John",
                    "last_name": "Doe",
                    "email": "john.doe@example.com",
                    "title": "VP of Engineering",
                }
            ]
        }
        mock_adapter.client.post.return_value = mock_response
        
        contacts = mock_adapter.fetch_contacts("org_789")
        
        assert len(contacts) == 1
        assert contacts[0]["id"] == "person_123"
        assert contacts[0]["first_name"] == "John"
        assert contacts[0]["email"] == "john.doe@example.com"
    
    def test_enrich_contact_success(self, mock_adapter):
        """Test enriching a contact by email."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "person": {
                "id": "person_456",
                "first_name": "Jane",
                "last_name": "Smith",
                "email": "jane.smith@example.com",
                "linkedin_url": "https://linkedin.com/in/janesmith",
                "organization": {
                    "name": "Example Corp"
                }
            }
        }
        mock_adapter.client.post.return_value = mock_response
        
        contact = mock_adapter.enrich_contact("jane.smith@example.com")
        
        assert contact is not None
        assert contact["id"] == "person_456"
        assert contact["email"] == "jane.smith@example.com"
        assert contact["metadata"]["linkedin_url"] == "https://linkedin.com/in/janesmith"
    
    def test_enrich_contact_not_found(self, mock_adapter):
        """Test enriching contact when not found."""
        mock_adapter.client.post.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock(status_code=404)
        )
        
        contact = mock_adapter.enrich_contact("notfound@example.com")
        
        assert contact is None
    
    def test_verify_email_valid(self, mock_adapter):
        """Test email verification with valid email."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "valid@example.com",
            "is_valid": True,
            "is_deliverable": True,
            "verification_status": "verified"
        }
        mock_adapter.client.post.return_value = mock_response
        
        result = mock_adapter.verify_email("valid@example.com")
        
        assert result["is_valid"] is True
        assert result["is_deliverable"] is True
        assert result["verification_status"] == "verified"
    
    def test_verify_email_invalid(self, mock_adapter):
        """Test email verification with invalid email."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "email": "invalid@example.com",
            "is_valid": False,
            "is_deliverable": False,
            "verification_status": "invalid"
        }
        mock_adapter.client.post.return_value = mock_response
        
        result = mock_adapter.verify_email("invalid@example.com")
        
        assert result["is_valid"] is False
        assert result["is_deliverable"] is False
    
    def test_fetch_buying_signals(self, mock_adapter):
        """Test deriving buying signals from engagement."""
        # Mock verify_email to return verified status
        with patch.object(mock_adapter, 'verify_email') as mock_verify:
            mock_verify.return_value = {
                "is_valid": True,
                "is_deliverable": True,
                "verification_status": "verified"
            }
            
            signals = mock_adapter.fetch_buying_signals("org_789")
            
            assert len(signals) > 0
            assert signals[0]["type"] in ["email_verified", "engagement_detected"]
    
    def test_normalize_company(self, mock_adapter):
        """Test company normalization to canonical format."""
        raw_company = {
            "id": "org_999",
            "name": "Test Inc",
            "website_url": "test.com",
            "industry": "Finance",
            "estimated_num_employees": 750,
            "annual_revenue": 75000000,
            "city": "New York",
            "state": "NY",
            "country": "US"
        }
        
        normalized = mock_adapter._normalize_company(raw_company)
        
        assert normalized["id"] == "org_999"
        assert normalized["name"] == "Test Inc"
        assert normalized["domain"] == "test.com"
        assert normalized["industry"] == "Finance"
        assert normalized["employee_count"] == 750
        assert normalized["revenue"] == 75000000
        assert normalized["location"]["city"] == "New York"
        assert normalized["location"]["state"] == "NY"
        assert normalized["metadata"]["source"] == "apollo"
    
    def test_normalize_contact(self, mock_adapter):
        """Test contact normalization to canonical format."""
        raw_contact = {
            "id": "person_888",
            "first_name": "Bob",
            "last_name": "Johnson",
            "email": "bob.johnson@test.com",
            "title": "CTO",
            "seniority": "executive",
            "departments": ["Engineering", "IT"]
        }
        
        normalized = mock_adapter._normalize_contact(raw_contact)
        
        assert normalized["id"] == "person_888"
        assert normalized["first_name"] == "Bob"
        assert normalized["last_name"] == "Johnson"
        assert normalized["email"] == "bob.johnson@test.com"
        assert normalized["title"] == "CTO"
        assert normalized["metadata"]["seniority"] == "executive"
        assert normalized["metadata"]["source"] == "apollo"
