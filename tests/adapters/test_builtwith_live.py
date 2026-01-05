#!/usr/bin/env python3
"""
Unit tests for BuiltWith live adapter.

Tests technology detection, tech stack history, and market intelligence without real credentials.
"""

import pytest
from unittest.mock import Mock, patch
import httpx

from cuga.adapters.sales.builtwith_live import BuiltWithLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "api_key": "test_builtwith_key_xyz",
        },
        metadata={"trace_id": "test-trace-builtwith"},
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create BuiltWith adapter with mocked HTTP client."""
    with patch('cuga.adapters.sales.builtwith_live.SafeClient'):
        adapter = BuiltWithLiveAdapter(mock_config)
        adapter.client = Mock()
        return adapter


class TestBuiltWithAdapter:
    """Test BuiltWith adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        with patch('cuga.adapters.sales.builtwith_live.SafeClient'):
            adapter = BuiltWithLiveAdapter(mock_config)
            
            assert adapter.config == mock_config
            assert adapter.trace_id == "test-trace-builtwith"
            assert adapter.api_key == "test_builtwith_key_xyz"
    
    def test_validate_config_missing_api_key(self):
        """Test config validation catches missing API key."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={},
            metadata={"trace_id": "test"},
        )
        
        with pytest.raises(ValueError, match="api_key"):
            BuiltWithLiveAdapter(invalid_config)
    
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
        """Test searching companies by technology."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Results": [
                {
                    "Domain": "example.com",
                    "Country": "US",
                    "FirstIndexed": "2020-01-01",
                    "LastIndexed": "2026-01-01",
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        accounts = mock_adapter.fetch_accounts({"technology": "React", "limit": 10})
        
        assert len(accounts) == 1
        assert accounts[0]["id"] == "example.com"
        assert accounts[0]["domain"] == "example.com"
        assert accounts[0]["location"]["country"] == "US"
    
    def test_fetch_accounts_no_technology_filter(self, mock_adapter):
        """Test fetch accounts requires technology filter."""
        accounts = mock_adapter.fetch_accounts({})
        
        assert accounts == []
    
    def test_fetch_accounts_404_error(self, mock_adapter):
        """Test fetch accounts handles 404 gracefully."""
        mock_adapter.client.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock(status_code=404)
        )
        
        accounts = mock_adapter.fetch_accounts({"technology": "UnknownTech"})
        
        assert accounts == []
    
    def test_fetch_buying_signals_success(self, mock_adapter):
        """Test deriving buying signals from technology changes."""
        # Mock get_technology_profile
        with patch.object(mock_adapter, 'get_technology_profile') as mock_tech:
            mock_tech.return_value = {
                "Technologies": {
                    "Analytics": [
                        {
                            "Name": "Google Analytics",
                            "Tag": "ga",
                            "FirstDetected": "2025-12-01",
                        }
                    ],
                    "Marketing": [
                        {
                            "Name": "HubSpot",
                            "Tag": "hubspot",
                            "FirstDetected": "2025-11-15",
                        }
                    ]
                }
            }
            
            signals = mock_adapter.fetch_buying_signals("example.com")
            
            assert len(signals) > 0
            assert signals[0]["type"] == "tech_adoption"
            assert "Google Analytics" in signals[0]["description"] or "HubSpot" in signals[0]["description"]
    
    def test_fetch_buying_signals_no_profile(self, mock_adapter):
        """Test fetch buying signals when profile not found."""
        with patch.object(mock_adapter, 'get_technology_profile') as mock_tech:
            mock_tech.return_value = None
            
            signals = mock_adapter.fetch_buying_signals("notfound.com")
            
            assert signals == []
    
    def test_get_technology_profile_success(self, mock_adapter):
        """Test getting technology profile for domain."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Results": [
                {
                    "Technologies": {
                        "Web Servers": [
                            {"Name": "Nginx", "Tag": "nginx"}
                        ]
                    }
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        profile = mock_adapter.get_technology_profile("test.com")
        
        assert profile is not None
        assert "Technologies" in profile
    
    def test_get_technology_profile_not_found(self, mock_adapter):
        """Test get technology profile when domain not found."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"Errors": ["Domain not found"]}
        mock_adapter.client.get.return_value = mock_response
        
        profile = mock_adapter.get_technology_profile("notfound.com")
        
        assert profile is None
    
    def test_get_technology_history_success(self, mock_adapter):
        """Test getting technology adoption history."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "Results": [
                {
                    "Technologies": {
                        "JavaScript Frameworks": [
                            {
                                "Name": "React",
                                "FirstDetected": "2020-01-01",
                                "LastDetected": "2026-01-01"
                            }
                        ]
                    }
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        history = mock_adapter.get_technology_history("test.com")
        
        assert "JavaScript Frameworks" in history
    
    def test_enrich_company_success(self, mock_adapter):
        """Test enriching company with tech stack."""
        # Mock get_technology_profile
        with patch.object(mock_adapter, 'get_technology_profile') as mock_tech:
            mock_tech.return_value = {
                "FirstIndexed": "2020-01-01",
                "LastIndexed": "2026-01-01",
                "Meta": {"Country": "US"},
                "Technologies": {
                    "Analytics": [
                        {
                            "Name": "Google Analytics",
                            "FirstDetected": "2020-01-01",
                            "LastDetected": "2026-01-01"
                        }
                    ]
                }
            }
            
            company = mock_adapter.enrich_company("test.com")
            
            assert company is not None
            assert company["id"] == "test.com"
            assert company["domain"] == "test.com"
            assert company["metadata"]["technology_count"] == 1
    
    def test_enrich_company_not_found(self, mock_adapter):
        """Test enriching company when not found."""
        with patch.object(mock_adapter, 'get_technology_profile') as mock_tech:
            mock_tech.return_value = None
            
            company = mock_adapter.enrich_company("notfound.com")
            
            assert company is None
    
    def test_normalize_tech_result(self, mock_adapter):
        """Test tech search result normalization."""
        raw_result = {
            "Domain": "test.com",
            "Country": "UK",
            "FirstIndexed": "2019-05-10",
            "LastIndexed": "2025-12-31",
        }
        
        normalized = mock_adapter._normalize_tech_result(raw_result)
        
        assert normalized["id"] == "test.com"
        assert normalized["name"] == "Test"
        assert normalized["domain"] == "test.com"
        assert normalized["location"]["country"] == "UK"
        assert normalized["metadata"]["first_indexed"] == "2019-05-10"
        assert normalized["metadata"]["source"] == "builtwith"
    
    def test_normalize_tech_profile(self, mock_adapter):
        """Test technology profile normalization."""
        profile = {
            "FirstIndexed": "2018-01-01",
            "LastIndexed": "2026-01-01",
            "Meta": {"Country": "Canada"},
            "Technologies": {
                "Web Servers": [
                    {
                        "Name": "Apache",
                        "FirstDetected": "2018-01-01",
                        "LastDetected": "2026-01-01"
                    }
                ],
                "CDN": [
                    {
                        "Name": "Cloudflare",
                        "FirstDetected": "2019-06-01",
                        "LastDetected": "2026-01-01"
                    }
                ]
            }
        }
        
        normalized = mock_adapter._normalize_tech_profile("example.com", profile)
        
        assert normalized["id"] == "example.com"
        assert normalized["domain"] == "example.com"
        assert normalized["location"]["country"] == "Canada"
        assert normalized["metadata"]["technology_count"] == 2
        assert len(normalized["metadata"]["technologies"]) == 2
        assert normalized["metadata"]["source"] == "builtwith"
