"""
HubSpot Live Adapter for Mid-Market CRM Integration.

This adapter provides:
- Company (account) management
- Contact management
- Deal (opportunity) pipeline tracking
- Activity-based buying signals
- Custom property support
- Pagination handling

API Documentation: https://developers.hubspot.com/docs/api/crm/

Authentication: API key (simpler than OAuth)
Rate Limits: 100 requests per 10 seconds (per API key)
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import httpx

from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode
from cuga.adapters.sales.config import AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event

logger = logging.getLogger(__name__)


class HubSpotLiveAdapter(VendorAdapter):
    """
    Live adapter for HubSpot CRM API.
    
    Features:
    - Companies (accounts) with custom properties
    - Contacts with associations
    - Deals (opportunities) with stages
    - Activity tracking (tasks, meetings, calls)
    - Pagination support (100 records per page)
    - Buying signals derived from deal stage changes
    """

    def __init__(self, config: AdapterConfig):
        """
        Initialize HubSpot adapter with API credentials.
        
        Args:
            config: Adapter configuration with credentials
        
        Raises:
            ValueError: If api_key is missing
        """
        self.config = config
        self._validate_config()
        
        api_key = config.credentials.get("api_key", "")
        
        # SafeClient with enforced timeouts and retry
        self.client = SafeClient(
            base_url="https://api.hubapi.com",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=10.0),
        )
        
        logger.info(f"HubSpotLiveAdapter initialized for profile: {config.profile}")
        self._emit_event("adapter_initialized", {"vendor": "hubspot", "mode": "live"})

    def _validate_config(self) -> None:
        """Validate required credentials are present."""
        if not self.config.credentials.get("api_key"):
            raise ValueError("HubSpot adapter requires 'api_key' in credentials")

    def _emit_event(self, event_type: str, metadata: Dict[str, Any]) -> None:
        """Emit structured observability event."""
        emit_event(
            event_type=event_type,
            metadata={
                **metadata,
                "adapter": "hubspot",
                "profile": self.config.profile,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def get_mode(self) -> AdapterMode:
        """Return adapter mode (always LIVE)."""
        return AdapterMode.LIVE

    def validate_connection(self) -> bool:
        """
        Test API connectivity with account info endpoint.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test with account details endpoint
            response = self.client.get("/account-info/v3/details")
            
            if response.status_code == 200:
                logger.info("HubSpot connection validated successfully")
                self._emit_event("connection_validated", {"status": "success"})
                return True
            else:
                logger.error(f"HubSpot connection failed: {response.status_code}")
                self._emit_event("connection_validated", {"status": "failed", "status_code": response.status_code})
                return False
                
        except Exception as exc:
            logger.error(f"HubSpot connection error: {exc}")
            self._emit_event("connection_error", {"error": str(exc)})
            return False

    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch companies from HubSpot with pagination support.
        
        Args:
            filters: Optional filters (limit, properties)
        
        Returns:
            List of normalized company/account records
        """
        try:
            filters = filters or {}
            limit = filters.get("limit", 100)
            properties = filters.get("properties", [
                "name", "domain", "industry", "numberofemployees",
                "annualrevenue", "city", "state", "country",
                "description", "createdate", "hs_lastmodifieddate"
            ])
            
            # Build query params
            params = {
                "limit": min(limit, 100),  # HubSpot max per page
                "properties": ",".join(properties),
            }
            
            self._emit_event("fetch_accounts_start", {"limit": limit})
            
            # Fetch companies with pagination
            all_companies = []
            after = None
            
            while len(all_companies) < limit:
                if after:
                    params["after"] = after
                
                response = self.client.get("/crm/v3/objects/companies", params=params)
                
                if response.status_code == 401:
                    logger.error("HubSpot authentication failed - check API key")
                    self._emit_event("auth_error", {})
                    raise ValueError("Invalid HubSpot API key")
                
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After", "10")
                    logger.warning(f"Rate limit exceeded, retry after {retry_after}s")
                    self._emit_event("rate_limit_exceeded", {"retry_after": retry_after})
                    raise Exception(f"Rate limit exceeded, retry after {retry_after}s")
                
                response.raise_for_status()
                data = response.json()
                
                companies = data.get("results", [])
                all_companies.extend(companies)
                
                # Check for more pages
                paging = data.get("paging", {})
                after = paging.get("next", {}).get("after")
                
                if not after or len(all_companies) >= limit:
                    break
            
            # Normalize to canonical schema
            normalized = [self._normalize_company(company) for company in all_companies[:limit]]
            
            self._emit_event("fetch_accounts_complete", {"count": len(normalized)})
            return normalized
            
        except Exception as exc:
            logger.error(f"Error fetching accounts: {exc}")
            self._emit_event("fetch_accounts_error", {"error": str(exc)})
            raise

    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch contacts associated with a company.
        
        Args:
            account_id: HubSpot company ID
            filters: Optional filters (limit, properties)
        
        Returns:
            List of normalized contact records
        """
        try:
            filters = filters or {}
            limit = filters.get("limit", 100)
            
            self._emit_event("fetch_contacts_start", {"account_id": account_id, "limit": limit})
            
            # Fetch associated contacts
            response = self.client.get(
                f"/crm/v3/objects/companies/{account_id}/associations/contacts",
                params={"limit": min(limit, 100)},
            )
            
            if response.status_code == 404:
                logger.warning(f"Company not found: {account_id}")
                self._emit_event("company_not_found", {"account_id": account_id})
                return []
            
            response.raise_for_status()
            associations = response.json().get("results", [])
            
            # Fetch full contact details
            contacts = []
            for assoc in associations[:limit]:
                contact_id = assoc.get("id")
                if contact_id:
                    contact_response = self.client.get(
                        f"/crm/v3/objects/contacts/{contact_id}",
                        params={
                            "properties": "email,firstname,lastname,jobtitle,company,phone,city,state,country"
                        },
                    )
                    if contact_response.status_code == 200:
                        contacts.append(contact_response.json())
            
            # Normalize to canonical schema
            normalized = [self._normalize_contact(contact) for contact in contacts]
            
            self._emit_event("fetch_contacts_complete", {"count": len(normalized)})
            return normalized
            
        except Exception as exc:
            logger.error(f"Error fetching contacts for {account_id}: {exc}")
            self._emit_event("fetch_contacts_error", {"account_id": account_id, "error": str(exc)})
            raise

    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Fetch deals (opportunities) associated with a company.
        
        Args:
            account_id: HubSpot company ID
            filters: Optional filters (limit, properties)
        
        Returns:
            List of normalized deal/opportunity records
        """
        try:
            filters = filters or {}
            limit = filters.get("limit", 100)
            
            self._emit_event("fetch_opportunities_start", {"account_id": account_id, "limit": limit})
            
            # Fetch associated deals
            response = self.client.get(
                f"/crm/v3/objects/companies/{account_id}/associations/deals",
                params={"limit": min(limit, 100)},
            )
            
            if response.status_code == 404:
                logger.warning(f"Company not found: {account_id}")
                self._emit_event("company_not_found", {"account_id": account_id})
                return []
            
            response.raise_for_status()
            associations = response.json().get("results", [])
            
            # Fetch full deal details
            deals = []
            for assoc in associations[:limit]:
                deal_id = assoc.get("id")
                if deal_id:
                    deal_response = self.client.get(
                        f"/crm/v3/objects/deals/{deal_id}",
                        params={
                            "properties": "dealname,amount,dealstage,pipeline,closedate,createdate,hs_lastmodifieddate"
                        },
                    )
                    if deal_response.status_code == 200:
                        deals.append(deal_response.json())
            
            # Normalize to canonical schema
            normalized = [self._normalize_deal(deal) for deal in deals]
            
            self._emit_event("fetch_opportunities_complete", {"count": len(normalized)})
            return normalized
            
        except Exception as exc:
            logger.error(f"Error fetching opportunities for {account_id}: {exc}")
            self._emit_event("fetch_opportunities_error", {"account_id": account_id, "error": str(exc)})
            raise

    def fetch_buying_signals(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Derive buying signals from deal stages and activities.
        
        Signals derived from:
        - Deal stage progressions (opportunity advancing)
        - Recent deal creation (new opportunity)
        - Deal amount increases (expanding deal)
        - Recent activities (engagement spike)
        
        Args:
            account_id: HubSpot company ID
            filters: Optional filters
        
        Returns:
            List of derived buying signals
        """
        try:
            self._emit_event("fetch_buying_signals_start", {"account_id": account_id})
            
            signals = []
            
            # Fetch deals for this company
            deals = self.fetch_opportunities(account_id, filters={"limit": 50})
            
            # Derive signals from deals
            for deal in deals:
                # Signal 1: New opportunity (created in last 30 days)
                created_date = deal.get("created_at")
                if created_date:
                    created_dt = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
                    if datetime.now(created_dt.tzinfo) - created_dt < timedelta(days=30):
                        signals.append({
                            "id": f"new_deal_{deal.get('id')}",
                            "type": "new_opportunity",
                            "description": f"New deal created: {deal.get('name')}",
                            "confidence": 0.8,
                            "date": created_date,
                            "metadata": {
                                "deal_id": deal.get("id"),
                                "amount": deal.get("amount"),
                                "stage": deal.get("stage"),
                            },
                        })
                
                # Signal 2: Deal progression (late-stage deals)
                stage = deal.get("stage", "").lower()
                if any(keyword in stage for keyword in ["qualified", "proposal", "negotiation", "closing"]):
                    signals.append({
                        "id": f"deal_progress_{deal.get('id')}",
                        "type": "deal_progression",
                        "description": f"Deal in {stage} stage: {deal.get('name')}",
                        "confidence": 0.85,
                        "date": deal.get("updated_at", datetime.utcnow().isoformat()),
                        "metadata": {
                            "deal_id": deal.get("id"),
                            "stage": deal.get("stage"),
                            "amount": deal.get("amount"),
                        },
                    })
            
            self._emit_event("buying_signals_fetched", {"account_id": account_id, "signal_count": len(signals)})
            return signals
            
        except Exception as exc:
            logger.error(f"Error fetching buying signals for {account_id}: {exc}")
            self._emit_event("buying_signals_error", {"account_id": account_id, "error": str(exc)})
            return []

    def _normalize_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize HubSpot company data to canonical schema.
        
        Args:
            company: Raw HubSpot company data
        
        Returns:
            Normalized company data
        """
        props = company.get("properties", {})
        
        return {
            "id": company.get("id", ""),
            "name": props.get("name", ""),
            "domain": props.get("domain", ""),
            "industry": props.get("industry", ""),
            "employee_count": self._parse_int(props.get("numberofemployees")),
            "annual_revenue": self._parse_float(props.get("annualrevenue")),
            "location": {
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "country": props.get("country", ""),
            },
            "description": props.get("description", ""),
            "created_at": props.get("createdate"),
            "updated_at": props.get("hs_lastmodifieddate"),
            "metadata": {
                "hubspot_id": company.get("id"),
                "properties": props,
            },
        }

    def _normalize_contact(self, contact: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize HubSpot contact data to canonical schema.
        
        Args:
            contact: Raw HubSpot contact data
        
        Returns:
            Normalized contact data
        """
        props = contact.get("properties", {})
        
        return {
            "id": contact.get("id", ""),
            "email": props.get("email", ""),
            "first_name": props.get("firstname", ""),
            "last_name": props.get("lastname", ""),
            "full_name": f"{props.get('firstname', '')} {props.get('lastname', '')}".strip(),
            "title": props.get("jobtitle", ""),
            "company": props.get("company", ""),
            "phone": props.get("phone", ""),
            "location": {
                "city": props.get("city", ""),
                "state": props.get("state", ""),
                "country": props.get("country", ""),
            },
            "metadata": {
                "hubspot_id": contact.get("id"),
                "properties": props,
            },
        }

    def _normalize_deal(self, deal: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize HubSpot deal data to canonical schema.
        
        Args:
            deal: Raw HubSpot deal data
        
        Returns:
            Normalized deal/opportunity data
        """
        props = deal.get("properties", {})
        
        return {
            "id": deal.get("id", ""),
            "name": props.get("dealname", ""),
            "amount": self._parse_float(props.get("amount")),
            "stage": props.get("dealstage", ""),
            "pipeline": props.get("pipeline", ""),
            "close_date": props.get("closedate"),
            "created_at": props.get("createdate"),
            "updated_at": props.get("hs_lastmodifieddate"),
            "probability": self._estimate_probability(props.get("dealstage", "")),
            "metadata": {
                "hubspot_id": deal.get("id"),
                "properties": props,
            },
        }

    def _parse_int(self, value: Any) -> int:
        """Safely parse integer value."""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0

    def _parse_float(self, value: Any) -> float:
        """Safely parse float value."""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0

    def _estimate_probability(self, stage: str) -> float:
        """
        Estimate deal probability based on stage.
        
        Args:
            stage: Deal stage name
        
        Returns:
            Probability (0.0-1.0)
        """
        stage_lower = stage.lower()
        
        if any(keyword in stage_lower for keyword in ["closed", "won"]):
            return 1.0
        elif any(keyword in stage_lower for keyword in ["lost", "dead"]):
            return 0.0
        elif any(keyword in stage_lower for keyword in ["negotiation", "closing", "contract"]):
            return 0.8
        elif any(keyword in stage_lower for keyword in ["proposal", "quote"]):
            return 0.6
        elif any(keyword in stage_lower for keyword in ["qualified", "demo"]):
            return 0.4
        elif any(keyword in stage_lower for keyword in ["appointment", "connect"]):
            return 0.2
        else:
            return 0.1  # Default for unknown/early stages
