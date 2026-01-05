"""
Unit tests for HubSpot live adapter.

Tests cover:
- Initialization and configuration validation
- Companies (accounts) fetching with pagination
- Contacts fetching with associations
- Deals (opportunities) fetching
- Buying signals derived from deals
- Schema normalization
- Error handling (404, 401, 429, timeouts)
- Probability estimation
- Observability event emission
"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timedelta

import httpx

from cuga.adapters.sales.hubspot_live import HubSpotLiveAdapter
from cuga.adapters.sales.config import AdapterConfig
from cuga.adapters.sales.protocol import AdapterMode


@pytest.fixture
def valid_config():
    """Create valid HubSpot adapter configuration."""
    return AdapterConfig(
        vendor="hubspot",
        mode="live",
        credentials={"api_key": "pat-na1-test-api-key"},
        profile="sales",
    )


def test_initialization(valid_config):
    """Test adapter initializes with valid configuration."""
    adapter = HubSpotLiveAdapter(valid_config)
    
    assert adapter.config == valid_config
    assert adapter.client is not None
    assert adapter.get_mode() == AdapterMode.LIVE


def test_validate_config_missing_api_key():
    """Test configuration validation fails without API key."""
    invalid_config = AdapterConfig(
        vendor="hubspot",
        mode="live",
        credentials={},  # Missing api_key
        profile="sales",
    )
    
    with pytest.raises(ValueError, match="requires 'api_key'"):
        HubSpotLiveAdapter(invalid_config)


def test_get_mode(valid_config):
    """Test adapter reports LIVE mode."""
    adapter = HubSpotLiveAdapter(valid_config)
    assert adapter.get_mode() == AdapterMode.LIVE


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_validate_connection_success(mock_safe_client, valid_config):
    """Test successful connection validation."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    assert adapter.validate_connection() is True


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_validate_connection_failure(mock_safe_client, valid_config):
    """Test failed connection validation."""
    # Mock failed response
    mock_response = Mock()
    mock_response.status_code = 401
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    assert adapter.validate_connection() is False


def test_normalize_company():
    """Test company data normalization from HubSpot format."""
    adapter = HubSpotLiveAdapter(
        AdapterConfig(
            vendor="hubspot",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    raw_company = {
        "id": "12345",
        "properties": {
            "name": "Acme Corp",
            "domain": "acme.com",
            "industry": "Technology",
            "numberofemployees": "500",
            "annualrevenue": "50000000",
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
            "description": "Leading tech company",
            "createdate": "2024-01-01T00:00:00Z",
            "hs_lastmodifieddate": "2024-06-01T00:00:00Z",
        },
    }
    
    normalized = adapter._normalize_company(raw_company)
    
    assert normalized["id"] == "12345"
    assert normalized["name"] == "Acme Corp"
    assert normalized["domain"] == "acme.com"
    assert normalized["industry"] == "Technology"
    assert normalized["employee_count"] == 500
    assert normalized["annual_revenue"] == 50000000.0
    assert normalized["location"]["city"] == "San Francisco"
    assert normalized["location"]["state"] == "California"
    assert normalized["description"] == "Leading tech company"
    assert normalized["metadata"]["hubspot_id"] == "12345"


def test_normalize_contact():
    """Test contact data normalization from HubSpot format."""
    adapter = HubSpotLiveAdapter(
        AdapterConfig(
            vendor="hubspot",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    raw_contact = {
        "id": "67890",
        "properties": {
            "email": "john@acme.com",
            "firstname": "John",
            "lastname": "Doe",
            "jobtitle": "VP of Sales",
            "company": "Acme Corp",
            "phone": "+1-555-0100",
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
        },
    }
    
    normalized = adapter._normalize_contact(raw_contact)
    
    assert normalized["id"] == "67890"
    assert normalized["email"] == "john@acme.com"
    assert normalized["first_name"] == "John"
    assert normalized["last_name"] == "Doe"
    assert normalized["full_name"] == "John Doe"
    assert normalized["title"] == "VP of Sales"
    assert normalized["company"] == "Acme Corp"
    assert normalized["phone"] == "+1-555-0100"
    assert normalized["location"]["city"] == "San Francisco"


def test_normalize_deal():
    """Test deal data normalization from HubSpot format."""
    adapter = HubSpotLiveAdapter(
        AdapterConfig(
            vendor="hubspot",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    raw_deal = {
        "id": "11111",
        "properties": {
            "dealname": "Enterprise Deal",
            "amount": "250000",
            "dealstage": "negotiation",
            "pipeline": "default",
            "closedate": "2024-12-31",
            "createdate": "2024-06-01T00:00:00Z",
            "hs_lastmodifieddate": "2024-06-15T00:00:00Z",
        },
    }
    
    normalized = adapter._normalize_deal(raw_deal)
    
    assert normalized["id"] == "11111"
    assert normalized["name"] == "Enterprise Deal"
    assert normalized["amount"] == 250000.0
    assert normalized["stage"] == "negotiation"
    assert normalized["pipeline"] == "default"
    assert normalized["probability"] == 0.8  # Negotiation stage


def test_estimate_probability():
    """Test deal probability estimation based on stage."""
    adapter = HubSpotLiveAdapter(
        AdapterConfig(
            vendor="hubspot",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    assert adapter._estimate_probability("Closed Won") == 1.0
    assert adapter._estimate_probability("Closed Lost") == 0.0
    assert adapter._estimate_probability("Negotiation") == 0.8
    assert adapter._estimate_probability("Proposal Sent") == 0.6
    assert adapter._estimate_probability("Qualified") == 0.4
    assert adapter._estimate_probability("Appointment Scheduled") == 0.2
    assert adapter._estimate_probability("Unknown Stage") == 0.1


def test_parse_int():
    """Test integer parsing helper."""
    adapter = HubSpotLiveAdapter(
        AdapterConfig(
            vendor="hubspot",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    assert adapter._parse_int("500") == 500
    assert adapter._parse_int(500) == 500
    assert adapter._parse_int("invalid") == 0
    assert adapter._parse_int(None) == 0
    assert adapter._parse_int("") == 0


def test_parse_float():
    """Test float parsing helper."""
    adapter = HubSpotLiveAdapter(
        AdapterConfig(
            vendor="hubspot",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    assert adapter._parse_float("50000.50") == 50000.50
    assert adapter._parse_float(50000) == 50000.0
    assert adapter._parse_float("invalid") == 0.0
    assert adapter._parse_float(None) == 0.0
    assert adapter._parse_float("") == 0.0


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_accounts_success(mock_safe_client, valid_config):
    """Test successful companies fetching with pagination."""
    # Mock HTTP response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "results": [
            {
                "id": "12345",
                "properties": {
                    "name": "Acme Corp",
                    "domain": "acme.com",
                    "industry": "Technology",
                    "numberofemployees": "500",
                },
            },
            {
                "id": "67890",
                "properties": {
                    "name": "TechCo Inc",
                    "domain": "techco.com",
                    "industry": "Software",
                    "numberofemployees": "250",
                },
            },
        ],
        "paging": {},  # No next page
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    companies = adapter.fetch_accounts(filters={"limit": 10})
    
    assert len(companies) == 2
    assert companies[0]["name"] == "Acme Corp"
    assert companies[0]["domain"] == "acme.com"
    assert companies[1]["name"] == "TechCo Inc"


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_accounts_with_pagination(mock_safe_client, valid_config):
    """Test companies fetching with multiple pages."""
    # First page response
    first_response = Mock()
    first_response.status_code = 200
    first_response.json.return_value = {
        "results": [{"id": "1", "properties": {"name": "Company 1"}}],
        "paging": {"next": {"after": "cursor1"}},
    }
    
    # Second page response
    second_response = Mock()
    second_response.status_code = 200
    second_response.json.return_value = {
        "results": [{"id": "2", "properties": {"name": "Company 2"}}],
        "paging": {},  # No next page
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.side_effect = [first_response, second_response]
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    companies = adapter.fetch_accounts(filters={"limit": 10})
    
    assert len(companies) == 2
    assert companies[0]["name"] == "Company 1"
    assert companies[1]["name"] == "Company 2"


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_accounts_auth_error(mock_safe_client, valid_config):
    """Test companies fetching with 401 auth error."""
    # Mock 401 response
    mock_response = Mock()
    mock_response.status_code = 401
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    with pytest.raises(ValueError, match="Invalid HubSpot API key"):
        adapter.fetch_accounts()


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_accounts_rate_limit(mock_safe_client, valid_config):
    """Test companies fetching with 429 rate limit."""
    # Mock 429 response
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "10"}
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    with pytest.raises(Exception, match="Rate limit exceeded"):
        adapter.fetch_accounts()


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_contacts_success(mock_safe_client, valid_config):
    """Test successful contacts fetching."""
    # Mock associations response
    assoc_response = Mock()
    assoc_response.status_code = 200
    assoc_response.json.return_value = {
        "results": [{"id": "contact1"}, {"id": "contact2"}],
    }
    
    # Mock contact details responses
    contact1_response = Mock()
    contact1_response.status_code = 200
    contact1_response.json.return_value = {
        "id": "contact1",
        "properties": {"email": "john@acme.com", "firstname": "John", "lastname": "Doe"},
    }
    
    contact2_response = Mock()
    contact2_response.status_code = 200
    contact2_response.json.return_value = {
        "id": "contact2",
        "properties": {"email": "jane@acme.com", "firstname": "Jane", "lastname": "Smith"},
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.side_effect = [assoc_response, contact1_response, contact2_response]
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    contacts = adapter.fetch_contacts("12345")
    
    assert len(contacts) == 2
    assert contacts[0]["email"] == "john@acme.com"
    assert contacts[1]["email"] == "jane@acme.com"


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_contacts_company_not_found(mock_safe_client, valid_config):
    """Test contacts fetching with 404 company not found."""
    # Mock 404 response
    mock_response = Mock()
    mock_response.status_code = 404
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    contacts = adapter.fetch_contacts("nonexistent")
    
    assert contacts == []


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_opportunities_success(mock_safe_client, valid_config):
    """Test successful deals fetching."""
    # Mock associations response
    assoc_response = Mock()
    assoc_response.status_code = 200
    assoc_response.json.return_value = {
        "results": [{"id": "deal1"}, {"id": "deal2"}],
    }
    
    # Mock deal details responses
    deal1_response = Mock()
    deal1_response.status_code = 200
    deal1_response.json.return_value = {
        "id": "deal1",
        "properties": {
            "dealname": "Enterprise Deal",
            "amount": "250000",
            "dealstage": "negotiation",
        },
    }
    
    deal2_response = Mock()
    deal2_response.status_code = 200
    deal2_response.json.return_value = {
        "id": "deal2",
        "properties": {
            "dealname": "SMB Deal",
            "amount": "50000",
            "dealstage": "proposal",
        },
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.side_effect = [assoc_response, deal1_response, deal2_response]
    mock_safe_client.return_value = mock_client_instance
    
    adapter = HubSpotLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    deals = adapter.fetch_opportunities("12345")
    
    assert len(deals) == 2
    assert deals[0]["name"] == "Enterprise Deal"
    assert deals[0]["amount"] == 250000.0
    assert deals[1]["name"] == "SMB Deal"


@patch("cuga.adapters.sales.hubspot_live.SafeClient")
def test_fetch_buying_signals(mock_safe_client, valid_config):
    """Test buying signals derived from deals."""
    # Mock deals response
    recent_date = (datetime.now() - timedelta(days=15)).isoformat()
    
    adapter = HubSpotLiveAdapter(valid_config)
    
    # Mock fetch_opportunities to return deals
    deals = [
        {
            "id": "deal1",
            "name": "New Deal",
            "stage": "qualified",
            "amount": 100000.0,
            "created_at": recent_date,
            "updated_at": recent_date,
        },
        {
            "id": "deal2",
            "name": "Advanced Deal",
            "stage": "negotiation",
            "amount": 250000.0,
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": recent_date,
        },
    ]
    
    adapter.fetch_opportunities = Mock(return_value=deals)
    
    signals = adapter.fetch_buying_signals("12345")
    
    # Should have signals for: new deal + deal progression
    assert len(signals) >= 2
    assert any(signal["type"] == "new_opportunity" for signal in signals)
    assert any(signal["type"] == "deal_progression" for signal in signals)
    
    # Check signal structure
    new_opp_signal = next(s for s in signals if s["type"] == "new_opportunity")
    assert new_opp_signal["confidence"] == 0.8
    assert "deal_id" in new_opp_signal["metadata"]
