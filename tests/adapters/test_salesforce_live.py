#!/usr/bin/env python3
"""
Unit tests for Salesforce live adapter.

Tests schema normalization and query building without requiring real credentials.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from cuga.adapters.sales.salesforce_live import SalesforceLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "instance_url": "https://test.my.salesforce.com",
            "client_id": "test_client_id",
            "client_secret": "test_client_secret",
            "username": "test@example.com",
            "password": "test_password",
            "security_token": "test_token",
        },
        trace_id="test-trace-001",
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create Salesforce adapter with mocked authentication."""
    with patch.object(SalesforceLiveAdapter, '_authenticate'):
        adapter = SalesforceLiveAdapter(mock_config)
        adapter._access_token = "mock_access_token"
        adapter._token_expires_at = datetime(2030, 1, 1)  # Far future
        return adapter


class TestSalesforceAdapter:
    """Test Salesforce adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        with patch.object(SalesforceLiveAdapter, '_authenticate'):
            adapter = SalesforceLiveAdapter(mock_config)
            
            assert adapter.config == mock_config
            assert adapter.trace_id == "test-trace-001"
            assert adapter._instance_url == "https://test.my.salesforce.com"
    
    def test_validate_config_missing_fields(self):
        """Test config validation catches missing credentials."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={
                "instance_url": "https://test.salesforce.com",
                # Missing required fields
            },
            trace_id="test",
        )
        
        with pytest.raises(ValueError, match="missing required credentials"):
            SalesforceLiveAdapter(invalid_config)
    
    def test_build_accounts_query_basic(self, mock_adapter):
        """Test SOQL query builder with no filters."""
        query = mock_adapter._build_accounts_query({})
        
        assert "SELECT" in query
        assert "FROM Account" in query
        assert "LIMIT 100" in query  # Default limit
        assert "WHERE" not in query
    
    def test_build_accounts_query_with_filters(self, mock_adapter):
        """Test SOQL query builder with filters."""
        filters = {
            "industry": "Technology",
            "min_revenue": 1000000,
            "state": "CA",
            "country": "USA",
            "limit": 50,
        }
        
        query = mock_adapter._build_accounts_query(filters)
        
        assert "WHERE" in query
        assert "Industry = 'Technology'" in query
        assert "AnnualRevenue >= 1000000" in query
        assert "BillingState = 'CA'" in query
        assert "BillingCountry = 'USA'" in query
        assert "LIMIT 50" in query
    
    def test_normalize_accounts(self, mock_adapter):
        """Test account schema normalization."""
        raw_records = [
            {
                "Id": "0011234567890ABC",
                "Name": "Acme Corp",
                "Industry": "Technology",
                "AnnualRevenue": 5000000,
                "NumberOfEmployees": 150,
                "BillingStreet": "123 Main St",
                "BillingCity": "San Francisco",
                "BillingState": "CA",
                "BillingCountry": "USA",
                "BillingPostalCode": "94105",
                "Phone": "+1-555-0100",
                "Website": "https://acme.com",
                "Description": "Software company",
                "CreatedDate": "2023-01-15T10:30:00Z",
                "LastModifiedDate": "2024-01-01T14:20:00Z",
            }
        ]
        
        normalized = mock_adapter._normalize_accounts(raw_records)
        
        assert len(normalized) == 1
        account = normalized[0]
        
        # Check field mapping
        assert account["id"] == "0011234567890ABC"
        assert account["name"] == "Acme Corp"
        assert account["industry"] == "Technology"
        assert account["revenue"] == 5000000
        assert account["employee_count"] == 150
        assert account["phone"] == "+1-555-0100"
        assert account["website"] == "https://acme.com"
        assert account["source"] == "salesforce"
        
        # Check nested address
        assert account["address"]["city"] == "San Francisco"
        assert account["address"]["state"] == "CA"
        assert account["address"]["country"] == "USA"
    
    def test_normalize_contacts(self, mock_adapter):
        """Test contact schema normalization."""
        raw_records = [
            {
                "Id": "0031234567890ABC",
                "FirstName": "John",
                "LastName": "Doe",
                "Email": "john.doe@acme.com",
                "Phone": "+1-555-0101",
                "Title": "VP of Sales",
                "Department": "Sales",
                "MailingCity": "San Francisco",
                "MailingState": "CA",
                "CreatedDate": "2023-06-01T09:00:00Z",
            }
        ]
        
        normalized = mock_adapter._normalize_contacts(raw_records)
        
        assert len(normalized) == 1
        contact = normalized[0]
        
        assert contact["id"] == "0031234567890ABC"
        assert contact["first_name"] == "John"
        assert contact["last_name"] == "Doe"
        assert contact["email"] == "john.doe@acme.com"
        assert contact["title"] == "VP of Sales"
        assert contact["department"] == "Sales"
        assert contact["source"] == "salesforce"
    
    def test_normalize_opportunities(self, mock_adapter):
        """Test opportunity schema normalization."""
        raw_records = [
            {
                "Id": "0061234567890ABC",
                "Name": "Q1 Enterprise Deal",
                "AccountId": "0011234567890ABC",
                "StageName": "Proposal",
                "Amount": 250000,
                "Probability": 60,
                "CloseDate": "2024-03-31",
                "Type": "New Business",
                "LeadSource": "Referral",
                "IsClosed": False,
                "IsWon": False,
                "CreatedDate": "2024-01-10T08:00:00Z",
                "LastModifiedDate": "2024-01-20T16:30:00Z",
            }
        ]
        
        normalized = mock_adapter._normalize_opportunities(raw_records)
        
        assert len(normalized) == 1
        opp = normalized[0]
        
        assert opp["id"] == "0061234567890ABC"
        assert opp["name"] == "Q1 Enterprise Deal"
        assert opp["account_id"] == "0011234567890ABC"
        assert opp["stage"] == "Proposal"
        assert opp["amount"] == 250000
        assert opp["probability"] == 60
        assert opp["is_closed"] is False
        assert opp["is_won"] is False
        assert opp["source"] == "salesforce"
    
    def test_get_mode(self, mock_adapter):
        """Test adapter reports correct mode."""
        assert mock_adapter.get_mode() == AdapterMode.LIVE
    
    @patch('httpx.post')
    def test_authentication_success(self, mock_post, mock_config):
        """Test successful OAuth authentication."""
        # Mock successful auth response
        mock_response = Mock()
        mock_response.json.return_value = {
            "access_token": "new_access_token",
            "instance_url": "https://prod.salesforce.com",
            "issued_at": 7200,
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        
        adapter = SalesforceLiveAdapter(mock_config)
        
        # Check token was set
        assert adapter._access_token == "new_access_token"
        assert adapter._instance_url == "https://prod.salesforce.com"
        
        # Check auth was called with correct params
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args[1]
        assert call_kwargs["data"]["grant_type"] == "password"
        assert call_kwargs["data"]["username"] == "test@example.com"
    
    def test_fetch_accounts_with_mock_client(self, mock_adapter):
        """Test fetch_accounts with mocked HTTP client."""
        # Mock SafeClient response
        mock_response = Mock()
        mock_response.json.return_value = {
            "records": [
                {
                    "Id": "001TESTID",
                    "Name": "Test Account",
                    "Industry": "Software",
                    "AnnualRevenue": 1000000,
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_adapter.client.get = Mock(return_value=mock_response)
        
        # Fetch accounts
        accounts = mock_adapter.fetch_accounts({"limit": 10})
        
        # Verify
        assert len(accounts) == 1
        assert accounts[0]["id"] == "001TESTID"
        assert accounts[0]["name"] == "Test Account"
        assert accounts[0]["source"] == "salesforce"
        
        # Verify SOQL query was built
        mock_adapter.client.get.assert_called_once()
        call_args = mock_adapter.client.get.call_args
        assert "query" in call_args[1]["params"]
        assert "SELECT" in call_args[1]["params"]["q"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
