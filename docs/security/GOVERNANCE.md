# MCP & OpenAPI Governance System

## Overview

The governance system provides defense-in-depth policy enforcement for MCP and OpenAPI tool execution with:

1. **Policy Gates**: Approval points for write/delete/financial actions
2. **Per-Tenant Capability Maps**: Tool access control by organizational role
3. **Runtime Health Checks**: Tool discovery ping, schema drift detection, and cache TTLs

This system integrates with the existing profile-based policy framework (AGENTS.md § 3 Profile Isolation) to provide layered security controls.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Request Entry Point                     │
│                   (CLI / FastAPI / MCP)                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                   GovernanceEngine                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Tool         │  │ Tenant       │  │ Approval         │  │
│  │ Capabilities │  │ Capability   │  │ Handler          │  │
│  │              │  │ Maps         │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│           │                 │                  │            │
│           └─────────────────┴──────────────────┘            │
│                            │                                │
│                   validate_tool_call()                      │
│                   request_approval()                        │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│              RegistryHealthMonitor                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Tool Cache   │  │ Schema       │  │ Health           │  │
│  │ (TTL-based)  │  │ Signatures   │  │ Check Results    │  │
│  │              │  │ (drift)      │  │                  │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│           │                 │                  │            │
│           └─────────────────┴──────────────────┘            │
│                            │                                │
│                   discover_tools()                          │
│                   check_schema_drift()                      │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
                  Tool Execution Layer
                  (existing registry)
```

## Components

### 1. Policy Gates (Approval Points)

**Location**: `src/cuga/security/governance.py`

Policy gates enforce human-in-the-loop (HITL) approval for high-risk actions:

- **READ**: Non-mutating queries (e.g., list files, get user) → auto-approve
- **WRITE**: Mutating operations (e.g., send Slack message, update record) → requires approval
- **DELETE**: Destructive operations (e.g., delete file, drop table) → requires approval with longer timeout
- **FINANCIAL**: Financial transactions (e.g., place order, transfer funds) → requires approval with short timeout
- **EXTERNAL**: External API calls with side effects → requires approval

#### ToolCapability

Defines governance rules per tool:

```python
ToolCapability(
    name="slack_send_message",
    action_type=ActionType.WRITE,
    requires_approval=True,              # HITL gate
    approval_timeout_seconds=300,        # 5 minutes
    allowed_tenants={"marketing", "support"},
    denied_tenants=set(),
    max_rate_per_minute=10,             # Rate limiting
    metadata={"risk_level": "medium"}
)
```

#### ApprovalRequest

Tracks pending approval requests:

```python
ApprovalRequest(
    request_id="req-123",
    tool_name="slack_send_message",
    action_type=ActionType.WRITE,
    tenant="marketing",
    inputs={"channel": "#general", "message": "Hello"},
    context={"trace_id": "abc-def"},
    status=ApprovalStatus.PENDING,      # PENDING → APPROVED/REJECTED/EXPIRED
    expires_at=datetime.utcnow() + timedelta(seconds=300)
)
```

#### Usage Example

```python
from cuga.security.governance import GovernanceEngine

# Initialize engine
engine = GovernanceEngine(capabilities, tenant_maps)

# Validate tool call
try:
    engine.validate_tool_call(
        tool_name="slack_send_message",
        tenant="marketing",
        inputs={"channel": "#general", "message": "Hello"},
        context={"trace_id": "abc-def"}
    )
except PolicyViolation as e:
    logger.error(f"Governance violation: {e}")
    return

# Request approval if needed
approval = engine.request_approval(
    tool_name="slack_send_message",
    tenant="marketing",
    inputs={"channel": "#general", "message": "Hello"},
    context={"trace_id": "abc-def"},
    request_id="req-123"
)

if approval.status == ApprovalStatus.PENDING:
    # Wait for human approval (webhook, polling, etc.)
    # ...
    status = engine.get_approval_status("req-123")

if status == ApprovalStatus.APPROVED:
    # Execute tool
    result = execute_tool(...)
```

### 2. Per-Tenant Capability Maps

**Location**: `configurations/policies/tenant_capabilities.yaml`

Capability maps define which tools each tenant (organizational role) can access:

```yaml
tenant_maps:
  marketing:
    allowed_tools:
      - slack_send_message
      - email_send
      - mailchimp_campaign
      - file_read
    denied_tools:
      - stock_order_place
      - payment_process
      - database_mutate
    max_concurrent_calls: 15
    budget_ceiling: 200
    
  trading:
    allowed_tools:
      - stock_order_place
      - payment_process
      - database_query
    denied_tools:
      - slack_send_message
      - mailchimp_campaign
    max_concurrent_calls: 20
    budget_ceiling: 500
    
  engineering:
    allowed_tools: []  # Empty = all tools allowed
    denied_tools: []
    max_concurrent_calls: 50
    budget_ceiling: 1000
```

#### Access Control Logic

1. **Tenant Denylist**: If tool in `denied_tools` → reject
2. **Tenant Allowlist**: If `allowed_tools` is non-empty and tool not in list → reject
3. **Tool-Level Tenant Restrictions**: Check tool's `allowed_tenants` / `denied_tenants`
4. **Rate Limits**: Enforce `max_rate_per_minute` per tenant/tool combination

#### Integration with Profile Policies

The governance system works alongside existing profile policies (AGENTS.md § 3):

```python
from cuga.security.governance_loader import merge_governance_with_profile_policy

# Load profile policy (from configurations/policies/default.yaml)
profile_policy = load_profile_policy("default")

# Merge with governance rules
merged = merge_governance_with_profile_policy(
    profile_policy=profile_policy,
    governance_engine=engine,
    tenant="marketing"
)

# Result: only tools allowed by BOTH profile AND tenant
# allowed_tools = (profile_allowed ∩ tenant_allowed) - tenant_denied
```

### 3. Runtime Health Checks

**Location**: `src/cuga/security/health_monitor.py`

Health monitoring prevents cold-start delays and detects schema drift:

#### Tool Discovery (Ping)

Periodic lightweight health checks to verify tool availability:

```python
monitor = RegistryHealthMonitor(
    discovery_interval_seconds=300,      # Ping every 5 minutes
    schema_check_interval_seconds=600,   # Check drift every 10 minutes
    cache_ttl_seconds=3600,             # Cache specs for 1 hour
    max_cold_start_tools=100            # Limit huge registry lists
)

# Discovery ping (concurrent for all tools)
health_map = await monitor.discover_tools(tool_specs)

for tool_name, result in health_map.items():
    if not result.is_healthy:
        logger.warning(f"Tool '{tool_name}' unhealthy: {result.error_message}")
```

#### Schema Drift Detection

Detects when tool input schemas change (breaking changes):

```python
# Capture baseline schema signature
monitor.capture_schema_signature(tool_spec)

# Later: check for drift
drift = monitor.check_schema_drift(tool_spec)

if drift:
    logger.warning(
        f"Schema drift detected for '{drift['tool']}': "
        f"hash changed from {drift['old_hash']} to {drift['new_hash']}"
    )
    # Alert operators, invalidate cache, etc.
```

Schema signatures use SHA256 hashes of sorted schema dicts for deterministic comparison.

#### Cache TTLs

Tool specs are cached with TTL to avoid repeated registry queries:

```python
# Cache tool spec
monitor.cache_tool_spec(tool_spec, ttl_seconds=1800)

# Retrieve from cache
cached_spec = monitor.get_cached_tool_spec("tool_name")
if cached_spec is None:
    # Cache miss or expired, fetch from registry
    spec = registry.get("tool_name")
    monitor.cache_tool_spec(spec)
```

Cache invalidation:

```python
# Invalidate single tool
monitor.invalidate_cache("tool_name")

# Invalidate all
monitor.invalidate_cache()
```

#### Cold Start Protection

When loading huge registries (100+ tools), limit discovery to prevent timeouts:

```python
# Automatically truncates to max_cold_start_tools
health_map = await monitor.discover_tools(all_tool_specs)
# Only first 100 tools pinged
```

## Configuration Files

### Tool Capabilities

**File**: `configurations/policies/governance_capabilities.yaml`

```yaml
capabilities:
  slack_send_message:
    action_type: write
    requires_approval: true
    approval_timeout_seconds: 300
    allowed_tenants: ["marketing", "support"]
    max_rate_per_minute: 10
    
  file_delete:
    action_type: delete
    requires_approval: true
    approval_timeout_seconds: 600
    allowed_tenants: ["engineering"]
    max_rate_per_minute: 5
    
  stock_order_place:
    action_type: financial
    requires_approval: true
    approval_timeout_seconds: 120
    allowed_tenants: ["trading"]
    denied_tenants: ["marketing", "support"]
    max_rate_per_minute: 5
```

### Tenant Capability Maps

**File**: `configurations/policies/tenant_capabilities.yaml`

```yaml
tenant_maps:
  marketing:
    allowed_tools: [slack_send_message, email_send, mailchimp_campaign]
    denied_tools: [stock_order_place, payment_process]
    max_concurrent_calls: 15
    budget_ceiling: 200
    
  trading:
    allowed_tools: [stock_order_place, payment_process, database_query]
    denied_tools: [slack_send_message, mailchimp_campaign]
    max_concurrent_calls: 20
    budget_ceiling: 500
```

## Integration with Orchestrator

The governance engine should be invoked from the orchestrator before tool execution:

```python
from cuga.security.governance_loader import create_governance_engine
from cuga.security.health_monitor import RegistryHealthMonitor

# Initialize at orchestrator startup
governance_engine = create_governance_engine()
health_monitor = RegistryHealthMonitor()

# In orchestrator's tool execution path:
def execute_tool(tool_name: str, inputs: dict, context: dict):
    tenant = context.get("tenant", "default")
    trace_id = context.get("trace_id")
    
    # 1. Check cache first
    cached_spec = health_monitor.get_cached_tool_spec(tool_name)
    if cached_spec is None:
        spec = registry.get(tool_name)
        health_monitor.cache_tool_spec(spec)
        
        # Check for schema drift
        drift = health_monitor.check_schema_drift(spec)
        if drift:
            logger.warning(f"Schema drift: {drift}")
    
    # 2. Governance validation
    try:
        governance_engine.validate_tool_call(
            tool_name=tool_name,
            tenant=tenant,
            inputs=inputs,
            context=context
        )
    except PolicyViolation as e:
        logger.error(f"Governance violation: {e}", extra={"trace_id": trace_id})
        raise
    
    # 3. Approval gate (if required)
    capability = governance_engine.capabilities[tool_name]
    if capability.requires_approval:
        approval = governance_engine.request_approval(
            tool_name=tool_name,
            tenant=tenant,
            inputs=inputs,
            context=context,
            request_id=f"{trace_id}-approval"
        )
        
        if approval.status == ApprovalStatus.PENDING:
            # Wait for approval (webhook, polling, etc.)
            status = await wait_for_approval(approval.request_id)
            if status != ApprovalStatus.APPROVED:
                raise PolicyViolation(
                    profile=tenant,
                    tool=tool_name,
                    code="approval_rejected",
                    message=f"Approval rejected or expired"
                )
    
    # 4. Execute tool
    result = registry.execute(tool_name, inputs, context)
    return result
```

## Testing

Comprehensive tests cover:

- ✅ Tool registration validation
- ✅ Tenant capability map enforcement
- ✅ Tool-level tenant restrictions
- ✅ Rate limiting per tenant/tool
- ✅ Approval request lifecycle (pending → approved/rejected/expired)
- ✅ Cache TTL and expiration
- ✅ Schema drift detection
- ✅ Health check discovery with cold start protection

Run tests:

```bash
uv run pytest tests/security/test_governance.py -v
uv run pytest tests/security/test_health_monitor.py -v
```

## Observability

All governance decisions are logged with structured context:

```python
logger.info(
    "Governance validation passed",
    extra={
        "tool": tool_name,
        "tenant": tenant,
        "action_type": capability.action_type.value,
        "requires_approval": capability.requires_approval,
        "trace_id": context.get("trace_id")
    }
)

logger.warning(
    "Schema drift detected",
    extra={
        "tool": spec.alias,
        "old_hash": old_signature.schema_hash,
        "new_hash": new_signature.schema_hash,
        "detected_at": datetime.utcnow().isoformat()
    }
)
```

Integrate with existing observability stack (Langfuse, OpenTelemetry) by emitting spans:

```python
with tracer.start_as_current_span("governance.validate_tool_call") as span:
    span.set_attribute("tool.name", tool_name)
    span.set_attribute("tenant", tenant)
    span.set_attribute("action_type", capability.action_type.value)
    
    governance_engine.validate_tool_call(...)
```

## Security Considerations

1. **Defense in Depth**: Governance works alongside profile policies (AGENTS.md § 3) and sandbox restrictions (AGENTS.md § 4)
2. **Fail-Safe Defaults**: Unknown tools are rejected by default; approval timeouts result in rejection
3. **Audit Trail**: All governance decisions logged with trace_id for forensic analysis
4. **Rate Limiting**: Prevents abuse and runaway tool execution
5. **Approval Expiration**: Time-bounded approval requests prevent stale approvals
6. **Schema Drift Detection**: Alerts on breaking changes to tool interfaces
7. **Cold Start Protection**: Limits tool discovery to prevent timeouts on huge registries

## Future Enhancements

- [ ] **Async Approval Webhooks**: Integrate with Slack/Teams for HITL approval workflows
- [ ] **Budget Enforcement**: Track and enforce `budget_ceiling` per tenant
- [ ] **Concurrent Call Limits**: Enforce `max_concurrent_calls` per tenant
- [ ] **Approval Delegation**: Role-based approval routing (e.g., financial tools → finance team)
- [ ] **Audit Log Export**: Export governance decisions to SIEM/compliance systems
- [ ] **Dynamic Capability Updates**: Hot-reload capability maps without restart
- [ ] **Health Check Telemetry**: Expose metrics endpoint for monitoring (Prometheus/Grafana)

## References

- [AGENTS.md § 3 Profile Isolation](../../AGENTS.md#3-profile-isolation)
- [AGENTS.md § 4 Sandbox Expectations](../../AGENTS.md#4-sandbox-expectations)
- [Policy Enforcement](../agents/policy.py)
- [Tool Registry](../tools/registry.py)
- [MCP Registry](../mcp/registry.py)
