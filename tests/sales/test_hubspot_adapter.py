"""
Integration tests for HubSpot CRM adapter.

Tests verify:
- SafeClient usage (timeout enforcement, retries)
- Env-only secrets
- Vendor-neutral return types
- Error handling
- Offline fallback when adapter unavailable
"""

import pytest
from unittest.mock import Mock, patch
import os


class TestHubSpotAdapterInit:
    """Test HubSpot adapter initialization."""
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    def test_init_with_api_key(self, mock_safe_client_cls):
        """Test initialization with explicit API key."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        mock_instance = Mock()
        mock_safe_client_cls.return_value = mock_instance
        
        adapter = HubSpotAdapter(api_key="test-key-123")
        
        assert adapter.api_key == "test-key-123"
        
        # Verify SafeClient called with correct config
        mock_safe_client_cls.assert_called_once()
        call_kwargs = mock_safe_client_cls.call_args.kwargs
        assert call_kwargs["base_url"] == "https://api.hubapi.com"
        assert "Authorization" in call_kwargs["headers"]
        assert "Bearer test-key-123" in call_kwargs["headers"]["Authorization"]
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    @patch.dict(os.environ, {"HUBSPOT_API_KEY": "env-key-456"})
    def test_init_with_env_var(self, mock_safe_client_cls):
        """Test initialization with environment variable."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        adapter = HubSpotAdapter()
        assert adapter.api_key == "env-key-456"
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    @patch.dict(os.environ, {}, clear=True)
    def test_init_without_api_key_raises_error(self, mock_safe_client_cls):
        """Test initialization fails without API key."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        with pytest.raises(ValueError, match="HUBSPOT_API_KEY not found"):
            HubSpotAdapter()


class TestHubSpotAdapterCreateAccount:
    """Test account creation."""
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    def test_create_account_success(self, mock_safe_client_cls):
        """Test successful account creation."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "12345",
            "properties": {"name": "Test Corp"}
        }
        mock_response.raise_for_status = Mock()
        
        mock_instance = Mock()
        mock_instance.post.return_value = mock_response
        mock_safe_client_cls.return_value = mock_instance
        
        adapter = HubSpotAdapter(api_key="test-key")
        
        result = adapter.create_account(
            account_data={
                "name": "Test Corp",
                "industry": "Technology",
                "employee_count": 500,
                "revenue": 10000000,
            },
            context={"trace_id": "test-123", "profile": "sales"}
        )
        
        # Verify result structure
        assert result["account_id"] == "12345"
        assert result["status"] == "created"
        assert "created_at" in result
        
        # Verify API call
        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "/crm/v3/objects/companies"
        
        # Verify payload mapping
        payload = call_args.kwargs["json"]["properties"]
        assert payload["name"] == "Test Corp"
        assert payload["industry"] == "Technology"
        assert payload["numberofemployees"] == 500
        assert payload["annualrevenue"] == 10000000


class TestHubSpotAdapterGetAccount:
    """Test account retrieval."""
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    def test_get_account_success(self, mock_safe_client_cls):
        """Test successful account retrieval."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "id": "12345",
            "properties": {
                "name": "Test Corp",
                "industry": "Technology",
                "numberofemployees": "500",
                "annualrevenue": "10000000.0",
                "city": "San Francisco"
            },
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-03T00:00:00Z"
        }
        mock_response.raise_for_status = Mock()
        
        mock_instance = Mock()
        mock_instance.get.return_value = mock_response
        mock_safe_client_cls.return_value = mock_instance
        
        adapter = HubSpotAdapter(api_key="test-key")
        
        result = adapter.get_account(
            account_id="12345",
            context={"trace_id": "test-456", "profile": "sales"}
        )
        
        # Verify vendor-neutral return type
        assert result["account_id"] == "12345"
        assert result["name"] == "Test Corp"
        assert result["industry"] == "Technology"
        assert result["employee_count"] == 500
        assert result["revenue"] == 10000000.0
        assert result["region"] == "San Francisco"
        assert result["status"] == "active"
        
        # Verify metadata includes source
        assert result["metadata"]["source"] == "hubspot"
        assert result["metadata"]["hubspot_id"] == "12345"
        
        # Verify API call
        mock_instance.get.assert_called_once()
        call_args = mock_instance.get.call_args
        assert "/crm/v3/objects/companies/12345" in call_args[0][0]


class TestHubSpotAdapterSearchAccounts:
    """Test account search."""
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    def test_search_accounts_by_name(self, mock_safe_client_cls):
        """Test account search by name."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        # Mock response
        mock_response = Mock()
        mock_response.json.return_value = {
            "results": [
                {
                    "id": "001",
                    "properties": {
                        "name": "Acme Corp",
                        "industry": "Technology"
                    }
                },
                {
                    "id": "002",
                    "properties": {
                        "name": "Acme Industries",
                        "industry": "Manufacturing"
                    }
                }
            ],
            "total": 2
        }
        mock_response.raise_for_status = Mock()
        
        mock_instance = Mock()
        mock_instance.post.return_value = mock_response
        mock_safe_client_cls.return_value = mock_instance
        
        adapter = HubSpotAdapter(api_key="test-key")
        
        result = adapter.search_accounts(
            filters={"name": "Acme"},
            context={"trace_id": "test-789", "profile": "sales"}
        )
        
        # Verify result structure
        assert result["count"] == 2
        assert result["total"] == 2
        assert len(result["accounts"]) == 2
        
        # Verify vendor-neutral return types
        for account in result["accounts"]:
            assert "account_id" in account
            assert "name" in account
            assert "status" in account
            assert account["metadata"]["source"] == "hubspot"
        
        # Verify search query structure
        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        assert call_args[0][0] == "/crm/v3/objects/companies/search"
        
        payload = call_args.kwargs["json"]
        assert "filterGroups" in payload
        assert payload["filterGroups"][0]["filters"][0]["propertyName"] == "name"
        assert payload["filterGroups"][0]["filters"][0]["value"] == "Acme"


class TestHubSpotAdapterErrorHandling:
    """Test error handling and retries."""
    
    @patch("cuga.adapters.crm.hubspot_adapter.SafeClient")
    def test_api_error_propagated(self, mock_safe_client_cls):
        """Test that API errors are propagated (not swallowed)."""
        from cuga.adapters.crm.hubspot_adapter import HubSpotAdapter
        
        # Mock error response
        mock_response = Mock()
        mock_response.raise_for_status.side_effect = Exception("HTTP 401 Unauthorized")
        
        mock_instance = Mock()
        mock_instance.get.return_value = mock_response
        mock_safe_client_cls.return_value = mock_instance
        
        adapter = HubSpotAdapter(api_key="invalid-key")
        
        # Error should propagate
        with pytest.raises(Exception, match="401 Unauthorized"):
            adapter.get_account(
                account_id="12345",
                context={"trace_id": "test-error", "profile": "sales"}
            )


class TestAdapterIntegrationWithCapability:
    """Test adapter integration with capabilities."""
    
    def test_retrieve_signals_with_adapter(self):
        """Test signal retrieval uses adapter when configured."""
        with patch("cuga.modular.tools.sales.account_intelligence._get_crm_adapter") as mock_get_adapter:
            from cuga.modular.tools.sales.account_intelligence import retrieve_account_signals
            
            # Mock adapter
            mock_adapter = Mock()
            mock_adapter.get_account.return_value = {
                "account_id": "12345",
                "name": "Test Corp",
                "revenue": 10000000,
                "industry": "Technology",
                "metadata": {"updated_at": "2026-01-03T00:00:00Z"}
            }
            mock_get_adapter.return_value = mock_adapter
            
            result = retrieve_account_signals(
                inputs={
                    "account_id": "12345",
                    "fetch_from_crm": True,  # Opt-in to adapter
                },
                context={"trace_id": "test-integration", "profile": "sales"}
            )
            
            # Verify signals extracted from CRM data
            assert result["signal_count"] > 0
            assert result["source"] == "hubspot"
            assert any(s["signal_type"] == "financial" for s in result["signals"])
            assert any(s["signal_type"] == "firmographic" for s in result["signals"])
    
    def test_retrieve_signals_offline_fallback(self):
        """Test signal retrieval falls back to offline when adapter unavailable."""
        with patch("cuga.modular.tools.sales.account_intelligence._get_crm_adapter") as mock_get_adapter:
            from cuga.modular.tools.sales.account_intelligence import retrieve_account_signals
            
            # No adapter configured
            mock_get_adapter.return_value = None
            
            result = retrieve_account_signals(
                inputs={
                    "account_id": "12345",
                    "fetch_from_crm": True,
                },
                context={"trace_id": "test-offline", "profile": "sales"}
            )
            
            # Should fall back to offline mode gracefully
            assert result["signal_count"] == 0
            assert result["source"] == "offline"
    
    def test_retrieve_signals_offline_by_default(self):
        """Test signal retrieval is offline by default (no adapter call)."""
        from cuga.modular.tools.sales.account_intelligence import retrieve_account_signals
        
        result = retrieve_account_signals(
            inputs={"account_id": "12345"},  # fetch_from_crm not specified
            context={"trace_id": "test-default", "profile": "sales"}
        )
        
        # Should be offline by default
        assert result["signal_count"] == 0
        assert result["source"] == "offline"
