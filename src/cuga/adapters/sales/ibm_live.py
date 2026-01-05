#!/usr/bin/env python3
"""
IBM Sales Cloud Live Adapter - Production Implementation

Implements live API integration for IBM Sales Cloud with:
- OAuth 2.0 authentication
- SafeClient (AGENTS.md compliant)
- Rate limiting and retry logic
- Schema normalization
- Observability integration
"""

import os
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import httpx

from cuga.security.http_client import SafeClient
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig


class IBMLiveAdapter(VendorAdapter):
    """
    Live adapter for IBM Sales Cloud API.
    
    Environment Variables Required:
        SALES_IBM_API_ENDPOINT - API base URL
        SALES_IBM_API_KEY - API key for authentication
        SALES_IBM_TENANT_ID - Tenant/organization ID
        SALES_IBM_OAUTH_CLIENT_ID - OAuth client ID (optional)
        SALES_IBM_OAUTH_CLIENT_SECRET - OAuth client secret (optional)
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize IBM Sales Cloud adapter."""
        self.config = config
        self.trace_id = config.trace_id
        
        # Validate required credentials
        self._validate_config()
        
        # Initialize SafeClient (AGENTS.md compliant)
        self.client = SafeClient(
            base_url=config.credentials["api_endpoint"],
            headers={
                "Authorization": f"Bearer {config.credentials['api_key']}",
                "X-Tenant-ID": config.credentials["tenant_id"],
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(
                connect=5.0,
                read=10.0,
                write=10.0,
                pool=10.0
            )
        )
        
        # Cache for OAuth token (if using OAuth)
        self._oauth_token = None
        self._token_expiry = None
    
    def _validate_config(self):
        """Validate required configuration fields."""
        required = ["api_endpoint", "api_key", "tenant_id"]
        missing = [k for k in required if k not in self.config.credentials]
        
        if missing:
            raise ValueError(
                f"Missing required IBM Sales Cloud credentials: {missing}\n"
                f"Required environment variables:\n"
                f"  - SALES_IBM_API_ENDPOINT\n"
                f"  - SALES_IBM_API_KEY\n"
                f"  - SALES_IBM_TENANT_ID\n"
                f"Set adapter mode: SALES_IBM_ADAPTER_MODE=live"
            )
    
    def _ensure_auth(self):
        """Ensure OAuth token is valid (if using OAuth)."""
        if "oauth_client_id" not in self.config.credentials:
            return  # Using API key only
        
        # Check if token needs refresh
        if self._oauth_token and self._token_expiry:
            if datetime.now() < self._token_expiry:
                return  # Token still valid
        
        # Refresh OAuth token
        try:
            response = self.client.post(
                "/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": self.config.credentials["oauth_client_id"],
                    "client_secret": self.config.credentials["oauth_client_secret"],
                }
            )
            
            token_data = response.json()
            self._oauth_token = token_data["access_token"]
            expires_in = token_data.get("expires_in", 3600)
            self._token_expiry = datetime.now() + timedelta(seconds=expires_in - 60)
            
            # Update client headers
            self.client.headers["Authorization"] = f"Bearer {self._oauth_token}"
            
        except Exception as e:
            self._emit_event("oauth_refresh_failed", {"error": str(e)})
            raise
    
    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
        """
        Fetch accounts from IBM Sales Cloud API.
        
        Args:
            filters: Optional filters (industry, revenue_min, territory, etc.)
        
        Returns:
            List of normalized account records
        """
        self._ensure_auth()
        
        start_time = datetime.now()
        filters = filters or {}
        
        try:
            self._emit_event("adapter_fetch_start", {
                "vendor": "ibm_sales_cloud",
                "resource": "accounts",
                "filters": filters,
            })
            
            # Build query parameters
            params = {
                "limit": filters.get("limit", 100),
                "offset": filters.get("offset", 0),
            }
            
            if filters.get("industry"):
                params["industry"] = filters["industry"]
            if filters.get("territory"):
                params["territory"] = filters["territory"]
            if filters.get("revenue_min"):
                params["revenue_min"] = filters["revenue_min"]
            
            # Call IBM API
            response = self.client.get("/v1/accounts", params=params)
            response.raise_for_status()
            
            raw_accounts = response.json().get("accounts", [])
            
            # Normalize to canonical schema
            normalized = self._normalize_accounts(raw_accounts)
            
            duration = (datetime.now() - start_time).total_seconds() * 1000
            
            self._emit_event("adapter_fetch_complete", {
                "vendor": "ibm_sales_cloud",
                "resource": "accounts",
                "record_count": len(normalized),
                "duration_ms": duration,
                "mode": "live",
            })
            
            return normalized
            
        except httpx.TimeoutException as e:
            self._emit_event("adapter_timeout", {
                "vendor": "ibm_sales_cloud",
                "resource": "accounts",
                "error": str(e),
            })
            raise
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limit hit
                retry_after = e.response.headers.get("Retry-After", 60)
                self._emit_event("adapter_rate_limit", {
                    "vendor": "ibm_sales_cloud",
                    "retry_after": retry_after,
                })
            
            self._emit_event("adapter_http_error", {
                "vendor": "ibm_sales_cloud",
                "status_code": e.response.status_code,
                "error": str(e),
            })
            raise
        
        except Exception as e:
            self._emit_event("adapter_error", {
                "vendor": "ibm_sales_cloud",
                "resource": "accounts",
                "error": str(e),
            })
            raise
    
    def fetch_contacts(self, filters: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
        """Fetch contacts from IBM Sales Cloud."""
        self._ensure_auth()
        
        filters = filters or {}
        params = {
            "limit": filters.get("limit", 100),
            "offset": filters.get("offset", 0),
        }
        
        if filters.get("account_id"):
            params["account_id"] = filters["account_id"]
        
        response = self.client.get("/v1/contacts", params=params)
        response.raise_for_status()
        
        raw_contacts = response.json().get("contacts", [])
        return self._normalize_contacts(raw_contacts)
    
    def fetch_opportunities(self, filters: Optional[Dict[str, Any]] = None) -> list[Dict[str, Any]]:
        """Fetch opportunities from IBM Sales Cloud."""
        self._ensure_auth()
        
        filters = filters or {}
        params = {
            "limit": filters.get("limit", 100),
            "offset": filters.get("offset", 0),
        }
        
        if filters.get("account_id"):
            params["account_id"] = filters["account_id"]
        if filters.get("stage"):
            params["stage"] = filters["stage"]
        
        response = self.client.get("/v1/opportunities", params=params)
        response.raise_for_status()
        
        raw_opps = response.json().get("opportunities", [])
        return self._normalize_opportunities(raw_opps)
    
    def fetch_buying_signals(self, account_id: str) -> list[Dict[str, Any]]:
        """
        Fetch buying signals for specific account.
        
        Signal types:
        - funding_event: New funding round announced
        - leadership_change: C-level hire/departure
        - product_launch: New product announced
        - tech_adoption: New technology detected
        - hiring_spree: Significant job posting increase
        """
        self._ensure_auth()
        
        response = self.client.get(f"/v1/accounts/{account_id}/signals")
        response.raise_for_status()
        
        raw_signals = response.json().get("signals", [])
        return self._normalize_signals(raw_signals)
    
    def get_mode(self) -> AdapterMode:
        """Return adapter mode."""
        return self.config.mode
    
    def validate_connection(self) -> bool:
        """Test API connection and credentials."""
        try:
            self._ensure_auth()
            
            # Test with minimal query
            response = self.client.get("/v1/health")
            return response.status_code == 200
            
        except Exception as e:
            self._emit_event("connection_validation_failed", {
                "vendor": "ibm_sales_cloud",
                "error": str(e),
            })
            return False
    
    # Schema Normalization Methods
    
    def _normalize_accounts(self, raw_accounts: list) -> list[Dict[str, Any]]:
        """Map IBM account fields to canonical schema."""
        normalized = []
        
        for account in raw_accounts:
            normalized.append({
                "id": account.get("id"),
                "name": account.get("name"),
                "industry": account.get("industry"),
                "employee_count": account.get("employeeCount"),
                "annual_revenue": account.get("annualRevenue"),
                "territory": account.get("territory"),
                "country": account.get("country"),
                "state": account.get("state"),
                "icp_score": account.get("icpScore", 0.0),
                "engagement_level": account.get("engagementLevel", "cold"),
                "last_contact_date": account.get("lastContactDate"),
                "owner": account.get("owner", {}).get("name"),
                "owner_id": account.get("owner", {}).get("id"),
            })
        
        return normalized
    
    def _normalize_contacts(self, raw_contacts: list) -> list[Dict[str, Any]]:
        """Map IBM contact fields to canonical schema."""
        normalized = []
        
        for contact in raw_contacts:
            normalized.append({
                "id": contact.get("id"),
                "first_name": contact.get("firstName"),
                "last_name": contact.get("lastName"),
                "email": contact.get("email"),
                "phone": contact.get("phone"),
                "title": contact.get("title"),
                "account_id": contact.get("accountId"),
                "account_name": contact.get("accountName"),
                "is_decision_maker": contact.get("isDecisionMaker", False),
                "engagement_score": contact.get("engagementScore", 0.0),
            })
        
        return normalized
    
    def _normalize_opportunities(self, raw_opps: list) -> list[Dict[str, Any]]:
        """Map IBM opportunity fields to canonical schema."""
        normalized = []
        
        for opp in raw_opps:
            normalized.append({
                "id": opp.get("id"),
                "name": opp.get("name"),
                "account_id": opp.get("accountId"),
                "account_name": opp.get("accountName"),
                "stage": opp.get("stage"),
                "value": opp.get("value"),
                "currency": opp.get("currency", "USD"),
                "close_date": opp.get("closeDate"),
                "probability": opp.get("probability", 0),
                "owner": opp.get("owner", {}).get("name"),
                "owner_id": opp.get("owner", {}).get("id"),
                "created_date": opp.get("createdDate"),
            })
        
        return normalized
    
    def _normalize_signals(self, raw_signals: list) -> list[Dict[str, Any]]:
        """Map IBM signal fields to canonical schema."""
        normalized = []
        
        for signal in raw_signals:
            normalized.append({
                "type": signal.get("type"),
                "timestamp": signal.get("timestamp"),
                "confidence": signal.get("confidence", 0.0),
                "details": signal.get("details"),
                "source": signal.get("source", "ibm_sales_cloud"),
                "url": signal.get("url"),
            })
        
        return normalized
    
    def _emit_event(self, event_type: str, metadata: Dict[str, Any]):
        """Emit observability event."""
        try:
            from cuga.observability import emit_event
            from cuga.observability.events import StructuredEvent, EventType
            
            emit_event(StructuredEvent(
                event_type=EventType.TOOL_CALL_COMPLETE if "complete" in event_type else EventType.TOOL_CALL_ERROR,
                trace_id=self.trace_id or "unknown",
                attributes={
                    **metadata,
                    "trace_id": self.trace_id,
                }
            ))
        except ImportError:
            pass  # Observability not available
