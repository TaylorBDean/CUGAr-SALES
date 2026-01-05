"""
CRM and external service adapters for CUGAr-SALES.

CRITICAL: Adapters are LATE-BOUND and REMOVABLE.
Capabilities (src/cuga/modular/tools/sales/) MUST NOT depend on adapters.
Adapters bind to capabilities, not the reverse.

Design Principles:
- Adapters are optional (capabilities work offline without them)
- Adapters are swappable (change vendor without changing capability code)
- Adapters use SafeClient (enforced timeouts, retries, redaction per AGENTS.md)
- Adapters are env-only (no hardcoded secrets)
- Adapters are testable (mock responses, no live API calls in tests)

Hot-Swap Architecture (v1.2.0):
- Mock mode: YAML fixtures, zero config required
- Live mode: Real APIs with frontend-managed credentials
- Config-driven: Frontend API writes configs/adapters.yaml
- Factory pattern: create_adapter() auto-selects mode
- Zero code changes: Tools automatically use configured adapter
"""

# Sales adapter system (hot-swap mock/live)
from .sales.protocol import VendorAdapter, AdapterMode, AdapterConfig
from .sales.factory import (
    create_adapter,
    get_adapter_status,
    create_ibm_adapter,
    create_salesforce_adapter,
    create_hubspot_adapter,
)
from .sales.mock_adapter import MockAdapter

__all__ = [
    # Protocol types
    "VendorAdapter",
    "AdapterMode",
    "AdapterConfig",
    
    # Factory functions
    "create_adapter",
    "get_adapter_status",
    
    # Convenience constructors
    "create_ibm_adapter",
    "create_salesforce_adapter",
    "create_hubspot_adapter",
    
    # Base implementations
    "MockAdapter",
]
