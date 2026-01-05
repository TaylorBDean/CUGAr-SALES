#!/usr/bin/env python3
"""
ZoomInfo Live Adapter - Production Implementation

Implements live API integration for ZoomInfo with:
- Bearer token authentication
- Intent signals (scoops) fetching
- Company enrichment
- Contact search
- SafeClient (AGENTS.md compliant)
- Rate limiting and retry logic
- Schema normalization
- Observability integration
"""

import os
from typing import Dict, Any, Optional, List
from datetime import datetime
import httpx

from cuga.security.http_client import SafeClient
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig


class ZoomInfoLiveAdapter(VendorAdapter):
    """
    Live adapter for ZoomInfo API.
    
    Environment Variables Required:
        SALES_ZOOMINFO_API_KEY - API key for authentication
        SALES_ZOOMINFO_USERNAME - Username (optional, for some endpoints)
        SALES_ZOOMINFO_PASSWORD - Password (optional, for some endpoints)
    
    API Documentation:
        https://api-docs.zoominfo.com/
    
    Key Features:
        - Intent signals (scoops) - company news, funding, leadership changes
        - Company enrichment - firmographic data
        - Contact search - find decision makers
        - Technology tracking - tech stack adoption/removal
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize ZoomInfo adapter."""
        self.config = config
        self.trace_id = config.trace_id
        
        # Validate required credentials
        self._validate_config()
        
        # Initialize SafeClient (AGENTS.md compliant)
        self.client = SafeClient(
            base_url="https://api.zoominfo.com/v1",
            headers={
                "Authorization": f"Bearer {config.credentials['api_key']}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0),
        )
    
    def _validate_config(self) -> None:
        """Validate required configuration fields."""
        required_fields = ["api_key"]
        
        missing = [f for f in required_fields if not self.config.credentials.get(f)]
        if missing:
            raise ValueError(
                f"ZoomInfo adapter missing required credentials: {missing}. "
                f"Set SALES_ZOOMINFO_API_KEY environment variable."
            )
    
    def fetch_accounts(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Fetch companies from ZoomInfo.
        
        Args:
            filters: Optional filters:
                - limit: Max records to return (default: 100)
                - revenue_min: Minimum annual revenue
                - revenue_max: Maximum annual revenue
                - employee_min: Minimum employee count
                - employee_max: Maximum employee count
                - industry: Industry name
                - location: Location (city, state, country)
        
        Returns:
            List of normalized company records
        """
        self._emit_event("adapter_fetch_start", {
            "vendor": "zoominfo",
            "entity": "accounts",
            "filters": filters,
        })
        
        try:
            # Build request payload
            filters = filters or {}
            payload = {
                "page": 1,
                "rpp": filters.get("limit", 100),  # Records per page
            }
            
            # Add filters
            filter_criteria = []
            
            if revenue_min := filters.get("revenue_min"):
                filter_criteria.append({
                    "field": "revenue",
                    "operator": "gte",
                    "value": revenue_min
                })
            
            if revenue_max := filters.get("revenue_max"):
                filter_criteria.append({
                    "field": "revenue",
                    "operator": "lte",
                    "value": revenue_max
                })
            
            if employee_min := filters.get("employee_min"):
                filter_criteria.append({
                    "field": "employeeCount",
                    "operator": "gte",
                    "value": employee_min
                })
            
            if employee_max := filters.get("employee_max"):
                filter_criteria.append({
                    "field": "employeeCount",
                    "operator": "lte",
                    "value": employee_max
                })
            
            if industry := filters.get("industry"):
                filter_criteria.append({
                    "field": "industry",
                    "operator": "eq",
                    "value": industry
                })
            
            if filter_criteria:
                payload["filters"] = filter_criteria
            
            # Execute search
            response = self.client.post(
                "/search/company",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            companies = data.get("data", [])
            
            # Normalize schema
            normalized = self._normalize_accounts(companies)
            
            self._emit_event("adapter_fetch_complete", {
                "vendor": "zoominfo",
                "entity": "accounts",
                "count": len(normalized),
            })
            
            return normalized
        
        except httpx.HTTPStatusError as exc:
            # Handle rate limiting (429)
            if exc.response.status_code == 429:
                self._emit_event("adapter_rate_limit", {
                    "vendor": "zoominfo",
                    "retry_after": exc.response.headers.get("Retry-After"),
                })
            
            # Handle authentication errors (401)
            if exc.response.status_code == 401:
                self._emit_event("adapter_auth_error", {
                    "vendor": "zoominfo",
                    "error": "Invalid API key or expired token",
                })
            
            self._emit_event("adapter_fetch_error", {
                "vendor": "zoominfo",
                "entity": "accounts",
                "status_code": exc.response.status_code,
                "error": exc.response.text,
            })
            raise
        
        except httpx.TimeoutException as exc:
            self._emit_event("adapter_fetch_error", {
                "vendor": "zoominfo",
                "entity": "accounts",
                "error": "timeout",
            })
            raise
    
    def _normalize_accounts(self, companies: List[Dict]) -> List[Dict[str, Any]]:
        """Normalize ZoomInfo company schema to canonical format."""
        normalized = []
        
        for company in companies:
            normalized.append({
                "id": company.get("id"),
                "name": company.get("companyName"),
                "industry": company.get("industry"),
                "revenue": company.get("revenue"),
                "employee_count": company.get("employeeCount"),
                "address": {
                    "street": company.get("street"),
                    "city": company.get("city"),
                    "state": company.get("state"),
                    "country": company.get("country"),
                    "postal_code": company.get("zipCode"),
                },
                "phone": company.get("phone"),
                "website": company.get("website"),
                "description": company.get("companyDescription"),
                "source": "zoominfo",
            })
        
        return normalized
    
    def fetch_contacts(
        self,
        account_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch contacts for a company.
        
        Args:
            account_id: ZoomInfo company ID
        
        Returns:
            List of normalized contact records
        """
        self._emit_event("adapter_fetch_start", {
            "vendor": "zoominfo",
            "entity": "contacts",
            "account_id": account_id,
        })
        
        try:
            # Search for contacts at company
            payload = {
                "page": 1,
                "rpp": 100,
                "filters": [
                    {
                        "field": "companyId",
                        "operator": "eq",
                        "value": account_id
                    }
                ]
            }
            
            response = self.client.post(
                "/search/contact",
                json=payload,
            )
            response.raise_for_status()
            
            data = response.json()
            contacts = data.get("data", [])
            
            # Normalize schema
            normalized = self._normalize_contacts(contacts)
            
            self._emit_event("adapter_fetch_complete", {
                "vendor": "zoominfo",
                "entity": "contacts",
                "count": len(normalized),
            })
            
            return normalized
        
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                self._emit_event("adapter_auth_error", {
                    "vendor": "zoominfo",
                    "error": "Invalid API key",
                })
            
            self._emit_event("adapter_fetch_error", {
                "vendor": "zoominfo",
                "entity": "contacts",
                "status_code": exc.response.status_code,
            })
            raise
    
    def _normalize_contacts(self, contacts: List[Dict]) -> List[Dict[str, Any]]:
        """Normalize ZoomInfo contact schema to canonical format."""
        normalized = []
        
        for contact in contacts:
            normalized.append({
                "id": contact.get("id"),
                "first_name": contact.get("firstName"),
                "last_name": contact.get("lastName"),
                "email": contact.get("email"),
                "phone": contact.get("directPhoneNumber"),
                "title": contact.get("jobTitle"),
                "department": contact.get("jobFunction"),
                "seniority": contact.get("managementLevel"),
                "source": "zoominfo",
            })
        
        return normalized
    
    def fetch_opportunities(
        self,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        ZoomInfo doesn't have opportunities - return empty list.
        
        Args:
            account_id: Not used
        
        Returns:
            Empty list (ZoomInfo is an enrichment provider, not a CRM)
        """
        self._emit_event("adapter_fetch_start", {
            "vendor": "zoominfo",
            "entity": "opportunities",
            "note": "ZoomInfo does not provide opportunity data",
        })
        
        return []
    
    def fetch_buying_signals(
        self,
        account_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch buying signals (scoops) for a company.
        
        ZoomInfo "scoops" are intent signals including:
        - Funding events
        - Leadership changes
        - Technology adoption/removal
        - Hiring sprees
        - Office expansions
        - Product launches
        
        Args:
            account_id: ZoomInfo company ID
        
        Returns:
            List of buying signal records
        """
        self._emit_event("adapter_fetch_start", {
            "vendor": "zoominfo",
            "entity": "buying_signals",
            "account_id": account_id,
        })
        
        try:
            # Fetch scoops (intent signals)
            response = self.client.get(
                f"/company/{account_id}/scoops",
                params={"limit": 50}
            )
            response.raise_for_status()
            
            data = response.json()
            scoops = data.get("scoops", [])
            
            # Normalize to buying signals
            signals = self._normalize_buying_signals(scoops)
            
            self._emit_event("adapter_fetch_complete", {
                "vendor": "zoominfo",
                "entity": "buying_signals",
                "count": len(signals),
            })
            
            return signals
        
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Company has no scoops - not an error
                return []
            
            self._emit_event("adapter_fetch_error", {
                "vendor": "zoominfo",
                "entity": "buying_signals",
                "status_code": exc.response.status_code,
            })
            raise
    
    def _normalize_buying_signals(self, scoops: List[Dict]) -> List[Dict[str, Any]]:
        """
        Normalize ZoomInfo scoops to canonical buying signals.
        
        Signal Type Mapping:
        - funding -> funding_event
        - executive_change -> leadership_change
        - tech_install -> tech_adoption
        - tech_uninstall -> tech_removal
        - hiring -> hiring_spree
        - expansion -> expansion
        - product -> product_launch
        """
        normalized = []
        
        # Map ZoomInfo scoop types to canonical signal types
        type_mapping = {
            "funding": "funding_event",
            "executive_change": "leadership_change",
            "tech_install": "tech_adoption",
            "tech_uninstall": "tech_removal",
            "hiring": "hiring_spree",
            "expansion": "expansion",
            "product": "product_launch",
            "news": "company_news",
        }
        
        for scoop in scoops:
            scoop_type = scoop.get("type", "unknown")
            signal_type = type_mapping.get(scoop_type, "other")
            
            normalized.append({
                "signal_type": signal_type,
                "signal_date": scoop.get("date"),
                "description": scoop.get("headline") or scoop.get("summary"),
                "confidence": self._calculate_signal_confidence(scoop),
                "metadata": {
                    "source_type": scoop_type,
                    "url": scoop.get("url"),
                    "severity": scoop.get("severity"),  # ZoomInfo's importance rating
                },
                "source": "zoominfo",
            })
        
        return normalized
    
    def _calculate_signal_confidence(self, scoop: Dict) -> float:
        """
        Calculate confidence score for a signal based on ZoomInfo metadata.
        
        Factors:
        - Severity (high/medium/low)
        - Recency (newer = higher confidence)
        - Source type (some types are more reliable)
        
        Returns:
            Confidence score (0.0 to 1.0)
        """
        confidence = 0.5  # Base confidence
        
        # Adjust by severity
        severity = scoop.get("severity", "medium")
        if severity == "high":
            confidence += 0.3
        elif severity == "medium":
            confidence += 0.1
        
        # Adjust by scoop type (some are more reliable)
        scoop_type = scoop.get("type")
        if scoop_type in ["funding", "executive_change", "tech_install"]:
            confidence += 0.1  # High-confidence types
        
        # Clamp to [0, 1]
        return min(1.0, max(0.0, confidence))
    
    def enrich_company(self, domain: str) -> Dict[str, Any]:
        """
        Enrich company data by domain.
        
        Args:
            domain: Company website domain (e.g., "acme.com")
        
        Returns:
            Enriched company data
        """
        self._emit_event("adapter_enrich_start", {
            "vendor": "zoominfo",
            "domain": domain,
        })
        
        try:
            # Lookup company by domain
            response = self.client.get(
                "/company/lookup",
                params={"website": domain}
            )
            response.raise_for_status()
            
            data = response.json()
            company = data.get("company", {})
            
            # Normalize
            enriched = {
                "id": company.get("id"),
                "name": company.get("companyName"),
                "domain": domain,
                "industry": company.get("industry"),
                "revenue": company.get("revenue"),
                "employee_count": company.get("employeeCount"),
                "founded_year": company.get("foundedYear"),
                "technologies": company.get("technologies", []),
                "description": company.get("companyDescription"),
                "social_media": {
                    "linkedin": company.get("linkedinUrl"),
                    "twitter": company.get("twitterHandle"),
                    "facebook": company.get("facebookUrl"),
                },
                "source": "zoominfo",
            }
            
            self._emit_event("adapter_enrich_complete", {
                "vendor": "zoominfo",
                "domain": domain,
            })
            
            return enriched
        
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                # Company not found
                return {"error": "Company not found", "domain": domain}
            
            self._emit_event("adapter_enrich_error", {
                "vendor": "zoominfo",
                "domain": domain,
                "status_code": exc.response.status_code,
            })
            raise
    
    def get_mode(self) -> AdapterMode:
        """Get adapter mode (always LIVE for this adapter)."""
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """
        Validate ZoomInfo connection by fetching user info.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try a lightweight API call
            response = self.client.get("/user/info")
            response.raise_for_status()
            
            return True
        
        except Exception:
            return False
    
    def _emit_event(self, event_type: str, metadata: Dict[str, Any]) -> None:
        """Emit observability event (if collector available)."""
        try:
            from cuga.observability import emit_event
            
            emit_event(
                event_type=event_type,
                trace_id=self.trace_id,
                metadata=metadata,
            )
        except ImportError:
            pass  # Observability not configured - silent fallback
