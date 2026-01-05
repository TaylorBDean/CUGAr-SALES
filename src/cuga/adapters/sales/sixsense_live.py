"""
6sense Live Adapter

Predictive intent platform providing:
- Account scoring (intent scores 0-100)
- Keyword research (what accounts are researching)
- Buying stage identification (awareness, consideration, decision, purchase)
- Intent segments (topics of interest)
- Predictive analytics integration

Clean, transparent implementation with no obfuscation.
"""

from typing import Dict, List, Optional, Any
import httpx
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event


class SixSenseLiveAdapter(VendorAdapter):
    """6sense predictive intent platform adapter.
    
    Provides predictive account scoring and intent tracking.
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize 6sense adapter.
        
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
            base_url="https://api.6sense.com",
            headers={
                "Authorization": f"Bearer {config.credentials['api_key']}",
                "Content-Type": "application/json"
            },
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0)
        )
        
        # Emit initialization event
        self._emit_event('adapter_initialized', {
            'adapter': '6sense',
            'mode': 'live',
            'base_url': 'https://api.6sense.com'
        })
    
    def _validate_config(self):
        """Validate required credentials are present with helpful error messages."""
        required = ['api_key']
        missing = [k for k in required if k not in self.config.credentials]
        if missing:
            env_hints = {
                'api_key': 'SALES_SIXSENSE_API_KEY'
            }
            hints = [f"{k} (set via {env_hints.get(k, f'SALES_SIXSENSE_{k.upper()}')})" for k in missing]
            raise ValueError(
                f"6sense adapter requires missing credentials: {', '.join(hints)}. "
                f"Please set the environment variables or provide them in credentials dict."
            )
    
    def get_mode(self) -> AdapterMode:
        """Return adapter mode (LIVE)."""
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """Validate connection to 6sense API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._emit_event('connection_validation_start', {'adapter': '6sense'})
            
            # Test API connection with simple query
            response = self.client.get("/v1/accounts", params={"limit": 1})
            success = response.status_code == 200
            
            self._emit_event('connection_validated', {
                'adapter': '6sense',
                'success': success,
                'status_code': response.status_code
            })
            
            return success
        except Exception as e:
            self._emit_event('connection_validation_error', {
                'adapter': '6sense',
                'error': str(e)[:200]
            })
            return False
    
    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch accounts with intent filters.
        
        Args:
            filters: Query filters
                - intent_score_min: Minimum intent score (0-100)
                - intent_score_max: Maximum intent score (0-100)
                - buying_stage: awareness, consideration, decision, purchase
                - keywords: List of keywords being researched
                - segment_id: Intent segment filter
                - limit: Maximum results (default 100)
        
        Returns:
            List of normalized account dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': '6sense',
            'operation': 'fetch_accounts',
            'filters': filters
        })
        
        try:
            # Build query parameters
            params = {
                "limit": filters.get("limit", 100)
            }
            
            if "intent_score_min" in filters:
                params["intent_score_min"] = filters["intent_score_min"]
            if "intent_score_max" in filters:
                params["intent_score_max"] = filters["intent_score_max"]
            if "buying_stage" in filters:
                params["buying_stage"] = filters["buying_stage"]
            if "segment_id" in filters:
                params["segment_id"] = filters["segment_id"]
            
            # Make API request
            response = self.client.get("/v1/accounts", params=params)
            response.raise_for_status()
            data = response.json()
            
            accounts = data.get("accounts", [])
            normalized = [self._normalize_account(acc) for acc in accounts]
            
            self._emit_event('fetch_complete', {
                'adapter': '6sense',
                'operation': 'fetch_accounts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': '6sense',
                'operation': 'fetch_accounts',
                'status_code': e.response.status_code,
                'error': str(e)[:200]
            })
            
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 401:
                raise ValueError("6sense authentication failed. Check API key.")
            elif e.response.status_code == 429:
                retry_after = e.response.headers.get('Retry-After', '60')
                raise Exception(f"Rate limit hit. Retry after {retry_after} seconds.")
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': '6sense',
                'operation': 'fetch_accounts',
                'error': 'timeout'
            })
            return []
    
    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch contacts for account (if available in 6sense).
        
        Args:
            account_id: Account identifier
            filters: Query filters
        
        Returns:
            List of normalized contact dictionaries (may be empty if not available)
        """
        # 6sense primarily focuses on account-level data
        # Contact data may not be available in all plans
        return []
    
    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch opportunities for account (not available in 6sense).
        
        Args:
            account_id: Account identifier
            filters: Query filters
        
        Returns:
            Empty list (6sense doesn't track opportunities)
        """
        return []
    
    def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
        """Fetch intent signals for account.
        
        Args:
            account_id: Account identifier (domain or 6sense ID)
        
        Returns:
            List of buying signal dictionaries with types:
                - intent_surge: Sudden increase in research activity
                - keyword_match: Researching relevant keywords
                - buying_stage_advance: Moved to later buying stage
                - segment_engagement: Active in intent segment
        """
        self._emit_event('fetch_start', {
            'adapter': '6sense',
            'operation': 'fetch_buying_signals',
            'account_id': account_id
        })
        
        try:
            signals = []
            
            # Get account details with intent data
            response = self.client.get(f"/v1/accounts/{account_id}/intent")
            response.raise_for_status()
            data = response.json()
            
            intent_score = data.get("intent_score", 0)
            intent_velocity = data.get("intent_velocity", "low")  # low, medium, high
            buying_stage = data.get("buying_stage", "unknown")
            keywords = data.get("keywords", [])
            segments = data.get("segments", [])
            
            # Intent surge signal (based on velocity)
            if intent_velocity in ["high", "medium"]:
                confidence = 0.9 if intent_velocity == "high" else 0.7
                signals.append({
                    "type": "intent_surge",
                    "description": f"High research activity detected (velocity: {intent_velocity})",
                    "confidence": confidence,
                    "metadata": {
                        "intent_score": intent_score,
                        "velocity": intent_velocity,
                        "detected_at": data.get("last_updated")
                    }
                })
            
            # Keyword match signals
            for keyword in keywords[:5]:  # Top 5 keywords
                signals.append({
                    "type": "keyword_match",
                    "description": f"Researching: {keyword.get('term')}",
                    "confidence": min(0.9, 0.6 + (keyword.get('relevance', 0) * 0.3)),
                    "metadata": {
                        "keyword": keyword.get('term'),
                        "relevance": keyword.get('relevance'),
                        "search_volume": keyword.get('search_volume')
                    }
                })
            
            # Buying stage advance signal
            if buying_stage in ["decision", "purchase"]:
                confidence = 0.95 if buying_stage == "purchase" else 0.85
                signals.append({
                    "type": "buying_stage_advance",
                    "description": f"Account in {buying_stage} stage",
                    "confidence": confidence,
                    "metadata": {
                        "buying_stage": buying_stage,
                        "intent_score": intent_score
                    }
                })
            
            # Segment engagement signals
            for segment in segments:
                signals.append({
                    "type": "segment_engagement",
                    "description": f"Engaging with: {segment.get('name')}",
                    "confidence": 0.7,
                    "metadata": {
                        "segment_id": segment.get('id'),
                        "segment_name": segment.get('name'),
                        "engagement_level": segment.get('engagement_level')
                    }
                })
            
            self._emit_event('fetch_complete', {
                'adapter': '6sense',
                'operation': 'fetch_buying_signals',
                'signal_count': len(signals)
            })
            
            return signals
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': '6sense',
                'operation': 'fetch_buying_signals',
                'account_id': account_id,
                'status_code': e.response.status_code
            })
            
            if e.response.status_code == 404:
                return []
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': '6sense',
                'operation': 'fetch_buying_signals',
                'error': 'timeout'
            })
            return []
    
    def get_account_score(self, domain: str) -> Dict[str, Any]:
        """Get predictive intent score for domain.
        
        Args:
            domain: Company domain (e.g., "example.com")
        
        Returns:
            Dictionary with intent score and metadata:
                - intent_score: 0-100
                - buying_stage: awareness, consideration, decision, purchase
                - score_change: Change over last 30 days
                - velocity: low, medium, high
        """
        try:
            response = self.client.get(f"/v1/accounts/by-domain/{domain}")
            response.raise_for_status()
            data = response.json()
            
            return {
                "intent_score": data.get("intent_score", 0),
                "buying_stage": data.get("buying_stage", "unknown"),
                "score_change": data.get("score_change_30d", 0),
                "velocity": data.get("intent_velocity", "low"),
                "last_updated": data.get("last_updated")
            }
        
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return {"intent_score": 0, "buying_stage": "unknown", "score_change": 0, "velocity": "low"}
            raise
    
    def get_intent_segments(self, domain: str) -> List[Dict[str, Any]]:
        """Get intent segments (topics) for domain.
        
        Args:
            domain: Company domain
        
        Returns:
            List of intent segments with engagement data
        """
        try:
            response = self.client.get(f"/v1/accounts/by-domain/{domain}/segments")
            response.raise_for_status()
            data = response.json()
            
            return data.get("segments", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def get_keyword_research(self, domain: str) -> List[Dict[str, Any]]:
        """Get keywords being researched by account.
        
        Args:
            domain: Company domain
        
        Returns:
            List of keywords with relevance and search volume
        """
        try:
            response = self.client.get(f"/v1/accounts/by-domain/{domain}/keywords")
            response.raise_for_status()
            data = response.json()
            
            return data.get("keywords", [])
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return []
            raise
    
    def _normalize_account(self, account: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize 6sense account to canonical format.
        
        Args:
            account: Raw 6sense account data
        
        Returns:
            Normalized account dictionary
        """
        return {
            "id": account.get("id", account.get("account_id")),
            "name": account.get("name", account.get("company_name")),
            "domain": account.get("domain", account.get("website")),
            "industry": account.get("industry"),
            "employee_count": account.get("employee_count"),
            "revenue": account.get("revenue"),
            "intent_score": account.get("intent_score", 0),
            "buying_stage": account.get("buying_stage", "unknown"),
            "location": {
                "city": account.get("city"),
                "state": account.get("state"),
                "country": account.get("country")
            },
            "metadata": {
                "intent_velocity": account.get("intent_velocity"),
                "score_change_30d": account.get("score_change_30d"),
                "top_keywords": account.get("top_keywords", []),
                "segments": account.get("segments", []),
                "last_updated": account.get("last_updated"),
                "source": "6sense"
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
