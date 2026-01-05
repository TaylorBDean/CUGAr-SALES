"""
BuiltWith Live Adapter

Technology tracking platform providing:
- Website technology detection
- Technology adoption trends
- Tech stack history
- Competitive intelligence
- Market share insights

Clean, transparent implementation with no obfuscation.
"""

from typing import Dict, List, Optional, Any
import httpx
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event


class BuiltWithLiveAdapter(VendorAdapter):
    """BuiltWith technology tracking adapter.
    
    Provides technology detection and market intelligence.
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize BuiltWith adapter.
        
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
        
        # Initialize HTTP client (API key passed as query param)
        self.client = SafeClient(
            base_url="https://api.builtwith.com",
            headers={
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0)
        )
        
        self.api_key = config.credentials['api_key']
        
        # Emit initialization event
        self._emit_event('adapter_initialized', {
            'adapter': 'builtwith',
            'mode': 'live',
            'base_url': 'https://api.builtwith.com'
        })
    
    def _validate_config(self):
        """Validate required credentials are present with helpful error messages."""
        if 'api_key' not in self.config.credentials:
            raise ValueError(
                "BuiltWith adapter requires missing credential: api_key (set via SALES_BUILTWITH_API_KEY). "
                "Please set the environment variable or provide it in credentials dict."
            )
    
    def get_mode(self) -> AdapterMode:
        """Return adapter mode (LIVE)."""
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """Validate connection to BuiltWith API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._emit_event('connection_validation_start', {'adapter': 'builtwith'})
            
            # Test API connection with simple domain lookup
            response = self.client.get("/v21/api.json", params={
                "KEY": self.api_key,
                "LOOKUP": "example.com"
            })
            success = response.status_code == 200
            
            self._emit_event('connection_validated', {
                'adapter': 'builtwith',
                'success': success,
                'status_code': response.status_code
            })
            
            return success
        except Exception as e:
            self._emit_event('connection_validation_error', {
                'adapter': 'builtwith',
                'error': str(e)[:200]
            })
            return False
    
    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search companies by technology usage.
        
        Args:
            filters: Query filters
                - technology: Technology to search for (required)
                - limit: Maximum results (default 100)
        
        Returns:
            List of normalized organization dictionaries
        """
        filters = filters or {}
        
        if "technology" not in filters:
            return []
        
        self._emit_event('fetch_start', {
            'adapter': 'builtwith',
            'operation': 'fetch_accounts',
            'filters': filters
        })
        
        try:
            # Use technology search endpoint
            response = self.client.get("/v1/api.json", params={
                "KEY": self.api_key,
                "TECH": filters["technology"],
                "MAXRESULTS": min(filters.get("limit", 100), 1000)
            })
            response.raise_for_status()
            data = response.json()
            
            results = data.get("Results", [])
            normalized = [self._normalize_tech_result(result) for result in results]
            
            self._emit_event('fetch_complete', {
                'adapter': 'builtwith',
                'operation': 'fetch_accounts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'builtwith',
                'operation': 'fetch_accounts',
                'status_code': e.response.status_code,
                'error': str(e)[:200]
            })
            
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 401:
                raise ValueError("BuiltWith authentication failed. Check API key.")
            elif e.response.status_code == 429:
                raise Exception("Rate limit hit. Please retry later.")
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'builtwith',
                'operation': 'fetch_accounts',
                'error': 'timeout'
            })
            return []
    
    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch contacts (not available in BuiltWith).
        
        Args:
            account_id: Domain identifier
            filters: Query filters
        
        Returns:
            Empty list (BuiltWith focuses on technology, not contacts)
        """
        return []
    
    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch opportunities (not available in BuiltWith).
        
        Args:
            account_id: Domain identifier
            filters: Query filters
        
        Returns:
            Empty list (BuiltWith doesn't track opportunities)
        """
        return []
    
    def fetch_buying_signals(self, domain: str) -> List[Dict[str, Any]]:
        """Derive buying signals from technology changes.
        
        Args:
            domain: Company domain
        
        Returns:
            List of buying signal dictionaries with types:
                - tech_adoption: New technology detected
                - tech_removal: Technology removed
                - tech_upgrade: Technology version changed
        """
        self._emit_event('fetch_start', {
            'adapter': 'builtwith',
            'operation': 'fetch_buying_signals',
            'domain': domain
        })
        
        try:
            signals = []
            
            # Get technology profile
            tech_profile = self.get_technology_profile(domain)
            
            if not tech_profile:
                return []
            
            # Analyze recent technology changes
            for group_name, technologies in tech_profile.get("Technologies", {}).items():
                for tech in technologies:
                    # Check for recent additions (FirstDetected within last 90 days)
                    first_detected = tech.get("FirstDetected")
                    if first_detected:
                        # Parse date and check recency
                        # For demo, treat all as potential signals
                        signals.append({
                            "type": "tech_adoption",
                            "description": f"Adopted {tech.get('Name')} in {group_name}",
                            "confidence": 0.8,
                            "metadata": {
                                "technology": tech.get("Name"),
                                "category": group_name,
                                "first_detected": first_detected,
                                "tag": tech.get("Tag")
                            }
                        })
            
            # Limit to top 5 signals
            signals = signals[:5]
            
            self._emit_event('fetch_complete', {
                'adapter': 'builtwith',
                'operation': 'fetch_buying_signals',
                'signal_count': len(signals)
            })
            
            return signals
        
        except Exception as e:
            self._emit_event('fetch_error', {
                'adapter': 'builtwith',
                'operation': 'fetch_buying_signals',
                'error': str(e)[:200]
            })
            return []
    
    def get_technology_profile(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get complete technology profile for domain.
        
        Args:
            domain: Company domain (e.g., "example.com")
        
        Returns:
            Raw BuiltWith technology profile or None if not found
        """
        try:
            response = self.client.get("/v21/api.json", params={
                "KEY": self.api_key,
                "LOOKUP": domain
            })
            response.raise_for_status()
            data = response.json()
            
            if data.get("Errors"):
                return None
            
            return data.get("Results", [{}])[0] if data.get("Results") else None
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def get_technology_history(self, domain: str) -> Dict[str, List[Dict[str, Any]]]:
        """Get technology adoption history for domain.
        
        Args:
            domain: Company domain
        
        Returns:
            Dictionary mapping technology categories to history entries
        """
        try:
            response = self.client.get("/v16/api.json", params={
                "KEY": self.api_key,
                "LOOKUP": domain,
                "SHOWHISTORY": "yes"
            })
            response.raise_for_status()
            data = response.json()
            
            if data.get("Errors"):
                return {}
            
            results = data.get("Results", [{}])[0] if data.get("Results") else {}
            return results.get("Technologies", {})
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {}
            raise
    
    def enrich_company(self, domain: str) -> Optional[Dict[str, Any]]:
        """Get company profile with technology stack.
        
        Args:
            domain: Company domain (e.g., "example.com")
        
        Returns:
            Normalized company dictionary with technology metadata
        """
        try:
            tech_profile = self.get_technology_profile(domain)
            
            if not tech_profile:
                return None
            
            return self._normalize_tech_profile(domain, tech_profile)
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def _normalize_tech_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize BuiltWith tech search result to canonical format.
        
        Args:
            result: Raw BuiltWith search result
        
        Returns:
            Normalized organization dictionary
        """
        domain = result.get("Domain")
        
        return {
            "id": domain,
            "name": domain.split(".")[0].title() if domain else None,
            "domain": domain,
            "industry": None,
            "employee_count": None,
            "revenue": None,
            "location": {
                "city": None,
                "state": None,
                "country": result.get("Country")
            },
            "metadata": {
                "first_indexed": result.get("FirstIndexed"),
                "last_indexed": result.get("LastIndexed"),
                "source": "builtwith"
            }
        }
    
    def _normalize_tech_profile(self, domain: str, profile: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize BuiltWith technology profile to canonical format.
        
        Args:
            domain: Company domain
            profile: Raw BuiltWith profile data
        
        Returns:
            Normalized organization dictionary with tech stack
        """
        # Extract technology categories
        technologies = profile.get("Technologies", {})
        tech_list = []
        
        for category, techs in technologies.items():
            for tech in techs:
                tech_list.append({
                    "name": tech.get("Name"),
                    "category": category,
                    "first_detected": tech.get("FirstDetected"),
                    "last_detected": tech.get("LastDetected")
                })
        
        return {
            "id": domain,
            "name": domain.split(".")[0].title(),
            "domain": domain,
            "industry": None,
            "employee_count": None,
            "revenue": None,
            "location": {
                "city": None,
                "state": profile.get("Meta", {}).get("Country"),
                "country": profile.get("Meta", {}).get("Country")
            },
            "metadata": {
                "first_indexed": profile.get("FirstIndexed"),
                "last_indexed": profile.get("LastIndexed"),
                "technology_count": len(tech_list),
                "technologies": tech_list,
                "source": "builtwith"
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
