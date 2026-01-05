#!/usr/bin/env python3
"""
Unit tests for 6sense live adapter.

Tests intent scoring, keyword research, and buying stage tracking without real credentials.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx

from cuga.adapters.sales.sixsense_live import SixSenseLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "api_key": "test_6sense_api_key_123",
        },
        metadata={"trace_id": "test-trace-sixsense"},
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create 6sense adapter with mocked HTTP client."""
    with patch('cuga.adapters.sales.sixsense_live.SafeClient'):
        adapter = SixSenseLiveAdapter(mock_config)
        adapter.client = Mock()
        return adapter


class TestSixSenseAdapter:
    """Test 6sense adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        with patch('cuga.adapters.sales.sixsense_live.SafeClient'):
            adapter = SixSenseLiveAdapter(mock_config)
            
            assert adapter.config == mock_config
            assert adapter.trace_id == "test-trace-sixsense"
            assert adapter.api_key == "test_6sense_api_key_123"
    
    def test_validate_config_missing_api_key(self):
        """Test config validation catches missing API key."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={},
            metadata={"trace_id": "test"},
        )
        
        with pytest.raises(ValueError, match="api_key"):
            SixSenseLiveAdapter(invalid_config)
    
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
        mock_adapter.client.get.assert_called_once()
    
    def test_validate_connection_failure(self, mock_adapter):
        """Test connection validation with failed response."""
        mock_adapter.client.get.side_effect = httpx.HTTPStatusError(
            "Unauthorized", request=Mock(), response=Mock(status_code=401)
        )
        
        result = mock_adapter.validate_connection()
        
        assert result is False
    
    def test_fetch_accounts_success(self, mock_adapter):
        """Test fetching accounts with successful API response."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "accounts": [
                {
                    "account_id": "acc_123",
                    "company_name": "Acme Corp",
                    "domain": "acme.com",
                    "intent_score": 85,
                    "buying_stage": "solution_education",
                    "employee_count": 500,
                    "revenue": 50000000,
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        accounts = mock_adapter.fetch_accounts({"limit": 10})
        
        assert len(accounts) == 1
        assert accounts[0]["id"] == "acc_123"
        assert accounts[0]["name"] == "Acme Corp"
        assert accounts[0]["domain"] == "acme.com"
        assert accounts[0]["metadata"]["intent_score"] == 85
        assert accounts[0]["metadata"]["buying_stage"] == "solution_education"
    
    def test_fetch_accounts_with_filters(self, mock_adapter):
        """Test fetch accounts applies filters correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"accounts": []}
        mock_adapter.client.get.return_value = mock_response
        
        filters = {
            "score_min": 70,
            "score_max": 90,
            "buying_stage": "solution_education",
            "keywords": ["analytics", "machine learning"],
            "limit": 25
        }
        
        mock_adapter.fetch_accounts(filters)
        
        call_args = mock_adapter.client.get.call_args
        params = call_args[1]["params"]
        
        assert params["score_min"] == 70
        assert params["score_max"] == 90
        assert params["buying_stage"] == "solution_education"
        assert params["limit"] == 25
    
    def test_fetch_accounts_empty_response(self, mock_adapter):
        """Test fetch accounts handles empty response gracefully."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"accounts": []}
        mock_adapter.client.get.return_value = mock_response
        
        accounts = mock_adapter.fetch_accounts()
        
        assert accounts == []
    
    def test_fetch_accounts_404_error(self, mock_adapter):
        """Test fetch accounts handles 404 gracefully."""
        mock_adapter.client.get.side_effect = httpx.HTTPStatusError(
            "Not Found", request=Mock(), response=Mock(status_code=404)
        )
        
        accounts = mock_adapter.fetch_accounts()
        
        assert accounts == []
    
    def test_fetch_buying_signals_success(self, mock_adapter):
        """Test fetching buying signals."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "signals": [
                {
                    "signal_type": "intent_surge",
                    "account_id": "acc_123",
                    "timestamp": "2026-01-04T10:00:00Z",
                    "score_change": 15,
                    "keywords": ["analytics"],
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        signals = mock_adapter.fetch_buying_signals("acc_123")
        
        assert len(signals) == 1
        assert signals[0]["type"] == "intent_surge"
        assert signals[0]["metadata"]["score_change"] == 15
    
    def test_get_account_score_success(self, mock_adapter):
        """Test getting account intent score."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "account_id": "acc_123",
            "intent_score": 82,
            "score_velocity": 5.2,
            "trend": "increasing"
        }
        mock_adapter.client.get.return_value = mock_response
        
        score_data = mock_adapter.get_account_score("acc_123")
        
        assert score_data["score"] == 82
        assert score_data["velocity"] == 5.2
        assert score_data["trend"] == "increasing"
    
    def test_get_intent_segments_success(self, mock_adapter):
        """Test getting intent segments."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "segments": [
                {
                    "segment_name": "Machine Learning",
                    "engagement_score": 75,
                    "keywords": ["ml", "neural networks"]
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        segments = mock_adapter.get_intent_segments("acc_123")
        
        assert len(segments) == 1
        assert segments[0]["segment_name"] == "Machine Learning"
        assert segments[0]["engagement_score"] == 75
    
    def test_get_keyword_research_success(self, mock_adapter):
        """Test getting keyword research data."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "keywords": [
                {
                    "keyword": "analytics platform",
                    "search_volume": 1200,
                    "first_seen": "2026-01-01T00:00:00Z"
                }
            ]
        }
        mock_adapter.client.get.return_value = mock_response
        
        keywords = mock_adapter.get_keyword_research("acc_123")
        
        assert len(keywords) == 1
        assert keywords[0]["keyword"] == "analytics platform"
        assert keywords[0]["search_volume"] == 1200
    
    def test_normalize_account(self, mock_adapter):
        """Test account normalization to canonical format."""
        raw_account = {
            "account_id": "acc_456",
            "company_name": "Test Company",
            "domain": "test.com",
            "intent_score": 78,
            "buying_stage": "problem_awareness",
            "employee_count": 250,
            "annual_revenue": 25000000,
            "industry": "Technology",
            "location": {
                "city": "San Francisco",
                "state": "CA",
                "country": "US"
            }
        }
        
        normalized = mock_adapter._normalize_account(raw_account)
        
        assert normalized["id"] == "acc_456"
        assert normalized["name"] == "Test Company"
        assert normalized["domain"] == "test.com"
        assert normalized["industry"] == "Technology"
        assert normalized["employee_count"] == 250
        assert normalized["revenue"] == 25000000
        assert normalized["location"]["city"] == "San Francisco"
        assert normalized["metadata"]["intent_score"] == 78
        assert normalized["metadata"]["buying_stage"] == "problem_awareness"
        assert normalized["metadata"]["source"] == "6sense"
