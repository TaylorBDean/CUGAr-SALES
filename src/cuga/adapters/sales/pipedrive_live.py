"""
Pipedrive Live Adapter

SMB CRM platform providing:
- Organizations (companies)
- Persons (contacts)
- Deals (opportunities)
- Activities tracking
- Pipeline management

Clean, transparent implementation with no obfuscation.
"""

from typing import Dict, List, Optional, Any
import httpx
from cuga.adapters.sales.protocol import VendorAdapter, AdapterMode, AdapterConfig
from cuga.security.http_client import SafeClient
from cuga.observability import emit_event


class PipedriveLiveAdapter(VendorAdapter):
    """Pipedrive SMB CRM adapter.
    
    Provides access to organizations, persons, and deals.
    """
    
    def __init__(self, config: AdapterConfig):
        """Initialize Pipedrive adapter.
        
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
        
        # Pipedrive uses API token in query params
        self.api_token = config.credentials['api_key']
        
        # Initialize HTTP client
        self.client = SafeClient(
            base_url="https://api.pipedrive.com/v1",
            headers={"Content-Type": "application/json"},
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=10.0, pool=10.0)
        )
        
        # Emit initialization event
        self._emit_event('adapter_initialized', {
            'adapter': 'pipedrive',
            'mode': 'live',
            'base_url': 'https://api.pipedrive.com/v1'
        })
    
    def _validate_config(self):
        """Validate required credentials are present with helpful error messages."""
        if 'api_key' not in self.config.credentials:
            raise ValueError(
                "Pipedrive adapter requires missing credential: api_key (set via SALES_PIPEDRIVE_API_KEY). "
                "Please set the environment variable or provide it in credentials dict."
            )
    
    def get_mode(self) -> AdapterMode:
        """Return adapter mode (LIVE)."""
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """Validate connection to Pipedrive API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._emit_event('connection_validation_start', {'adapter': 'pipedrive'})
            
            # Test API connection
            response = self.client.get("/organizations", params={
                "api_token": self.api_token,
                "limit": 1
            })
            success = response.status_code == 200
            
            self._emit_event('connection_validated', {
                'adapter': 'pipedrive',
                'success': success,
                'status_code': response.status_code
            })
            
            return success
        except Exception as e:
            self._emit_event('connection_validation_error', {
                'adapter': 'pipedrive',
                'error': str(e)[:200]
            })
            return False
    
    def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch organizations (companies).
        
        Args:
            filters: Query filters
                - limit: Maximum results (default 100)
                - search: Search term
        
        Returns:
            List of normalized organization dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': 'pipedrive',
            'operation': 'fetch_accounts',
            'filters': filters
        })
        
        try:
            params = {
                "api_token": self.api_token,
                "limit": min(filters.get("limit", 100), 500)
            }
            
            if "search" in filters:
                params["term"] = filters["search"]
            
            # Make API request
            response = self.client.get("/organizations", params=params)
            response.raise_for_status()
            data = response.json()
            
            organizations = data.get("data", []) if data.get("success") else []
            normalized = [self._normalize_organization(org) for org in organizations] if organizations else []
            
            self._emit_event('fetch_complete', {
                'adapter': 'pipedrive',
                'operation': 'fetch_accounts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_accounts',
                'status_code': e.response.status_code,
                'error': str(e)[:200]
            })
            
            if e.response.status_code == 404:
                return []
            elif e.response.status_code == 401:
                raise ValueError("Pipedrive authentication failed. Check API token.")
            elif e.response.status_code == 429:
                raise Exception("Rate limit hit. Please retry later.")
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_accounts',
                'error': 'timeout'
            })
            return []
    
    def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch persons (contacts) for organization.
        
        Args:
            account_id: Organization ID
            filters: Query filters
                - limit: Maximum results (default 50)
        
        Returns:
            List of normalized person dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': 'pipedrive',
            'operation': 'fetch_contacts',
            'account_id': account_id,
            'filters': filters
        })
        
        try:
            params = {
                "api_token": self.api_token,
                "limit": min(filters.get("limit", 50), 500)
            }
            
            # Get persons for organization
            response = self.client.get(f"/organizations/{account_id}/persons", params=params)
            response.raise_for_status()
            data = response.json()
            
            persons = data.get("data", []) if data.get("success") else []
            normalized = [self._normalize_person(person) for person in persons] if persons else []
            
            self._emit_event('fetch_complete', {
                'adapter': 'pipedrive',
                'operation': 'fetch_contacts',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_contacts',
                'status_code': e.response.status_code
            })
            
            if e.response.status_code == 404:
                return []
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_contacts',
                'error': 'timeout'
            })
            return []
    
    def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Fetch deals (opportunities) for organization.
        
        Args:
            account_id: Organization ID
            filters: Query filters
                - status: open, won, lost, all
                - limit: Maximum results (default 50)
        
        Returns:
            List of normalized deal dictionaries
        """
        filters = filters or {}
        self._emit_event('fetch_start', {
            'adapter': 'pipedrive',
            'operation': 'fetch_opportunities',
            'account_id': account_id,
            'filters': filters
        })
        
        try:
            params = {
                "api_token": self.api_token,
                "org_id": account_id,
                "limit": min(filters.get("limit", 50), 500)
            }
            
            status = filters.get("status", "all_not_deleted")
            if status == "open":
                params["status"] = "open"
            elif status == "won":
                params["status"] = "won"
            elif status == "lost":
                params["status"] = "lost"
            else:
                params["status"] = "all_not_deleted"
            
            # Make API request
            response = self.client.get("/deals", params=params)
            response.raise_for_status()
            data = response.json()
            
            deals = data.get("data", []) if data.get("success") else []
            normalized = [self._normalize_deal(deal) for deal in deals] if deals else []
            
            self._emit_event('fetch_complete', {
                'adapter': 'pipedrive',
                'operation': 'fetch_opportunities',
                'count': len(normalized)
            })
            
            return normalized
        
        except httpx.HTTPStatusError as e:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_opportunities',
                'status_code': e.response.status_code
            })
            
            if e.response.status_code == 404:
                return []
            else:
                raise
        
        except httpx.TimeoutException:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_opportunities',
                'error': 'timeout'
            })
            return []
    
    def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
        """Derive buying signals from deal activity.
        
        Args:
            account_id: Organization ID
        
        Returns:
            List of buying signal dictionaries with types:
                - deal_created: New deal created
                - deal_progression: Deal moved forward
                - activity_logged: Recent activity
        """
        self._emit_event('fetch_start', {
            'adapter': 'pipedrive',
            'operation': 'fetch_buying_signals',
            'account_id': account_id
        })
        
        try:
            signals = []
            
            # Get deals for organization
            deals = self.fetch_opportunities(account_id, {'status': 'open'})
            
            for deal in deals:
                # Deal created signal (recent deals)
                add_time = deal.get('metadata', {}).get('add_time')
                if add_time:
                    signals.append({
                        "type": "deal_created",
                        "description": f"New deal: {deal.get('name')}",
                        "confidence": 0.7,
                        "metadata": {
                            "deal_id": deal.get('id'),
                            "deal_name": deal.get('name'),
                            "value": deal.get('amount'),
                            "stage": deal.get('stage'),
                            "created_at": add_time
                        }
                    })
                
                # Deal progression signal (based on stage)
                stage = deal.get('stage', '')
                if any(keyword in stage.lower() for keyword in ['proposal', 'negotiation', 'closing']):
                    signals.append({
                        "type": "deal_progression",
                        "description": f"Deal in advanced stage: {stage}",
                        "confidence": 0.8,
                        "metadata": {
                            "deal_id": deal.get('id'),
                            "deal_name": deal.get('name'),
                            "stage": stage,
                            "value": deal.get('amount')
                        }
                    })
                
                # Activity logged signal
                update_time = deal.get('metadata', {}).get('update_time')
                if update_time:
                    signals.append({
                        "type": "activity_logged",
                        "description": f"Recent activity on deal: {deal.get('name')}",
                        "confidence": 0.6,
                        "metadata": {
                            "deal_id": deal.get('id'),
                            "deal_name": deal.get('name'),
                            "last_updated": update_time
                        }
                    })
            
            self._emit_event('fetch_complete', {
                'adapter': 'pipedrive',
                'operation': 'fetch_buying_signals',
                'signal_count': len(signals)
            })
            
            return signals
        
        except Exception as e:
            self._emit_event('fetch_error', {
                'adapter': 'pipedrive',
                'operation': 'fetch_buying_signals',
                'error': str(e)[:200]
            })
            return []
    
    def _normalize_organization(self, org: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Pipedrive organization to canonical format.
        
        Args:
            org: Raw Pipedrive organization data
        
        Returns:
            Normalized organization dictionary
        """
        address = org.get("address") or ""
        
        return {
            "id": str(org.get("id")),
            "name": org.get("name"),
            "domain": org.get("cc_email"),  # Pipedrive doesn't always have domain
            "industry": None,  # Not directly available
            "employee_count": org.get("people_count"),
            "revenue": None,  # Not directly available
            "location": {
                "city": address.split(',')[0] if address else None,
                "state": None,
                "country": org.get("address_country")
            },
            "metadata": {
                "owner_id": org.get("owner_id", {}).get("id") if isinstance(org.get("owner_id"), dict) else org.get("owner_id"),
                "open_deals_count": org.get("open_deals_count"),
                "closed_deals_count": org.get("closed_deals_count"),
                "active_flag": org.get("active_flag"),
                "source": "pipedrive"
            }
        }
    
    def _normalize_person(self, person: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Pipedrive person to canonical format.
        
        Args:
            person: Raw Pipedrive person data
        
        Returns:
            Normalized person dictionary
        """
        email = person.get("email", [{}])[0].get("value") if person.get("email") else None
        phone = person.get("phone", [{}])[0].get("value") if person.get("phone") else None
        
        return {
            "id": str(person.get("id")),
            "email": email,
            "first_name": person.get("first_name"),
            "last_name": person.get("last_name"),
            "name": person.get("name"),
            "title": None,  # Not directly available in basic API
            "phone": phone,
            "account_id": str(person.get("org_id", {}).get("value")) if person.get("org_id") else None,
            "account_name": person.get("org_name"),
            "metadata": {
                "owner_id": person.get("owner_id", {}).get("id") if isinstance(person.get("owner_id"), dict) else person.get("owner_id"),
                "active_flag": person.get("active_flag"),
                "open_deals_count": person.get("open_deals_count"),
                "source": "pipedrive"
            }
        }
    
    def _normalize_deal(self, deal: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize Pipedrive deal to canonical format.
        
        Args:
            deal: Raw Pipedrive deal data
        
        Returns:
            Normalized deal dictionary
        """
        return {
            "id": str(deal.get("id")),
            "name": deal.get("title"),
            "amount": deal.get("value"),
            "currency": deal.get("currency"),
            "stage": deal.get("stage_id"),
            "probability": deal.get("probability"),
            "close_date": deal.get("expected_close_date"),
            "account_id": str(deal.get("org_id", {}).get("value")) if deal.get("org_id") else None,
            "account_name": deal.get("org_name"),
            "metadata": {
                "status": deal.get("status"),
                "owner_id": deal.get("user_id", {}).get("id") if isinstance(deal.get("user_id"), dict) else deal.get("user_id"),
                "pipeline_id": deal.get("pipeline_id"),
                "add_time": deal.get("add_time"),
                "update_time": deal.get("update_time"),
                "won_time": deal.get("won_time"),
                "lost_time": deal.get("lost_time"),
                "source": "pipedrive"
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
