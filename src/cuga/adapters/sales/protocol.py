"""
Adapter protocol for vendor integrations with hot-swap support.

All vendors (CRM, enrichment, intent) implement VendorAdapter protocol.
Supports mock/live/hybrid modes with zero-downtime switching.
"""

from typing import Protocol, Dict, Any, List, Optional
from enum import Enum
from dataclasses import dataclass, field


class AdapterMode(str, Enum):
    """Adapter execution mode"""
    MOCK = "mock"      # Use local fixtures (no API calls)
    LIVE = "live"      # Call real vendor API
    HYBRID = "hybrid"  # Read live, write mock (safe testing)


@dataclass
class AdapterConfig:
    """Adapter configuration with credentials and execution context.
    
    Provides both legacy trace_id access and modern ExecutionContext integration.
    Adapters should prefer execution_context when available for full observability.
    
    Attributes:
        mode: Adapter execution mode (mock/live/hybrid)
        credentials: Vendor-specific credentials dict
        trace_id: Legacy trace identifier (deprecated, use execution_context)
        execution_context: Optional canonical ExecutionContext with full observability
        metadata: Additional adapter metadata (for backward compatibility)
    """
    mode: AdapterMode
    credentials: Dict[str, str]
    trace_id: Optional[str] = None
    execution_context: Optional[Any] = None  # ExecutionContext from cuga.orchestrator.protocol
    metadata: Dict[str, Any] = field(default_factory=dict)


class VendorAdapter(Protocol):
    """
    Canonical interface for all vendor integrations.
    
    All adapters MUST implement:
    - fetch_accounts() - Get account list
    - fetch_contacts() - Get contacts for account
    - fetch_opportunities() - Get opportunities for account
    - get_mode() - Current mode (mock/live/hybrid)
    - validate_connection() - Test credentials/connection
    """
    
    def fetch_accounts(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch accounts matching filters"""
        ...
    
    def fetch_contacts(
        self,
        account_id: str
    ) -> List[Dict[str, Any]]:
        """Fetch contacts for account"""
        ...
    
    def fetch_opportunities(
        self,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch opportunities (all or for specific account)"""
        ...
    
    def get_mode(self) -> AdapterMode:
        """Get current adapter mode"""
        ...
    
    def validate_connection(self) -> bool:
        """Test connection (returns True for mock mode)"""
        ...
