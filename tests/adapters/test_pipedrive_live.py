#!/usr/bin/env python3
"""
Unit tests for Pipedrive live adapter.

Tests organizations, persons, deals, and buying signals without real credentials.
"""

import pytest
from unittest.mock import Mock, patch
import httpx

from cuga.adapters.sales.pipedrive_live import PipedriveLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "api_token": "test_pipedrive_token_789",
        },
        metadata={"trace_id": "test-trace-pipedrive"},
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create Pipedrive adapter with mocked HTTP client."""
    with patch('cuga.adapters.sales.pipedrive_live.SafeClient'):
        adapter = PipedriveLiveAdapter(mock_config)
        adapter.client = Mock()
        return adapter


class TestPipedriveAdapter:
    """Test Pipedrive adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        with patch('cuga.adapters.sales.pipedrive_live.SafeClient'):
            adapter = PipedriveLiveAdapter(mock_config)
            
            assert adapter.config == mock_config
            assert adapter.trace_id == "test-trace-pipedrive"
            assert adapter.api_token == "test_pipedrive_token_789"
    
    def test_validate_config_missing_api_token(self):
        """Test config validation catches missing API token."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={},
            metadata={"trace_id": "test"},
        )
        
        with pytest.raises(ValueError, match="api_token"):
            PipedriveLiveAdapter(invalid_config)
    
    def test_get_mode(self, mock_adapter):
        """Test adapter mode is LIVE."""
        assert mock_adapter.get_mode() == AdapterMode.LIVE
    
    def test_validate_connection_success(self, mock_adapter):
        """Test connection validation with successful response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}
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
        """Test fetching organizations with successful API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {
                    "id": 101,
                    "name": "Acme Organization",
                    "address": "123 Main St",
                    "address_locality": "San Francisco",
                    "address_admin_area_level_1": "CA",
                    "address_country": "US",
                    "people_count": 50,
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        accounts = mock_adapter.fetch_accounts({"limit": 10})
        
        assert len(accounts) == 1
        assert accounts[0]["id"] == "101"
        assert accounts[0]["name"] == "Acme Organization"
        assert accounts[0]["location"]["city"] == "San Francisco"
    
    def test_fetch_accounts_with_filters(self, mock_adapter):
        """Test fetch accounts applies filters correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": []}
        mock_adapter.client.get.return_value = mock_response
        
        filters = {"limit": 25}
        
        mock_adapter.fetch_accounts(filters)
        
        call_args = mock_adapter.client.get.call_args
        params = call_args[1]["params"]
        
        assert params["api_token"] == "test_pipedrive_token_789"
        assert params["limit"] == 25
    
    def test_fetch_contacts_success(self, mock_adapter):
        """Test fetching persons for an organization."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {
                    "id": 201,
                    "name": "John Doe",
                    "email": [{"value": "john@example.com", "primary": True}],
                    "phone": [{"value": "+1234567890", "primary": True}],
                    "org_id": 101,
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        contacts = mock_adapter.fetch_contacts("101")
        
        assert len(contacts) == 1
        assert contacts[0]["id"] == "201"
        assert contacts[0]["email"] == "john@example.com"
    
    def test_fetch_opportunities_success(self, mock_adapter):
        """Test fetching deals for an organization."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "data": [
                {
                    "id": 301,
                    "title": "Q1 Enterprise Deal",
                    "value": 50000,
                    "currency": "USD",
                    "status": "open",
                    "stage_id": 5,
                    "org_id": 101,
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        opportunities = mock_adapter.fetch_opportunities("101")
        
        assert len(opportunities) == 1
        assert opportunities[0]["id"] == "301"
        assert opportunities[0]["name"] == "Q1 Enterprise Deal"
        assert opportunities[0]["value"] == 50000
    
    def test_fetch_opportunities_with_status_filter(self, mock_adapter):
        """Test fetch opportunities with status filter."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": []}
        mock_adapter.client.get.return_value = mock_response
        
        mock_adapter.fetch_opportunities("101", {"status": "won"})
        
        call_args = mock_adapter.client.get.call_args
        params = call_args[1]["params"]
        
        assert params["status"] == "won"
    
    def test_fetch_buying_signals_success(self, mock_adapter):
        """Test deriving buying signals from deal activity."""
        # Mock fetch_opportunities to return deals
        with patch.object(mock_adapter, 'fetch_opportunities') as mock_opps:
            mock_opps.return_value = [
                {
                    "id": "301",
                    "name": "Test Deal",
                    "value": 100000,
                    "stage": "negotiation",
                    "created_at": "2026-01-04T10:00:00Z"
                }
            ]
            
            signals = mock_adapter.fetch_buying_signals("101")
            
            assert len(signals) > 0
            assert signals[0]["type"] in ["deal_created", "deal_progression", "activity_logged"]
    
    def test_normalize_organization(self, mock_adapter):
        """Test organization normalization to canonical format."""
        raw_org = {
            "id": 999,
            "name": "Test Org",
            "address": "456 Oak Ave",
            "address_locality": "Boston",
            "address_admin_area_level_1": "MA",
            "address_country": "US",
            "people_count": 100,
        }
        
        normalized = mock_adapter._normalize_organization(raw_org)
        
        assert normalized["id"] == "999"
        assert normalized["name"] == "Test Org"
        assert normalized["location"]["city"] == "Boston"
        assert normalized["location"]["state"] == "MA"
        assert normalized["location"]["country"] == "US"
        assert normalized["metadata"]["people_count"] == 100
        assert normalized["metadata"]["source"] == "pipedrive"
    
    def test_normalize_person(self, mock_adapter):
        """Test person normalization to canonical format."""
        raw_person = {
            "id": 888,
            "name": "Jane Smith",
            "email": [{"value": "jane@test.com", "primary": True}],
            "phone": [{"value": "+9876543210", "primary": True}],
            "org_id": 999,
        }
        
        normalized = mock_adapter._normalize_person(raw_person)
        
        assert normalized["id"] == "888"
        assert normalized["first_name"] == "Jane"
        assert normalized["last_name"] == "Smith"
        assert normalized["email"] == "jane@test.com"
        assert normalized["phone"] == "+9876543210"
        assert normalized["metadata"]["org_id"] == 999
        assert normalized["metadata"]["source"] == "pipedrive"
    
    def test_normalize_deal(self, mock_adapter):
        """Test deal normalization to canonical format."""
        raw_deal = {
            "id": 777,
            "title": "Test Deal",
            "value": 75000,
            "currency": "USD",
            "status": "open",
            "stage_id": 3,
            "org_id": 999,
            "add_time": "2026-01-01 10:00:00",
        }
        
        normalized = mock_adapter._normalize_deal(raw_deal)
        
        assert normalized["id"] == "777"
        assert normalized["name"] == "Test Deal"
        assert normalized["value"] == 75000
        assert normalized["currency"] == "USD"
        assert normalized["stage"] == "stage_3"
        assert normalized["status"] == "open"
        assert normalized["metadata"]["org_id"] == 999
        assert normalized["metadata"]["source"] == "pipedrive"
