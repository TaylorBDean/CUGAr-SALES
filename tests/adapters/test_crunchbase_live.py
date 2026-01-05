#!/usr/bin/env python3
"""
Unit tests for Crunchbase live adapter.

Tests organization search, funding rounds, and investment intelligence without real credentials.
"""

import pytest
from unittest.mock import Mock, patch
import httpx

from cuga.adapters.sales.crunchbase_live import CrunchbaseLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "api_key": "test_crunchbase_key_abc",
        },
        metadata={"trace_id": "test-trace-crunchbase"},
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create Crunchbase adapter with mocked HTTP client."""
    with patch('cuga.adapters.sales.crunchbase_live.SafeClient'):
        adapter = CrunchbaseLiveAdapter(mock_config)
        adapter.client = Mock()
        return adapter


class TestCrunchbaseAdapter:
    """Test Crunchbase adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        with patch('cuga.adapters.sales.crunchbase_live.SafeClient'):
            adapter = CrunchbaseLiveAdapter(mock_config)
            
            assert adapter.config == mock_config
            assert adapter.trace_id == "test-trace-crunchbase"
    
    def test_validate_config_missing_api_key(self):
        """Test config validation catches missing API key."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={},
            metadata={"trace_id": "test"},
        )
        
        with pytest.raises(ValueError, match="api_key"):
            CrunchbaseLiveAdapter(invalid_config)
    
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
        """Test fetching organizations with successful API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entities": [
                {
                    "properties": {
                        "identifier": {"permalink": "acme-corp"},
                        "name": "Acme Corp",
                        "website": {"value": "acme.com"},
                        "short_description": "Leading software company",
                        "founded_on": {"value": "2010-01-01"},
                        "num_employees_enum": "c_00101_00250",
                        "funding_total": {"value": 50000000, "currency": "USD"},
                        "last_funding_type": "series_b",
                        "categories": [{"value": "Software"}],
                    }
                }
            ]
        }
        mock_adapter.client.post.return_value = mock_response
        
        accounts = mock_adapter.fetch_accounts({"limit": 10})
        
        assert len(accounts) == 1
        assert accounts[0]["id"] == "acme-corp"
        assert accounts[0]["name"] == "Acme Corp"
        assert accounts[0]["domain"] == "acme.com"
        assert accounts[0]["metadata"]["funding_total"] == 50000000
    
    def test_fetch_accounts_with_filters(self, mock_adapter):
        """Test fetch accounts applies filters correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"entities": []}
        mock_adapter.client.post.return_value = mock_response
        
        filters = {
            "funding_round_min": 1000000,
            "funding_round_max": 10000000,
            "funding_stage": "series_a",
            "founded_year_min": 2015,
            "founded_year_max": 2020,
            "limit": 20
        }
        
        mock_adapter.fetch_accounts(filters)
        
        call_args = mock_adapter.client.post.call_args
        json_data = call_args[1]["json"]
        
        assert json_data["limit"] == 20
        assert "query" in json_data
    
    def test_fetch_accounts_404_error(self, mock_adapter):
        """Test fetch accounts handles 404 gracefully."""
        mock_adapter.client.post.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock(status_code=404)
        )
        
        accounts = mock_adapter.fetch_accounts()
        
        assert accounts == []
    
    def test_fetch_buying_signals_success(self, mock_adapter):
        """Test deriving buying signals from funding events."""
        # Mock get_funding_rounds
        with patch.object(mock_adapter, 'get_funding_rounds') as mock_funding:
            mock_funding.return_value = [
                {
                    "investment_type": "series_b",
                    "money_raised": {"value": 25000000, "currency": "USD"},
                    "announced_on": "2026-01-01",
                    "num_investors": 5,
                }
            ]
            
            signals = mock_adapter.fetch_buying_signals("acme-corp")
            
            assert len(signals) > 0
            assert signals[0]["type"] == "funding_event"
            assert signals[0]["metadata"]["funding_type"] == "series_b"
            assert signals[0]["metadata"]["amount"] == 25000000
    
    def test_enrich_company_success(self, mock_adapter):
        """Test enriching company by domain."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "entities": [
                {
                    "properties": {
                        "identifier": {"permalink": "test-company"},
                        "name": "Test Company",
                        "website": {"value": "test.com"},
                        "funding_total": {"value": 10000000, "currency": "USD"},
                    }
                }
            ]
        }
        mock_adapter.client.post.return_value = mock_response
        
        company = mock_adapter.enrich_company("test.com")
        
        assert company is not None
        assert company["id"] == "test-company"
        assert company["domain"] == "test.com"
    
    def test_enrich_company_not_found(self, mock_adapter):
        """Test enriching company when not found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"entities": []}
        mock_adapter.client.post.return_value = mock_response
        
        company = mock_adapter.enrich_company("notfound.com")
        
        assert company is None
    
    def test_get_funding_rounds_success(self, mock_adapter):
        """Test getting funding history."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "cards": {
                "funding_rounds": [
                    {
                        "investment_type": "seed",
                        "money_raised": {"value": 2000000, "currency": "USD"},
                        "announced_on": "2020-01-15",
                    }
                ]
            }
        }
        mock_adapter.client.get.return_value = mock_response
        
        rounds = mock_adapter.get_funding_rounds("test-org")
        
        assert len(rounds) == 1
        assert rounds[0]["investment_type"] == "seed"
    
    def test_get_funding_rounds_404(self, mock_adapter):
        """Test get funding rounds handles 404."""
        mock_adapter.client.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock(status_code=404)
        )
        
        rounds = mock_adapter.get_funding_rounds("test-org")
        
        assert rounds == []
    
    def test_normalize_organization(self, mock_adapter):
        """Test organization normalization to canonical format."""
        raw_org = {
            "identifier": {"permalink": "example-inc"},
            "name": "Example Inc",
            "website": {"value": "example.com"},
            "short_description": "Example company",
            "founded_on": {"value": "2015-03-20"},
            "num_employees_enum": "c_00051_00100",
            "funding_total": {"value": 15000000, "currency": "USD"},
            "last_funding_type": "series_a",
            "categories": [{"value": "Technology"}, {"value": "Software"}],
            "location_identifiers": [{"value": "San Francisco"}],
        }
        
        normalized = mock_adapter._normalize_organization(raw_org)
        
        assert normalized["id"] == "example-inc"
        assert normalized["name"] == "Example Inc"
        assert normalized["domain"] == "example.com"
        assert normalized["industry"] == "Technology, Software"
        assert normalized["employee_count"] == 75  # Midpoint of range
        assert normalized["metadata"]["funding_total"] == 15000000
        assert normalized["metadata"]["last_funding_type"] == "series_a"
        assert normalized["metadata"]["source"] == "crunchbase"
    
    def test_parse_employee_range(self, mock_adapter):
        """Test employee range parsing."""
        assert mock_adapter._parse_employee_range("c_00001_00010") == 5
        assert mock_adapter._parse_employee_range("c_00051_00100") == 75
        assert mock_adapter._parse_employee_range("c_00501_01000") == 750
        assert mock_adapter._parse_employee_range("c_10001_max") == 15000
        assert mock_adapter._parse_employee_range(None) is None
        assert mock_adapter._parse_employee_range("unknown_range") is None
