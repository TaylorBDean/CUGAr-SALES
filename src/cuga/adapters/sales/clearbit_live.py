"""
Clearbit Live Adapter for Company Enrichment and Tech Stack Detection.

This adapter provides:
- Company enrichment by domain (firmographics, employee count, funding)
- Person enrichment by email (job title, seniority, role)
- Technology stack detection (installed technologies)
- Industry classification and company categorization

API Documentation: https://clearbit.com/docs

Clearbit is an enrichment provider (not a CRM), so it does NOT provide:
- Account lists (use fetch via domain lookup)
- Contact lists (use enrichment via email)
- Opportunities (not applicable)
- Buying signals (derived from tech changes)

Authentication: Bearer token (API key)
Rate Limits: 600 requests/minute (10 req/sec)
"""

import logging
from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx

from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode
from cuga.adapters.sales.config import AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event

logger = logging.getLogger(__name__)


class ClearbitLiveAdapter(VendorAdapter):
    """
    Live adapter for Clearbit enrichment API.
    
    Features:
    - Company enrichment by domain
    - Person enrichment by email
    - Technology stack detection
    - Industry/sub-industry classification
    - Funding and employee data
    """

    def __init__(self, config: AdapterConfig):
        """
        Initialize Clearbit adapter with API credentials.
        
        Args:
            config: Adapter configuration with credentials
        
        Raises:
            ValueError: If api_key is missing
        """
        self.config = config
        self._validate_config()
        
        # Clearbit uses Basic auth with API key as username (password empty)
        api_key = config.credentials.get("api_key", "")
        
        # SafeClient with enforced timeouts and retry
        self.client = SafeClient(
            base_url="https://company.clearbit.com",
            auth=(api_key, ""),  # Basic auth: (username=api_key, password="")
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=10.0),
        )
        
        # Separate client for Person API (different base URL)
        self.person_client = SafeClient(
            base_url="https://person.clearbit.com",
            auth=(api_key, ""),
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=10.0),
        )
        
        logger.info(f"ClearbitLiveAdapter initialized for profile: {config.profile}")
        self._emit_event("adapter_initialized", {"vendor": "clearbit", "mode": "live"})

    def _validate_config(self) -> None:
        """Validate required credentials are present."""
        if not self.config.credentials.get("api_key"):
            raise ValueError("Clearbit adapter requires 'api_key' in credentials")

    def _emit_event(self, event_type: str, metadata: Dict[str, Any]) -> None:
        """Emit structured observability event."""
        emit_event(
            event_type=event_type,
            metadata={
                **metadata,
                "adapter": "clearbit",
                "profile": self.config.profile,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    def get_mode(self) -> AdapterMode:
        """Return adapter mode (always LIVE)."""
        return AdapterMode.LIVE

    def validate_connection(self) -> bool:
        """
        Test API connectivity with a simple enrichment query.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Test with a known company domain
            response = self.client.get(
                "/v2/companies/find",
                params={"domain": "clearbit.com"},
            )
            
            if response.status_code == 200:
                logger.info("Clearbit connection validated successfully")
                self._emit_event("connection_validated", {"status": "success"})
                return True
            else:
                logger.error(f"Clearbit connection failed: {response.status_code}")
                self._emit_event("connection_validated", {"status": "failed", "status_code": response.status_code})
                return False
                
        except Exception as exc:
            logger.error(f"Clearbit connection error: {exc}")
            self._emit_event("connection_error", {"error": str(exc)})
            return False

    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Clearbit does not provide account lists.
        Use enrich_company(domain) for individual company lookups.
        
        Args:
            filters: Not applicable for Clearbit
        
        Returns:
            Empty list (Clearbit is enrichment-only)
        """
        logger.warning("Clearbit does not support account listing - use enrich_company(domain) instead")
        self._emit_event("fetch_accounts_called", {"note": "Not supported by Clearbit"})
        return []

    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Clearbit does not provide contact lists.
        Use enrich_contact(email) for individual contact lookups.
        
        Args:
            account_id: Not applicable for Clearbit
            filters: Not applicable for Clearbit
        
        Returns:
            Empty list (Clearbit is enrichment-only)
        """
        logger.warning("Clearbit does not support contact listing - use enrich_contact(email) instead")
        self._emit_event("fetch_contacts_called", {"note": "Not supported by Clearbit"})
        return []

    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Clearbit does not provide opportunities (not a CRM).
        
        Args:
            account_id: Not applicable
            filters: Not applicable
        
        Returns:
            Empty list
        """
        logger.warning("Clearbit does not support opportunities - not a CRM")
        self._emit_event("fetch_opportunities_called", {"note": "Not supported by Clearbit"})
        return []

    def fetch_buying_signals(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Derive buying signals from technology changes.
        
        Clearbit does not explicitly provide signals, but we can derive them:
        - Technology additions → tech_adoption signals
        - Technology removals → tech_removal signals
        
        Args:
            account_id: Domain to check for tech changes
            filters: Optional filters
        
        Returns:
            List of derived buying signals
        """
        try:
            # Fetch current tech stack
            technologies = self.get_technologies(account_id)
            
            # Derive signals from recent tech changes
            # Note: In production, compare against historical data to detect changes
            signals = []
            
            for tech in technologies:
                # If we had historical data, we'd detect additions/removals
                # For now, return current tech as potential signals
                signals.append({
                    "id": f"tech_{tech.get('name', 'unknown').lower().replace(' ', '_')}",
                    "type": "tech_adoption",  # Assume adoption (no historical data)
                    "description": f"Using {tech.get('name')} technology",
                    "confidence": 0.7,  # Medium confidence without historical data
                    "date": datetime.utcnow().isoformat(),
                    "metadata": {
                        "category": tech.get("category", "unknown"),
                        "technology": tech.get("name"),
                    },
                })
            
            self._emit_event("buying_signals_fetched", {"domain": account_id, "signal_count": len(signals)})
            return signals
            
        except Exception as exc:
            logger.error(f"Error fetching buying signals for {account_id}: {exc}")
            self._emit_event("buying_signals_error", {"domain": account_id, "error": str(exc)})
            return []

    def enrich_company(self, domain: str) -> Optional[Dict[str, Any]]:
        """
        Enrich company data by domain lookup.
        
        Args:
            domain: Company website domain (e.g., "stripe.com")
        
        Returns:
            Enriched company data or None if not found
        """
        try:
            response = self.client.get(
                "/v2/companies/find",
                params={"domain": domain},
            )
            
            if response.status_code == 404:
                logger.warning(f"Company not found for domain: {domain}")
                self._emit_event("company_not_found", {"domain": domain})
                return None
            
            if response.status_code == 401:
                logger.error("Clearbit authentication failed - check API key")
                self._emit_event("auth_error", {"domain": domain})
                raise ValueError("Invalid Clearbit API key")
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                logger.warning(f"Rate limit exceeded, retry after {retry_after}s")
                self._emit_event("rate_limit_exceeded", {"domain": domain, "retry_after": retry_after})
                raise Exception(f"Rate limit exceeded, retry after {retry_after}s")
            
            response.raise_for_status()
            company_data = response.json()
            
            # Normalize to canonical schema
            enriched = self._normalize_company(company_data)
            
            self._emit_event("company_enriched", {"domain": domain, "found": True})
            return enriched
            
        except httpx.TimeoutException:
            logger.error(f"Timeout enriching company: {domain}")
            self._emit_event("company_enrich_timeout", {"domain": domain})
            return None
        except Exception as exc:
            if "404" in str(exc) or "not found" in str(exc).lower():
                return None
            logger.error(f"Error enriching company {domain}: {exc}")
            self._emit_event("company_enrich_error", {"domain": domain, "error": str(exc)})
            raise

    def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Enrich contact data by email lookup.
        
        Args:
            email: Contact email address
        
        Returns:
            Enriched contact data or None if not found
        """
        try:
            response = self.person_client.get(
                "/v2/people/find",
                params={"email": email},
            )
            
            if response.status_code == 404:
                logger.warning(f"Contact not found for email: {email}")
                self._emit_event("contact_not_found", {"email": email})
                return None
            
            if response.status_code == 401:
                logger.error("Clearbit authentication failed - check API key")
                self._emit_event("auth_error", {"email": email})
                raise ValueError("Invalid Clearbit API key")
            
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After", "60")
                logger.warning(f"Rate limit exceeded, retry after {retry_after}s")
                self._emit_event("rate_limit_exceeded", {"email": email, "retry_after": retry_after})
                raise Exception(f"Rate limit exceeded, retry after {retry_after}s")
            
            response.raise_for_status()
            person_data = response.json()
            
            # Normalize to canonical schema
            enriched = self._normalize_contact(person_data)
            
            self._emit_event("contact_enriched", {"email": email, "found": True})
            return enriched
            
        except httpx.TimeoutException:
            logger.error(f"Timeout enriching contact: {email}")
            self._emit_event("contact_enrich_timeout", {"email": email})
            return None
        except Exception as exc:
            if "404" in str(exc) or "not found" in str(exc).lower():
                return None
            logger.error(f"Error enriching contact {email}: {exc}")
            self._emit_event("contact_enrich_error", {"email": email, "error": str(exc)})
            raise

    def get_technologies(self, domain: str) -> List[Dict[str, Any]]:
        """
        Get technology stack for a company.
        
        Args:
            domain: Company website domain
        
        Returns:
            List of technologies with categories
        """
        try:
            # Tech data is included in company enrichment response
            company_data = self.enrich_company(domain)
            
            if not company_data:
                return []
            
            # Extract tech stack from company data
            tech_list = company_data.get("metadata", {}).get("technologies", [])
            
            self._emit_event("technologies_fetched", {"domain": domain, "tech_count": len(tech_list)})
            return tech_list
            
        except Exception as exc:
            logger.error(f"Error fetching technologies for {domain}: {exc}")
            self._emit_event("technologies_error", {"domain": domain, "error": str(exc)})
            return []

    def _normalize_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Clearbit company data to canonical schema.
        
        Args:
            company: Raw Clearbit company data
        
        Returns:
            Normalized company data
        """
        # Extract tech stack
        tech_list = []
        if company.get("tech"):
            tech_list = [
                {
                    "name": tech,
                    "category": self._categorize_technology(tech),
                }
                for tech in company.get("tech", [])
            ]
        
        # Categorize by industry
        category = company.get("category", {})
        
        return {
            "id": company.get("id", company.get("domain", "")),
            "name": company.get("name", ""),
            "domain": company.get("domain", ""),
            "industry": category.get("industry", ""),
            "sub_industry": category.get("subIndustry", ""),
            "employees": company.get("metrics", {}).get("employees", 0),
            "revenue": company.get("metrics", {}).get("estimatedAnnualRevenue"),
            "location": {
                "city": company.get("geo", {}).get("city", ""),
                "state": company.get("geo", {}).get("state", ""),
                "country": company.get("geo", {}).get("country", ""),
            },
            "description": company.get("description", ""),
            "founded_year": company.get("foundedYear"),
            "funding": {
                "raised": company.get("metrics", {}).get("raised"),
                "stage": None,  # Clearbit doesn't provide funding stage directly
            },
            "social_media": {
                "linkedin": company.get("linkedin", {}).get("handle"),
                "twitter": company.get("twitter", {}).get("handle"),
                "facebook": company.get("facebook", {}).get("handle"),
            },
            "metadata": {
                "tags": company.get("tags", []),
                "technologies": tech_list,
                "logo": company.get("logo"),
                "phone": company.get("phone"),
                "email_provider": company.get("emailProvider"),
            },
        }

    def _normalize_contact(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize Clearbit person data to canonical schema.
        
        Args:
            person: Raw Clearbit person data
        
        Returns:
            Normalized contact data
        """
        employment = person.get("employment", {})
        
        return {
            "id": person.get("id", person.get("email", "")),
            "email": person.get("email", ""),
            "first_name": person.get("name", {}).get("givenName", ""),
            "last_name": person.get("name", {}).get("familyName", ""),
            "full_name": person.get("name", {}).get("fullName", ""),
            "title": employment.get("title", ""),
            "role": employment.get("role", ""),
            "seniority": employment.get("seniority", ""),
            "company": {
                "name": employment.get("name", ""),
                "domain": employment.get("domain", ""),
            },
            "location": {
                "city": person.get("geo", {}).get("city", ""),
                "state": person.get("geo", {}).get("state", ""),
                "country": person.get("geo", {}).get("country", ""),
            },
            "social_media": {
                "linkedin": person.get("linkedin", {}).get("handle"),
                "twitter": person.get("twitter", {}).get("handle"),
                "facebook": person.get("facebook", {}).get("handle"),
            },
            "metadata": {
                "avatar": person.get("avatar"),
                "bio": person.get("bio"),
                "site": person.get("site"),
            },
        }

    def _categorize_technology(self, tech_name: str) -> str:
        """
        Categorize technology by name (simple heuristic).
        
        Args:
            tech_name: Technology name
        
        Returns:
            Category string
        """
        tech_lower = tech_name.lower()
        
        if any(keyword in tech_lower for keyword in ["google", "facebook", "linkedin", "analytics", "tag"]):
            return "analytics"
        elif any(keyword in tech_lower for keyword in ["aws", "azure", "cloud", "server", "hosting"]):
            return "infrastructure"
        elif any(keyword in tech_lower for keyword in ["salesforce", "hubspot", "marketo", "crm"]):
            return "crm"
        elif any(keyword in tech_lower for keyword in ["shopify", "magento", "ecommerce", "stripe", "payment"]):
            return "ecommerce"
        elif any(keyword in tech_lower for keyword in ["wordpress", "drupal", "cms", "content"]):
            return "cms"
        else:
            return "other"
