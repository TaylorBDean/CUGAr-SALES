# MCP & OpenAPI Governance Implementation Summary

## Overview

Implemented comprehensive governance system for MCP and OpenAPI tool execution with policy gates, per-tenant capability maps, and runtime health checks per AGENTS.md § 4 Sandbox Expectations.

## Components Delivered

### 1. Core Governance Engine
**Location**: `src/cuga/security/governance.py` (400+ lines)

**Key Features**:
- Action type classification (READ/WRITE/DELETE/FINANCIAL/EXTERNAL)
- Tool capability definitions with approval requirements and tenant restrictions
- Per-tenant capability maps with allowlist/denylist semantics
- Approval request lifecycle (PENDING → APPROVED/REJECTED/EXPIRED)
- Rate limiting per tenant/tool combination with sliding window
- Layered validation: tool registration → tenant map → tool restrictions → rate limits

**API**:
```python
from cuga.security import GovernanceEngine, create_governance_engine

engine = create_governance_engine()

# Validate tool call
engine.validate_tool_call(
    tool_name="slack_send_message",
    tenant="marketing",
    inputs={"channel": "#general", "message": "Hello"},
    context={"trace_id": "abc-def"}
)

# Request approval for high-risk actions
approval = engine.request_approval(
    tool_name="slack_send_message",
    tenant="marketing",
    inputs={"channel": "#general", "message": "Hello"},
    context={"trace_id": "abc-def"},
    request_id="req-123"
)

# Approve/reject
engine.approve_request("req-123", approved_by="admin@example.com")
engine.reject_request("req-123", reason="Not authorized")
```

### 2. Runtime Health Monitor
**Location**: `src/cuga/security/health_monitor.py` (450+ lines)

**Key Features**:
- Periodic tool discovery with concurrent pings (5 min default)
- Schema drift detection via SHA256 hash comparison
- TTL-based caching (1 hour default) with invalidation API
- Cold start protection (limit to 100 tools max)
- Health metrics summary (total/healthy/unhealthy tools, avg response time)

**API**:
```python
from cuga.security import RegistryHealthMonitor

monitor = RegistryHealthMonitor(
    discovery_interval_seconds=300,
    schema_check_interval_seconds=600,
    cache_ttl_seconds=3600,
    max_cold_start_tools=100
)

# Discovery
health_map = await monitor.discover_tools(tool_specs)

# Cache management
monitor.cache_tool_spec(spec, ttl_seconds=1800)
cached = monitor.get_cached_tool_spec("tool_name")
monitor.invalidate_cache("tool_name")  # or None for all

# Schema drift
drift = monitor.check_schema_drift(spec)
if drift:
    logger.warning(f"Schema changed: {drift['old_hash']} → {drift['new_hash']}")
```

### 3. Configuration Files

**Governance Capabilities**: `configurations/policies/governance_capabilities.yaml`
- 15+ tool capability definitions
- Action types: read/write/delete/financial/external
- Approval requirements with configurable timeouts (120s-600s)
- Tenant restrictions (allowed_tenants/denied_tenants)
- Rate limits (5-100 calls/min per tool)

**Tenant Capability Maps**: `configurations/policies/tenant_capabilities.yaml`
- 8 organizational roles:
  - **marketing**: Communication tools (Slack, email, Mailchimp), denied financial
  - **trading**: Financial tools (stock orders, payments), denied marketing
  - **engineering**: Full access (empty allowlist)
  - **support**: Read-only data access
  - **data_science**: Analytics and file I/O
  - **finance**: Payment processing
  - **content**: CMS tools (WordPress)
  - **analytics**: Read-only queries
- Per-tenant resource limits (max_concurrent_calls, budget_ceiling)

### 4. Governance Loader
**Location**: `src/cuga/security/governance_loader.py` (200+ lines)

Utilities for loading configurations and merging with existing profile policies:

```python
from cuga.security.governance_loader import (
    load_governance_capabilities,
    load_tenant_capability_maps,
    create_governance_engine,
    merge_governance_with_profile_policy,
)

# Load from YAML files
capabilities = load_governance_capabilities(path)
tenant_maps = load_tenant_capability_maps(path)

# Create engine
engine = create_governance_engine()

# Merge with profile policies (defense-in-depth)
merged_policy = merge_governance_with_profile_policy(
    profile_policy=profile_policy,
    governance_engine=engine,
    tenant="marketing"
)
```

### 5. Comprehensive Tests

**Governance Tests**: `tests/security/test_governance.py` (350+ lines, 20+ tests)
- Tool registration validation
- Tenant capability map enforcement
- Tool-level tenant restrictions
- Rate limiting with sliding window
- Approval lifecycle (PENDING → APPROVED/REJECTED/EXPIRED)
- Capability map logic (allowlist/denylist semantics)

**Health Monitor Tests**: `tests/security/test_health_monitor.py` (400+ lines, 25+ tests)
- Cache TTL enforcement
- Schema drift detection with SHA256
- Tool discovery with concurrent pings
- Cold start protection (100 tool limit)
- Metrics summary generation
- Cache invalidation (single/all)

**Coverage**: 35+ tests covering all major code paths

### 6. Documentation

**Governance Guide**: `docs/security/GOVERNANCE.md` (500+ lines)
- Architecture diagram with component relationships
- Detailed component specifications
- Configuration file schemas and examples
- Integration patterns for orchestrators
- Observability and logging guidance
- Security considerations and future enhancements

**Integration Example**: `examples/governance_integration.py` (350+ lines)
- Complete orchestrator integration example
- 6-stage execution pipeline:
  1. Cache check with TTL
  2. Schema drift detection
  3. Governance validation
  4. Approval gate (HITL)
  5. Rate limit enforcement
  6. Tool execution
- 4 realistic scenarios (marketing Slack send, file read, denied stock order, trading stock order)
- Structured logging with trace_id propagation

### 7. Module Exports

**Security Module**: `src/cuga/security/__init__.py`
Updated to export all governance components:
- `ActionType`, `ApprovalStatus`, `ApprovalRequest`
- `ToolCapability`, `TenantCapabilityMap`, `GovernanceEngine`
- `HealthCheckResult`, `SchemaSignature`, `RegistryHealthMonitor`
- Loader utilities

## Key Design Decisions

### 1. Layered Access Control
Four validation layers provide defense-in-depth:
1. **Tool Registration**: Tool must exist in capability map
2. **Tenant Map**: Tenant allowlist/denylist filters
3. **Tool Restrictions**: Tool-level allowed_tenants/denied_tenants
4. **Rate Limits**: Per tenant/tool sliding window

### 2. Action Type Taxonomy
Severity-based classification guides approval requirements:
- **READ**: Auto-approved (file_read, database_query)
- **WRITE**: Requires approval (Slack send, file write)
- **DELETE**: Requires approval with longer timeout (file delete)
- **FINANCIAL**: Requires approval with short timeout (stock orders, payments)
- **EXTERNAL**: Requires approval (OpenAPI POST/DELETE)

### 3. Approval Expiration
Time-bounded approval requests prevent stale approvals:
- READ: N/A (auto-approved)
- WRITE: 300s (5 minutes)
- DELETE: 600s (10 minutes)
- FINANCIAL: 120s (2 minutes)
- EXTERNAL: 300s (5 minutes)

### 4. Cold Start Protection
Discovery limited to first 100 tools to prevent:
- Timeout cascades on huge registries
- Memory exhaustion from concurrent pings
- Network congestion from parallel health checks

### 5. Schema Drift Detection
SHA256 hash comparison of sorted schemas enables:
- Deterministic drift detection across restarts
- Baseline capture on first observation
- Alert on breaking changes (hash mismatch)
- Cache invalidation on schema updates

## Integration Points

### Orchestrator Integration
```python
# 1. Initialize at startup
governance_engine = create_governance_engine()
health_monitor = RegistryHealthMonitor()

# 2. Run discovery on startup
await health_monitor.discover_tools(all_tool_specs)

# 3. Before tool execution
governance_engine.validate_tool_call(tool_name, tenant, inputs, context)

# 4. Approval gate (if required)
if capability.requires_approval:
    approval = governance_engine.request_approval(...)
    status = await wait_for_approval(approval.request_id)
    if status != ApprovalStatus.APPROVED:
        raise PolicyViolation(...)

# 5. Execute tool
result = registry.execute(tool_name, inputs, context)
```

### Profile Policy Integration
```python
# Merge governance with existing profile policies
merged = merge_governance_with_profile_policy(
    profile_policy=load_profile_policy("default"),
    governance_engine=engine,
    tenant="marketing"
)

# Result: tools must be allowed by BOTH profile AND tenant
# allowed_tools = (profile_allowed ∩ tenant_allowed) - tenant_denied
```

### Observability Integration
```python
# Structured logging with trace_id
logger.info(
    "Governance validation passed",
    extra={
        "tool": tool_name,
        "tenant": tenant,
        "action_type": capability.action_type.value,
        "trace_id": context["trace_id"]
    }
)

# OpenTelemetry spans
with tracer.start_as_current_span("governance.validate_tool_call") as span:
    span.set_attribute("tool.name", tool_name)
    span.set_attribute("tenant", tenant)
    governance_engine.validate_tool_call(...)
```

## Testing Strategy

### Unit Tests
- ✅ Governance validation rules (tool/tenant restrictions)
- ✅ Rate limiting enforcement (sliding window)
- ✅ Approval lifecycle transitions
- ✅ Cache TTL and expiration
- ✅ Schema drift detection (hash comparison)
- ✅ Cold start protection (tool count limit)

### Integration Tests
- Example orchestrator integration (examples/governance_integration.py)
- 4 realistic scenarios with trace_id propagation
- Mock registry for deterministic testing

### Test Coverage
- **Governance**: 20+ tests, 350+ lines
- **Health Monitor**: 25+ tests, 400+ lines
- **Total**: 35+ tests covering all major code paths

## Security Considerations

### Defense in Depth
Governance works alongside existing security controls:
- Profile policies (AGENTS.md § 3 Profile Isolation)
- Sandbox restrictions (AGENTS.md § 4 Sandbox Expectations)
- Import allowlists (cuga.modular.tools.* only)
- HTTP client enforcement (SafeClient with timeouts)
- Secrets management (env-only, no hardcoded)

### Fail-Safe Defaults
- Unknown tools rejected by default
- Approval timeouts result in rejection (not approval)
- Empty allowed_tenants = allow all (explicit opt-in required)
- Denied tenants override allowed tenants
- Rate limits enforced before execution

### Audit Trail
All governance decisions logged with:
- Tool name and tenant
- Action type and approval requirement
- Approval status and approver identity
- Rate limit violations
- Schema drift events
- trace_id for forensic analysis

## Performance Characteristics

### Cache Hit Performance
- Cache lookup: O(1) dict access
- TTL check: Single datetime comparison
- No network I/O on cache hit

### Cache Miss Performance
- Registry lookup: Depends on registry implementation
- Schema signature: O(n) for schema dict sorting + SHA256
- Cache insertion: O(1) dict assignment

### Discovery Performance
- Concurrent pings: O(1) time with async/await
- Cold start limit: Max 100 tools prevents unbounded execution
- Response time tracking: Minimal overhead (<1ms)

### Rate Limiting Performance
- Sliding window: O(n) cleanup where n = calls in last minute
- Worst case: 100 calls/min = 100 comparisons
- Typical case: <10 calls/min = negligible overhead

## Future Enhancements

### High Priority
- [ ] Async approval webhooks (Slack/Teams integration)
- [ ] Budget enforcement (track and enforce budget_ceiling)
- [ ] Concurrent call limits (enforce max_concurrent_calls)

### Medium Priority
- [ ] Approval delegation (role-based routing)
- [ ] Audit log export (SIEM integration)
- [ ] Dynamic capability updates (hot-reload without restart)

### Low Priority
- [ ] Health check telemetry (Prometheus/Grafana metrics)
- [ ] Approval workflow engine (multi-stage approvals)
- [ ] Tool recommendation engine (suggest allowed alternatives)

## Documentation Updates

### README.md
Added governance overview to "Security & Safe Execution" section:
- Policy gates for write/delete/financial actions
- Per-tenant capability maps (8 organizational roles)
- Runtime health checks (discovery/drift/cache)
- Reference to docs/security/GOVERNANCE.md

### CHANGELOG.md
Added comprehensive vNext entry:
- Governance engine implementation (400+ lines)
- Health monitor implementation (450+ lines)
- Configuration files (governance_capabilities.yaml, tenant_capabilities.yaml)
- Governance loader utilities (200+ lines)
- Test coverage (35+ tests, 750+ lines)
- Documentation (GOVERNANCE.md, 500+ lines)
- Integration example (governance_integration.py, 350+ lines)

### AGENTS.md
No changes required—governance system aligns with existing § 3 Profile Isolation and § 4 Sandbox Expectations guardrails.

## Migration Path

### For New Projects
1. Copy configuration files to `configurations/policies/`
2. Initialize governance engine at orchestrator startup
3. Call `validate_tool_call()` before tool execution
4. Implement approval handler for HITL gates

### For Existing Projects
1. Add governance configs alongside existing profile policies
2. Use `merge_governance_with_profile_policy()` for defense-in-depth
3. Gradually migrate approval logic to governance engine
4. Monitor governance validation failures and adjust capability maps

## Success Criteria

✅ **Policy Gates**: Approval points for write/delete/financial actions implemented
✅ **Tenant Capability Maps**: 8 organizational roles with tool allowlists/denylists configured
✅ **Runtime Health Checks**: Tool discovery, schema drift detection, cache TTLs operational
✅ **Layered Validation**: 4-stage access control (registration → tenant → tool → rate limit)
✅ **Comprehensive Tests**: 35+ tests covering governance and health monitoring
✅ **Documentation**: 500+ line guide with architecture, integration patterns, examples
✅ **Example Integration**: Working orchestrator example with 4 realistic scenarios
✅ **Module Exports**: All components accessible via `from cuga.security import ...`

## References

- [AGENTS.md § 3 Profile Isolation](../../AGENTS.md#3-profile-isolation)
- [AGENTS.md § 4 Sandbox Expectations](../../AGENTS.md#4-sandbox-expectations)
- [docs/security/GOVERNANCE.md](../../docs/security/GOVERNANCE.md)
- [examples/governance_integration.py](../../examples/governance_integration.py)
- [tests/security/test_governance.py](../../tests/security/test_governance.py)
- [tests/security/test_health_monitor.py](../../tests/security/test_health_monitor.py)
