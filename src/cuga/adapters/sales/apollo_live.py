"""
Apollo.io Live Adapter

Contact enrichment platform providing:
- Contact search and enrichment by email
- Email verification and deliverability
- Company search
- Engagement tracking
- Sequence automation support

Clean, transparent implementation with no obfuscation.
"""

from typing import Dict, List, Optional, Any
import httpx
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event


class ApolloLiveAdapter(VendorAdapter):
    """Apollo.io contact enrichment adapter.
    
    Provides contact/company enrichment and email verification.
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize Apollo.io adapter.
        
        Args:
            config: Adapter configuration with credentials and execution context
        """
        self.config = config
        
        # Extract trace_id from ExecutionContext (preferred) or fallback to legacy patterns
        if config.execution_context:
            self.trace_id = config.execution_context.trace_id
        elif config.trace_id:
            self.trace_id = config.trace_id
        elif config.metadata and 'trace_id' in config.metadata:
            self.trace_id = config.metadata['trace_id']
        else:
            self.trace_id = 'unknown'
        
        # Validate configuration
        self._validate_config()
        
        # Initialize HTTP client
        self.client = SafeClient(
            base_url="https://api.apollo.io",
            headers={
                "X-Api-Key": config.credentials['api_key'],
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0)
        )
        
        # Emit initialization event
        self._emit_event('adapter_initialized', {
            'adapter': 'apollo',
            'mode': 'live',
            'base_url': 'https://api.apollo.io'
        })
    
    def _validate_config(self):
        """Validate required credentials are present with helpful error messages."""
        if 'api_key' not in self.config.credentials:
            raise ValueError(
                "Apollo.io adapter requires missing credential: api_key (set via SALES_APOLLO_API_KEY). "
                "Please set the environment variable or provide it in credentials dict."
            )
    
    def get_mode(self) -> AdapterMode:
        """Return adapter mode (LIVE)."""
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """Validate connection to Apollo.io API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._emit_event('connection_validation_start', {'adapter': 'apollo'})
            
            # Test API connection with simple organization search
            response = self.client.post("/v1/organizations/search", json={
                "page": 1,
                "per_page": 1
            })
            success = response.status_code == 200
            
            self._emit_event('connection_validated', {
                'adapter': 'apollo',
                'success': success,
                'status_code': response.status_code
            })
            
            return success
        except Exception as e:
            self._emit_event('connection_validation_error', {
                'adapter': 'apollo',
                'error': str(e)[:200]
            })
            return False
    
    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search companies with filters.
        
        Args:
            filters: Query filters
                - industry: Industry filter
                - revenue_min: Minimum revenue
                - revenue_max: Maximum revenue
                - employees_min: Minimum employees
                - employees_max: Maximum employees
                - location: Geographic filter
                - limit: Maximum results (default 100)
        
        Returns:
            List of normalized company dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': 'apollo',
            'operation': 'fetch_accounts',
            'filters': filters
        })
        
        try:
            # Build search query
            query = {}
            
            if "industry" in filters:
                query["organization_industry_tag_ids"] = [filters["industry"]]
            if "revenue_min" in filters or "revenue_max" in filters:
                query["revenue_range"] = {
                    "min": filters.get("revenue_min"),
                    "max": filters.get("revenue_max")
                }
            if "employees_min" in filters or "employees_max" in filters:
                query["organization_num_employees_ranges"] = [{
                    "min": filters.get("employees_min"),
                    "max": filters.get("employees_max")
                }]
            if "location" in filters:
                query["organization_locations"] = [filters["location"]]
            
            # Make API request
            response = self.client.post("/v1/organizations/search", json={
                **query,
                "page": 1,
                "per_page": min(filters.get("limit", 100), 100)
            })
            response.raise_for_status()
            data = response.json()
            
            organizations = data.get("organizations", [])
            normalized = [self._normalize_company(org) for org in organizations]
            
            self._emit_event('fetch_complete', {
                'adapter': 'apollo',
                'operation': 'fetch_accounts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'apollo',
                'operation': 'fetch_accounts',
                'status_code': e.response.status_code,
                'error': str(e)[:200]
            })
            
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 401:
                raise ValueError("Apollo.io authentication failed. Check API key.")
            elif e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After', '60')
                raise Exception(f"Rate limit hit. Retry after {retry_after} seconds.")
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'apollo',
                'operation': 'fetch_accounts',
                'error': 'timeout'
            })
            return []
    
    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search contacts with filters.
        
        Args:
            account_id: Company identifier (domain or Apollo ID)
            filters: Query filters
                - title: Job title filter
                - seniority: Seniority level
                - department: Department filter
                - email_status: verified, unverified
                - limit: Maximum results (default 50)
        
        Returns:
            List of normalized contact dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': 'apollo',
            'operation': 'fetch_contacts',
            'account_id': account_id,
            'filters': filters
        })
        
        try:
            # Build search query
            query = {
                "organization_ids": [account_id] if not account_id.endswith('.com') else None,
                "organization_domains": [account_id] if account_id.endswith('.com') else None
            }
            
            if "title" in filters:
                query["person_titles"] = [filters["title"]]
            if "seniority" in filters:
                query["person_seniorities"] = [filters["seniority"]]
            if "department" in filters:
                query["organization_department_or_subdepartments"] = [filters["department"]]
            if filters.get("email_status") == "verified":
                query["prospected_by_current_team"] = ["yes"]
            
            # Make API request
            response = self.client.post("/v1/people/search", json={
                **{k: v for k, v in query.items() if v is not None},
                "page": 1,
                "per_page": min(filters.get("limit", 50), 100)
            })
            response.raise_for_status()
            data = response.json()
            
            people = data.get("people", [])
            normalized = [self._normalize_contact(person) for person in people]
            
            self._emit_event('fetch_complete', {
                'adapter': 'apollo',
                'operation': 'fetch_contacts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'apollo',
                'operation': 'fetch_contacts',
                'status_code': e.response.status_code
            })
            
            if e.response.status_code == 404:
                return []
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'apollo',
                'operation': 'fetch_contacts',
                'error': 'timeout'
            })
            return []
    
    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch opportunities (not available in Apollo.io).
        
        Args:
            account_id: Account identifier
            filters: Query filters
        
        Returns:
            Empty list (Apollo.io doesn't track opportunities)
        """
        return []
    
    def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
        """Derive buying signals from enrichment data.
        
        Args:
            account_id: Account identifier (domain or Apollo ID)
        
        Returns:
            List of buying signal dictionaries with types:
                - email_verified: Contact email verified
                - engagement_detected: Contact engaged with outreach
        """
        self._emit_event('fetch_start', {
            'adapter': 'apollo',
            'operation': 'fetch_buying_signals',
            'account_id': account_id
        })
        
        try:
            signals = []
            
            # Get contacts for account
            contacts = self.fetch_contacts(account_id, {'email_status': 'verified'})
            
            # Email verified signal
            if contacts:
                verified_count = len(contacts)
                signals.append({
                    "type": "email_verified",
                    "description": f"{verified_count} verified contact(s) available",
                    "confidence": 0.9,
                    "metadata": {
                        "verified_count": verified_count,
                        "contacts": [c.get('email') for c in contacts[:5]]
                    }
                })
            
            # Note: Engagement tracking requires emailer campaign integration
            # which is beyond basic enrichment scope
            
            self._emit_event('fetch_complete', {
                'adapter': 'apollo',
                'operation': 'fetch_buying_signals',
                'signal_count': len(signals)
            })
            
            return signals
        
        except Exception as e:
            self._emit_event('fetch_error', {
                'adapter': 'apollo',
                'operation': 'fetch_buying_signals',
                'error': str(e)[:200]
            })
            return []
    
    def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
        """Enrich contact by email (get full profile).
        
        Args:
            email: Contact email address
        
        Returns:
            Normalized contact dictionary or None if not found
        """
        try:
            response = self.client.post("/v1/people/match", json={
                "email": email
            })
            response.raise_for_status()
            data = response.json()
            
            person = data.get("person")
            return self._normalize_contact(person) if person else None
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def verify_email(self, email: str) -> Dict[str, Any]:
        """Verify email deliverability.
        
        Args:
            email: Email address to verify
        
        Returns:
            Dictionary with verification results:
                - status: valid, invalid, unknown
                - deliverable: True/False
                - free_email: True/False (Gmail, Yahoo, etc.)
        """
        try:
            response = self.client.post("/v1/email_verifier/verify", json={
                "email": email
            })
            response.raise_for_status()
            data = response.json()
            
            return {
                "status": data.get("status", "unknown"),
                "deliverable": data.get("deliverable", False),
                "free_email": data.get("is_free_email", False),
                "catch_all": data.get("is_catch_all", False),
                "disposable": data.get("is_disposable", False)
            }
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"status": "unknown", "deliverable": False, "free_email": False}
            raise
    
    def _normalize_company(self, org: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Apollo.io organization to canonical format.
        
        Args:
            org: Raw Apollo.io organization data
        
        Returns:
            Normalized company dictionary
        """
        return {
            "id": org.get("id"),
            "name": org.get("name"),
            "domain": org.get("website_url", org.get("primary_domain")),
            "industry": org.get("industry"),
            "employee_count": org.get("estimated_num_employees"),
            "revenue": None,  # Revenue not directly in search results
            "location": {
                "city": org.get("city"),
                "state": org.get("state"),
                "country": org.get("country")
            },
            "metadata": {
                "phone": org.get("phone"),
                "linkedin_url": org.get("linkedin_url"),
                "facebook_url": org.get("facebook_url"),
                "twitter_url": org.get("twitter_url"),
                "founded_year": org.get("founded_year"),
                "source": "apollo"
            }
        }
    
    def _normalize_contact(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Apollo.io person to canonical format.
        
        Args:
            person: Raw Apollo.io person data
        
        Returns:
            Normalized contact dictionary
        """
        return {
            "id": person.get("id"),
            "email": person.get("email"),
            "first_name": person.get("first_name"),
            "last_name": person.get("last_name"),
            "name": f"{person.get('first_name', '')} {person.get('last_name', '')}".strip(),
            "title": person.get("title"),
            "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number") if person.get("phone_numbers") else None,
            "account_id": person.get("organization_id"),
            "account_name": person.get("organization", {}).get("name"),
            "metadata": {
                "linkedin_url": person.get("linkedin_url"),
                "seniority": person.get("seniority"),
                "departments": person.get("departments", []),
                "email_status": person.get("email_status"),
                "photo_url": person.get("photo_url"),
                "city": person.get("city"),
                "state": person.get("state"),
                "country": person.get("country"),
                "source": "apollo"
            }
        }
    
    def _emit_event(self, event_type: str, attributes: Dict[str, Any]):
        """Emit observability event.
        
        Args:
            event_type: Type of event
            attributes: Event attributes
        """
        try:
            from cuga.observability.events import StructuredEvent, EventType
            
            # Map string event types to EventType enum
            event_type_map = {
                'adapter_initialized': EventType.TOOL_CALL_START,
                'connection_validation_start': EventType.TOOL_CALL_START,
                'connection_validated': EventType.TOOL_CALL_COMPLETE,
                'connection_validation_error': EventType.TOOL_CALL_ERROR,
                'data_fetch_start': EventType.TOOL_CALL_START,
                'data_fetched': EventType.TOOL_CALL_COMPLETE,
                'fetch_error': EventType.TOOL_CALL_ERROR,
            }
            
            mapped_type = event_type_map.get(event_type, EventType.TOOL_CALL_START)
            
            emit_event(StructuredEvent(
                event_type=mapped_type,
                trace_id=self.trace_id,
                attributes={**attributes, 'original_event_type': event_type}
            ))
        except ImportError:
            # Observability not available, skip silently
            pass
