#!/usr/bin/env python3
"""
Unit tests for ZoomInfo live adapter.

Tests schema normalization, signal processing, and API interaction without requiring real credentials.
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from cuga.adapters.sales.zoominfo_live import ZoomInfoLiveAdapter
from cuga.adapters.sales.protocol import AdapterConfig, AdapterMode


@pytest.fixture
def mock_config():
    """Create mock adapter configuration."""
    return AdapterConfig(
        mode=AdapterMode.LIVE,
        credentials={
            "api_key": "test_api_key_12345",
            "username": "test@example.com",  # Optional
            "password": "test_password",  # Optional
        },
        trace_id="test-trace-001",
    )


@pytest.fixture
def mock_adapter(mock_config):
    """Create ZoomInfo adapter (no real API calls)."""
    adapter = ZoomInfoLiveAdapter(mock_config)
    return adapter


class TestZoomInfoAdapter:
    """Test ZoomInfo adapter functionality."""
    
    def test_initialization(self, mock_config):
        """Test adapter initializes with valid config."""
        adapter = ZoomInfoLiveAdapter(mock_config)
        
        assert adapter.config == mock_config
        assert adapter.trace_id == "test-trace-001"
        assert adapter.client.base_url == "https://api.zoominfo.com/v1"
    
    def test_validate_config_missing_api_key(self):
        """Test config validation catches missing API key."""
        invalid_config = AdapterConfig(
            mode=AdapterMode.LIVE,
            credentials={
                # Missing api_key
            },
            trace_id="test",
        )
        
        with pytest.raises(ValueError, match="missing required credentials"):
            ZoomInfoLiveAdapter(invalid_config)
    
    def test_normalize_accounts(self, mock_adapter):
        """Test company schema normalization."""
        raw_companies = [
            {
                "id": "12345",
                "companyName": "Acme Corp",
                "industry": "Technology",
                "revenue": 5000000,
                "employeeCount": 150,
                "street": "123 Main St",
                "city": "San Francisco",
                "state": "CA",
                "country": "USA",
                "zipCode": "94105",
                "phone": "+1-555-0100",
                "website": "https://acme.com",
                "companyDescription": "Software company",
            }
        ]
        
        normalized = mock_adapter._normalize_accounts(raw_companies)
        
        assert len(normalized) == 1
        company = normalized[0]
        
        # Check field mapping
        assert company["id"] == "12345"
        assert company["name"] == "Acme Corp"
        assert company["industry"] == "Technology"
        assert company["revenue"] == 5000000
        assert company["employee_count"] == 150
        assert company["phone"] == "+1-555-0100"
        assert company["website"] == "https://acme.com"
        assert company["source"] == "zoominfo"
        
        # Check nested address
        assert company["address"]["city"] == "San Francisco"
        assert company["address"]["state"] == "CA"
        assert company["address"]["postal_code"] == "94105"
    
    def test_normalize_contacts(self, mock_adapter):
        """Test contact schema normalization."""
        raw_contacts = [
            {
                "id": "67890",
                "firstName": "John",
                "lastName": "Doe",
                "email": "john.doe@acme.com",
                "directPhoneNumber": "+1-555-0101",
                "jobTitle": "VP of Sales",
                "jobFunction": "Sales",
                "managementLevel": "C-Level",
            }
        ]
        
        normalized = mock_adapter._normalize_contacts(raw_contacts)
        
        assert len(normalized) == 1
        contact = normalized[0]
        
        assert contact["id"] == "67890"
        assert contact["first_name"] == "John"
        assert contact["last_name"] == "Doe"
        assert contact["email"] == "john.doe@acme.com"
        assert contact["phone"] == "+1-555-0101"
        assert contact["title"] == "VP of Sales"
        assert contact["department"] == "Sales"
        assert contact["seniority"] == "C-Level"
        assert contact["source"] == "zoominfo"
    
    def test_normalize_buying_signals(self, mock_adapter):
        """Test buying signal (scoop) normalization."""
        raw_scoops = [
            {
                "type": "funding",
                "date": "2024-01-15",
                "headline": "Acme Corp raises $50M Series B",
                "summary": "Tech startup secures funding for expansion",
                "severity": "high",
                "url": "https://news.example.com/acme-funding",
            },
            {
                "type": "executive_change",
                "date": "2024-02-01",
                "headline": "Acme Corp appoints new CFO",
                "severity": "medium",
            },
            {
                "type": "tech_install",
                "date": "2024-02-10",
                "headline": "Acme Corp adopts Salesforce",
                "severity": "low",
            },
        ]
        
        normalized = mock_adapter._normalize_buying_signals(raw_scoops)
        
        assert len(normalized) == 3
        
        # Funding signal
        signal1 = normalized[0]
        assert signal1["signal_type"] == "funding_event"
        assert signal1["signal_date"] == "2024-01-15"
        assert "raises $50M" in signal1["description"]
        assert signal1["confidence"] >= 0.8  # High severity
        assert signal1["metadata"]["source_type"] == "funding"
        assert signal1["source"] == "zoominfo"
        
        # Leadership signal
        signal2 = normalized[1]
        assert signal2["signal_type"] == "leadership_change"
        assert signal2["confidence"] >= 0.5  # Medium severity
        
        # Tech adoption signal
        signal3 = normalized[2]
        assert signal3["signal_type"] == "tech_adoption"
        assert signal3["confidence"] >= 0.5  # Low severity + type boost
    
    def test_calculate_signal_confidence(self, mock_adapter):
        """Test signal confidence calculation."""
        # High severity funding event
        high_confidence_scoop = {
            "type": "funding",
            "severity": "high"
        }
        confidence = mock_adapter._calculate_signal_confidence(high_confidence_scoop)
        assert confidence >= 0.9  # Base + severity + type
        
        # Medium severity news
        medium_confidence_scoop = {
            "type": "news",
            "severity": "medium"
        }
        confidence = mock_adapter._calculate_signal_confidence(medium_confidence_scoop)
        assert 0.5 <= confidence <= 0.7
        
        # Low severity
        low_confidence_scoop = {
            "type": "other",
            "severity": "low"
        }
        confidence = mock_adapter._calculate_signal_confidence(low_confidence_scoop)
        assert confidence >= 0.5  # At least base confidence
    
    def test_get_mode(self, mock_adapter):
        """Test adapter reports correct mode."""
        assert mock_adapter.get_mode() == AdapterMode.LIVE
    
    def test_fetch_opportunities_returns_empty(self, mock_adapter):
        """Test fetch_opportunities returns empty (ZoomInfo is not a CRM)."""
        opportunities = mock_adapter.fetch_opportunities()
        
        assert opportunities == []
    
    def test_fetch_accounts_with_mock_client(self, mock_adapter):
        """Test fetch_accounts with mocked HTTP client."""
        # Mock SafeClient response
        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {
                    "id": "12345",
                    "companyName": "Test Company",
                    "industry": "Software",
                    "revenue": 1000000,
                    "employeeCount": 50,
                }
            ]
        }
        mock_response.raise_for_status = Mock()
        
        mock_adapter.client.post = Mock(return_value=mock_response)
        
        # Fetch accounts
        companies = mock_adapter.fetch_accounts({"limit": 10})
        
        # Verify
        assert len(companies) == 1
        assert companies[0]["id"] == "12345"
        assert companies[0]["name"] == "Test Company"
        assert companies[0]["source"] == "zoominfo"
        
        # Verify API call
        mock_adapter.client.post.assert_called_once()
        call_args = mock_adapter.client.post.call_args
        assert call_args[0][0] == "/search/company"
        assert call_args[1]["json"]["rpp"] == 10  # Limit
    
    def test_fetch_accounts_with_filters(self, mock_adapter):
        """Test fetch_accounts applies filters correctly."""
        mock_response = Mock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = Mock()
        mock_adapter.client.post = Mock(return_value=mock_response)
        
        # Fetch with filters
        filters = {
            "limit": 50,
            "revenue_min": 1000000,
            "revenue_max": 10000000,
            "employee_min": 10,
            "employee_max": 500,
            "industry": "Technology",
        }
        mock_adapter.fetch_accounts(filters)
        
        # Verify filters in payload
        call_args = mock_adapter.client.post.call_args
        payload = call_args[1]["json"]
        
        assert payload["rpp"] == 50
        assert "filters" in payload
        
        # Check filter criteria
        filter_fields = {f["field"] for f in payload["filters"]}
        assert "revenue" in filter_fields
        assert "employeeCount" in filter_fields
        assert "industry" in filter_fields
    
    def test_enrich_company(self, mock_adapter):
        """Test company enrichment by domain."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "company": {
                "id": "12345",
                "companyName": "Acme Corp",
                "industry": "Technology",
                "revenue": 5000000,
                "employeeCount": 150,
                "foundedYear": 2010,
                "technologies": ["Salesforce", "AWS", "Python"],
                "linkedinUrl": "https://linkedin.com/company/acme",
            }
        }
        mock_response.raise_for_status = Mock()
        mock_adapter.client.get = Mock(return_value=mock_response)
        
        # Enrich company
        enriched = mock_adapter.enrich_company("acme.com")
        
        # Verify
        assert enriched["id"] == "12345"
        assert enriched["name"] == "Acme Corp"
        assert enriched["domain"] == "acme.com"
        assert enriched["founded_year"] == 2010
        assert enriched["technologies"] == ["Salesforce", "AWS", "Python"]
        assert enriched["source"] == "zoominfo"
        
        # Verify API call
        mock_adapter.client.get.assert_called_once()
        call_args = mock_adapter.client.get.call_args
        assert call_args[0][0] == "/company/lookup"
        assert call_args[1]["params"]["website"] == "acme.com"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
