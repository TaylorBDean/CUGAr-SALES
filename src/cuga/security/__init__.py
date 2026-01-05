"""
Security module for CUGAR Agent.

Provides:
- SafeClient: HTTP client with enforced timeouts and retry logic
- AsyncSafeClient: Async variant of SafeClient
- Secrets management: env-only enforcement and validation
- URL/secret redaction for safe logging
- Governance: Policy gates, approval flows, tenant capability maps
- Health monitoring: Tool discovery, schema drift detection, cache TTLs

Per AGENTS.md canonical requirements.
"""

from cuga.security.http_client import (
    SafeClient,
    AsyncSafeClient,
    DEFAULT_TIMEOUT,
)

from cuga.security.secrets import (
    is_sensitive_key,
    redact_dict,
    validate_env_parity,
    enforce_env_only_secrets,
    detect_hardcoded_secrets,
    validate_startup_env,
)

from cuga.security.governance import (
    ActionType,
    ApprovalStatus,
    ApprovalRequest,
    ToolCapability,
    TenantCapabilityMap,
    GovernanceEngine,
)

from cuga.security.health_monitor import (
    HealthCheckResult,
    SchemaSignature,
    CachedToolSpec,
    RegistryHealthMonitor,
)

from cuga.security.governance_loader import (
    load_governance_capabilities,
    load_tenant_capability_maps,
    create_governance_engine,
    merge_governance_with_profile_policy,
)

__all__ = [
    # HTTP client
    "SafeClient",
    "AsyncSafeClient",
    "DEFAULT_TIMEOUT",
    # Secrets management
    "is_sensitive_key",
    "redact_dict",
    "validate_env_parity",
    "enforce_env_only_secrets",
    "detect_hardcoded_secrets",
    "validate_startup_env",
    # Governance
    "ActionType",
    "ApprovalStatus",
    "ApprovalRequest",
    "ToolCapability",
    "TenantCapabilityMap",
    "GovernanceEngine",
    # Health monitoring
    "HealthCheckResult",
    "SchemaSignature",
    "CachedToolSpec",
    "RegistryHealthMonitor",
    # Governance loader
    "load_governance_capabilities",
    "load_tenant_capability_maps",
    "create_governance_engine",
    "merge_governance_with_profile_policy",
]

