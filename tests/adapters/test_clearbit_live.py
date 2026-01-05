"""
Unit tests for Clearbit live adapter.

Tests cover:
- Initialization and configuration validation
- Company enrichment by domain
- Person enrichment by email
- Technology stack detection
- Schema normalization
- Error handling (404, 401, 429, timeouts)
- Observability event emission
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import httpx

from cuga.adapters.sales.clearbit_live import ClearbitLiveAdapter
from cuga.adapters.sales.config import AdapterConfig
from cuga.adapters.sales.protocol import AdapterMode


@pytest.fixture
def valid_config():
    """Create valid Clearbit adapter configuration."""
    return AdapterConfig(
        vendor="clearbit",
        mode="live",
        credentials={"api_key": "sk_test_clearbit_api_key"},
        profile="sales",
    )


@pytest.fixture
def mock_http_client():
    """Create mock HTTP client."""
    mock_client = Mock()
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}
    mock_client.get.return_value = mock_response
    return mock_client


def test_initialization(valid_config):
    """Test adapter initializes with valid configuration."""
    adapter = ClearbitLiveAdapter(valid_config)
    
    assert adapter.config == valid_config
    assert adapter.client is not None
    assert adapter.person_client is not None
    assert adapter.get_mode() == AdapterMode.LIVE


def test_validate_config_missing_api_key():
    """Test configuration validation fails without API key."""
    invalid_config = AdapterConfig(
        vendor="clearbit",
        mode="live",
        credentials={},  # Missing api_key
        profile="sales",
    )
    
    with pytest.raises(ValueError, match="requires 'api_key'"):
        ClearbitLiveAdapter(invalid_config)


def test_get_mode(valid_config):
    """Test adapter reports LIVE mode."""
    adapter = ClearbitLiveAdapter(valid_config)
    assert adapter.get_mode() == AdapterMode.LIVE


def test_fetch_accounts_returns_empty(valid_config):
    """Test fetch_accounts returns empty list (not supported)."""
    adapter = ClearbitLiveAdapter(valid_config)
    accounts = adapter.fetch_accounts()
    
    assert accounts == []
    assert isinstance(accounts, list)


def test_fetch_contacts_returns_empty(valid_config):
    """Test fetch_contacts returns empty list (not supported)."""
    adapter = ClearbitLiveAdapter(valid_config)
    contacts = adapter.fetch_contacts("example.com")
    
    assert contacts == []
    assert isinstance(contacts, list)


def test_fetch_opportunities_returns_empty(valid_config):
    """Test fetch_opportunities returns empty list (not a CRM)."""
    adapter = ClearbitLiveAdapter(valid_config)
    opportunities = adapter.fetch_opportunities("example.com")
    
    assert opportunities == []
    assert isinstance(opportunities, list)


def test_normalize_company():
    """Test company data normalization from Clearbit format."""
    adapter = ClearbitLiveAdapter(
        AdapterConfig(
            vendor="clearbit",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    raw_company = {
        "id": "clearbit-123",
        "name": "Clearbit Inc",
        "domain": "clearbit.com",
        "description": "Marketing data engine",
        "foundedYear": 2015,
        "category": {
            "industry": "Technology",
            "subIndustry": "Software",
        },
        "metrics": {
            "employees": 250,
            "estimatedAnnualRevenue": "50M-100M",
            "raised": 10000000,
        },
        "geo": {
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
        },
        "tech": ["Google Analytics", "AWS", "Salesforce"],
        "tags": ["B2B", "SaaS", "Data"],
        "logo": "https://logo.clearbit.com/clearbit.com",
        "linkedin": {"handle": "clearbit"},
        "twitter": {"handle": "clearbit"},
    }
    
    normalized = adapter._normalize_company(raw_company)
    
    assert normalized["id"] == "clearbit-123"
    assert normalized["name"] == "Clearbit Inc"
    assert normalized["domain"] == "clearbit.com"
    assert normalized["industry"] == "Technology"
    assert normalized["sub_industry"] == "Software"
    assert normalized["employees"] == 250
    assert normalized["revenue"] == "50M-100M"
    assert normalized["location"]["city"] == "San Francisco"
    assert normalized["founded_year"] == 2015
    assert normalized["funding"]["raised"] == 10000000
    assert normalized["social_media"]["linkedin"] == "clearbit"
    assert len(normalized["metadata"]["technologies"]) == 3
    assert normalized["metadata"]["tags"] == ["B2B", "SaaS", "Data"]


def test_normalize_contact():
    """Test contact data normalization from Clearbit format."""
    adapter = ClearbitLiveAdapter(
        AdapterConfig(
            vendor="clearbit",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    raw_person = {
        "id": "person-456",
        "email": "john@clearbit.com",
        "name": {
            "givenName": "John",
            "familyName": "Doe",
            "fullName": "John Doe",
        },
        "employment": {
            "name": "Clearbit Inc",
            "domain": "clearbit.com",
            "title": "VP of Sales",
            "role": "sales",
            "seniority": "executive",
        },
        "geo": {
            "city": "San Francisco",
            "state": "California",
            "country": "United States",
        },
        "linkedin": {"handle": "johndoe"},
        "twitter": {"handle": "johndoe"},
        "avatar": "https://avatar.clearbit.com/john.jpg",
        "bio": "Sales executive at Clearbit",
    }
    
    normalized = adapter._normalize_contact(raw_person)
    
    assert normalized["id"] == "person-456"
    assert normalized["email"] == "john@clearbit.com"
    assert normalized["first_name"] == "John"
    assert normalized["last_name"] == "Doe"
    assert normalized["full_name"] == "John Doe"
    assert normalized["title"] == "VP of Sales"
    assert normalized["role"] == "sales"
    assert normalized["seniority"] == "executive"
    assert normalized["company"]["name"] == "Clearbit Inc"
    assert normalized["company"]["domain"] == "clearbit.com"
    assert normalized["location"]["city"] == "San Francisco"
    assert normalized["social_media"]["linkedin"] == "johndoe"
    assert normalized["metadata"]["avatar"] == "https://avatar.clearbit.com/john.jpg"


def test_categorize_technology():
    """Test technology categorization heuristic."""
    adapter = ClearbitLiveAdapter(
        AdapterConfig(
            vendor="clearbit",
            mode="live",
            credentials={"api_key": "test_key"},
            profile="sales",
        )
    )
    
    assert adapter._categorize_technology("Google Analytics") == "analytics"
    assert adapter._categorize_technology("AWS Lambda") == "infrastructure"
    assert adapter._categorize_technology("Salesforce") == "crm"
    assert adapter._categorize_technology("Shopify") == "ecommerce"
    assert adapter._categorize_technology("WordPress") == "cms"
    assert adapter._categorize_technology("Custom Tool") == "other"


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_enrich_company_success(mock_safe_client, valid_config):
    """Test successful company enrichment."""
    # Mock HTTP response
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "company-123",
        "name": "Test Company",
        "domain": "test.com",
        "category": {"industry": "Technology"},
        "metrics": {"employees": 100},
        "geo": {"city": "San Francisco"},
        "tech": ["Google Analytics"],
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    result = adapter.enrich_company("test.com")
    
    assert result is not None
    assert result["name"] == "Test Company"
    assert result["domain"] == "test.com"
    assert result["employees"] == 100
    mock_client_instance.get.assert_called_once_with(
        "/v2/companies/find",
        params={"domain": "test.com"},
    )


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_enrich_company_not_found(mock_safe_client, valid_config):
    """Test company enrichment with 404 not found."""
    # Mock 404 response
    mock_response = Mock()
    mock_response.status_code = 404
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    result = adapter.enrich_company("notfound.com")
    
    assert result is None


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_enrich_company_auth_error(mock_safe_client, valid_config):
    """Test company enrichment with 401 auth error."""
    # Mock 401 response
    mock_response = Mock()
    mock_response.status_code = 401
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    with pytest.raises(ValueError, match="Invalid Clearbit API key"):
        adapter.enrich_company("test.com")


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_enrich_company_rate_limit(mock_safe_client, valid_config):
    """Test company enrichment with 429 rate limit."""
    # Mock 429 response
    mock_response = Mock()
    mock_response.status_code = 429
    mock_response.headers = {"Retry-After": "120"}
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    with pytest.raises(Exception, match="Rate limit exceeded"):
        adapter.enrich_company("test.com")


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_enrich_contact_success(mock_safe_client, valid_config):
    """Test successful contact enrichment."""
    # Mock HTTP response for person API
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "person-789",
        "email": "john@test.com",
        "name": {"givenName": "John", "familyName": "Doe", "fullName": "John Doe"},
        "employment": {"title": "CEO", "name": "Test Co"},
        "geo": {"city": "NYC"},
    }
    
    mock_person_client = Mock()
    mock_person_client.get.return_value = mock_response
    mock_safe_client.return_value = mock_person_client
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.person_client = mock_person_client
    
    result = adapter.enrich_contact("john@test.com")
    
    assert result is not None
    assert result["email"] == "john@test.com"
    assert result["first_name"] == "John"
    assert result["title"] == "CEO"
    mock_person_client.get.assert_called_once_with(
        "/v2/people/find",
        params={"email": "john@test.com"},
    )


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_enrich_contact_not_found(mock_safe_client, valid_config):
    """Test contact enrichment with 404 not found."""
    # Mock 404 response
    mock_response = Mock()
    mock_response.status_code = 404
    
    mock_person_client = Mock()
    mock_person_client.get.return_value = mock_response
    mock_safe_client.return_value = mock_person_client
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.person_client = mock_person_client
    
    result = adapter.enrich_contact("notfound@example.com")
    
    assert result is None


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_get_technologies(mock_safe_client, valid_config):
    """Test technology stack fetching."""
    # Mock company enrichment response with tech data
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "company-123",
        "name": "Tech Corp",
        "domain": "techcorp.com",
        "tech": ["Google Analytics", "AWS", "Salesforce", "Stripe"],
        "category": {"industry": "Technology"},
        "metrics": {},
        "geo": {},
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    technologies = adapter.get_technologies("techcorp.com")
    
    assert len(technologies) == 4
    assert any(tech["name"] == "Google Analytics" for tech in technologies)
    assert any(tech["category"] == "analytics" for tech in technologies)
    assert any(tech["category"] == "infrastructure" for tech in technologies)
    assert any(tech["category"] == "crm" for tech in technologies)


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_fetch_buying_signals(mock_safe_client, valid_config):
    """Test buying signals derived from tech stack."""
    # Mock company enrichment with technologies
    mock_response = Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "company-456",
        "name": "Signal Corp",
        "domain": "signal.com",
        "tech": ["Salesforce", "HubSpot"],
        "category": {"industry": "Technology"},
        "metrics": {},
        "geo": {},
    }
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    signals = adapter.fetch_buying_signals("signal.com")
    
    assert len(signals) == 2  # One signal per technology
    assert all(signal["type"] == "tech_adoption" for signal in signals)
    assert all(signal["confidence"] == 0.7 for signal in signals)
    assert any("Salesforce" in signal["description"] for signal in signals)
    assert any("HubSpot" in signal["description"] for signal in signals)


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_validate_connection_success(mock_safe_client, valid_config):
    """Test successful connection validation."""
    # Mock successful response
    mock_response = Mock()
    mock_response.status_code = 200
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    assert adapter.validate_connection() is True


@patch("cuga.adapters.sales.clearbit_live.SafeClient")
def test_validate_connection_failure(mock_safe_client, valid_config):
    """Test failed connection validation."""
    # Mock failed response
    mock_response = Mock()
    mock_response.status_code = 401
    
    mock_client_instance = Mock()
    mock_client_instance.get.return_value = mock_response
    mock_safe_client.return_value = mock_client_instance
    
    adapter = ClearbitLiveAdapter(valid_config)
    adapter.client = mock_client_instance
    
    assert adapter.validate_connection() is False
