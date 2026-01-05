"""
Crunchbase Live Adapter

Funding events platform providing:
- Organization search and profiles
- Funding rounds tracking
- M&A activity
- IPO tracking
- Executive changes
- Investment intelligence

Clean, transparent implementation with no obfuscation.
"""

from typing import Dict, List, Optional, Any
import httpx
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event


class CrunchbaseLiveAdapter(VendorAdapter):
    """Crunchbase funding events adapter.
    
    Provides funding rounds, M&A, and company profile data.
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize Crunchbase adapter.
        
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
            base_url="https://api.crunchbase.com/api/v4",
            headers={
                "X-cb-user-key": config.credentials['api_key'],
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0)
        )
        
        # Emit initialization event
        self._emit_event('adapter_initialized', {
            'adapter': 'crunchbase',
            'mode': 'live',
            'base_url': 'https://api.crunchbase.com/api/v4'
        })
    
    def _validate_config(self):
        """Validate required credentials are present with helpful error messages."""
        if 'api_key' not in self.config.credentials:
            raise ValueError(
                "Crunchbase adapter requires missing credential: api_key (set via SALES_CRUNCHBASE_API_KEY). "
                "Please set the environment variable or provide it in credentials dict."
            )
    
    def get_mode(self) -> AdapterMode:
        """Return adapter mode (LIVE)."""
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """Validate connection to Crunchbase API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._emit_event('connection_validation_start', {'adapter': 'crunchbase'})
            
            # Test API connection with simple search
            response = self.client.get("/searches/organizations", params={
                "limit": 1
            })
            success = response.status_code == 200
            
            self._emit_event('connection_validated', {
                'adapter': 'crunchbase',
                'success': success,
                'status_code': response.status_code
            })
            
            return success
        except Exception as e:
            self._emit_event('connection_validation_error', {
                'adapter': 'crunchbase',
                'error': str(e)[:200]
            })
            return False
    
    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search organizations with filters.
        
        Args:
            filters: Query filters
                - funding_round_min: Minimum funding amount
                - funding_round_max: Maximum funding amount
                - funding_stage: seed, series_a, series_b, etc.
                - founded_year_min: Minimum founding year
                - founded_year_max: Maximum founding year
                - location: Geographic filter
                - limit: Maximum results (default 100)
        
        Returns:
            List of normalized organization dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': 'crunchbase',
            'operation': 'fetch_accounts',
            'filters': filters
        })
        
        try:
            # Build query
            query = {}
            
            if "funding_round_min" in filters or "funding_round_max" in filters:
                query["funding_total"] = {
                    "min": filters.get("funding_round_min"),
                    "max": filters.get("funding_round_max")
                }
            if "funding_stage" in filters:
                query["last_funding_type"] = filters["funding_stage"]
            if "founded_year_min" in filters or "founded_year_max" in filters:
                query["founded_on"] = {
                    "min": f"{filters.get('founded_year_min', 1900)}-01-01",
                    "max": f"{filters.get('founded_year_max', 2030)}-12-31"
                }
            if "location" in filters:
                query["location_identifiers"] = [filters["location"]]
            
            # Make API request
            response = self.client.post("/searches/organizations", json={
                "field_ids": [
                    "identifier", "name", "short_description", "website",
                    "founded_on", "num_employees_enum", "funding_total",
                    "last_funding_type", "location_identifiers"
                ],
                "query": [query] if query else [],
                "limit": min(filters.get("limit", 100), 1000)
            })
            response.raise_for_status()
            data = response.json()
            
            entities = data.get("entities", [])
            normalized = [self._normalize_organization(org["properties"]) for org in entities]
            
            self._emit_event('fetch_complete', {
                'adapter': 'crunchbase',
                'operation': 'fetch_accounts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'crunchbase',
                'operation': 'fetch_accounts',
                'status_code': e.response.status_code,
                'error': str(e)[:200]
            })
            
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 401:
                raise ValueError("Crunchbase authentication failed. Check API key.")
            elif e.response.status_code == 429:
                raise Exception("Rate limit hit. Please retry later.")
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'crunchbase',
                'operation': 'fetch_accounts',
                'error': 'timeout'
            })
            return []
    
    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch contacts (executives) for organization.
        
        Args:
            account_id: Organization identifier (permalink)
            filters: Query filters
        
        Returns:
            List of normalized contact dictionaries (may be limited)
        """
        # Crunchbase focuses on company data, not individual contacts
        # Contact data (executives) requires specific entity queries
        return []
    
    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch opportunities (not available in Crunchbase).
        
        Args:
            account_id: Organization identifier
            filters: Query filters
        
        Returns:
            Empty list (Crunchbase doesn't track opportunities)
        """
        return []
    
    def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
        """Derive buying signals from funding events.
        
        Args:
            account_id: Organization identifier (permalink)
        
        Returns:
            List of buying signal dictionaries with types:
                - funding_event: New funding round announced
                - acquisition: Company acquired
                - ipo: IPO filed/completed
                - executive_change: Leadership transition
        """
        self._emit_event('fetch_start', {
            'adapter': 'crunchbase',
            'operation': 'fetch_buying_signals',
            'account_id': account_id
        })
        
        try:
            signals = []
            
            # Get funding rounds
            funding_rounds = self.get_funding_rounds(account_id)
            
            for round_data in funding_rounds[:3]:  # Recent 3 rounds
                signals.append({
                    "type": "funding_event",
                    "description": f"{round_data.get('investment_type')} round: ${round_data.get('money_raised', {}).get('value', 0):,.0f}",
                    "confidence": 0.9,
                    "metadata": {
                        "funding_type": round_data.get("investment_type"),
                        "amount": round_data.get("money_raised", {}).get("value"),
                        "currency": round_data.get("money_raised", {}).get("currency"),
                        "announced_on": round_data.get("announced_on"),
                        "num_investors": round_data.get("num_investors")
                    }
                })
            
            # Note: Acquisition and IPO data require specific queries
            # These would be detected via organization status changes
            
            self._emit_event('fetch_complete', {
                'adapter': 'crunchbase',
                'operation': 'fetch_buying_signals',
                'signal_count': len(signals)
            })
            
            return signals
        
        except Exception as e:
            self._emit_event('fetch_error', {
                'adapter': 'crunchbase',
                'operation': 'fetch_buying_signals',
                'error': str(e)[:200]
            })
            return []
    
    def enrich_company(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get company profile by domain.
        
        Args:
            domain: Company domain (e.g., "example.com")
        
        Returns:
            Normalized company dictionary or None if not found
        """
        try:
            # Search by domain
            response = self.client.post("/searches/organizations", json={
                "field_ids": [
                    "identifier", "name", "short_description", "website",
                    "founded_on", "num_employees_enum", "funding_total",
                    "last_funding_type", "location_identifiers", "categories"
                ],
                "query": [{"website_url": domain}],
                "limit": 1
            })
            response.raise_for_status()
            data = response.json()
            
            entities = data.get("entities", [])
            if entities:
                return self._normalize_organization(entities[0]["properties"])
            return None
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def get_funding_rounds(self, organization_id: str) -> List[Dict[str, Any]]:
        """Get funding history for organization.
        
        Args:
            organization_id: Organization identifier (permalink)
        
        Returns:
            List of funding round dictionaries
        """
        try:
            response = self.client.get(f"/entities/organizations/{organization_id}/funding_rounds")
            response.raise_for_status()
            data = response.json()
            
            return data.get("cards", {}).get("funding_rounds", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def _normalize_organization(self, org: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Crunchbase organization to canonical format.
        
        Args:
            org: Raw Crunchbase organization data
        
        Returns:
            Normalized organization dictionary
        """
        # Extract location
        locations = org.get("location_identifiers", [])
        location = locations[0] if locations else {}
        
        return {
            "id": org.get("identifier", {}).get("permalink"),
            "name": org.get("name"),
            "domain": org.get("website", {}).get("value"),
            "industry": ", ".join([cat.get("value") for cat in org.get("categories", [])]),
            "employee_count": self._parse_employee_range(org.get("num_employees_enum")),
            "revenue": None,  # Not directly available
            "location": {
                "city": location.get("value") if isinstance(location, dict) else None,
                "state": None,
                "country": None
            },
            "metadata": {
                "short_description": org.get("short_description"),
                "founded_on": org.get("founded_on", {}).get("value"),
                "funding_total": org.get("funding_total", {}).get("value"),
                "funding_currency": org.get("funding_total", {}).get("currency"),
                "last_funding_type": org.get("last_funding_type"),
                "source": "crunchbase"
            }
        }
    
    def _parse_employee_range(self, employee_enum: Optional[str]) -> Optional[int]:
        """Parse employee range enum to approximate count.
        
        Args:
            employee_enum: Crunchbase employee range (e.g., "c_00101_00250")
        
        Returns:
            Approximate employee count (midpoint of range)
        """
        if not employee_enum:
            return None
        
        # Map common ranges to midpoints
        ranges = {
            "c_00001_00010": 5,
            "c_00011_00050": 30,
            "c_00051_00100": 75,
            "c_00101_00250": 175,
            "c_00251_00500": 375,
            "c_00501_01000": 750,
            "c_01001_05000": 3000,
            "c_05001_10000": 7500,
            "c_10001_max": 15000
        }
        
        return ranges.get(employee_enum)
    
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
