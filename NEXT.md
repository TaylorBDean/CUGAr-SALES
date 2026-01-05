# Architecture Review & Future Roadmap

**Status**: Architectural Review  
**Date**: 2025-12-31  
**Reviewer**: Principal Engineer  
**Scope**: Repository-wide evolution planning

---

## Overview

This document captures architectural questions that inform future design decisions, followed by prioritized features and evolution opportunities for the cugar-agent system. The system has achieved solid foundational abstractions (OrchestratorProtocol, AgentLifecycle, ExecutionContext, RoutingAuthority, ConfigResolver) with clear separation of concerns and deterministic local-first execution.

**Current Maturity Assessment**:
- **Orchestration Core**: Production-ready contracts with comprehensive protocol definitions
- **Agent Lifecycle**: Well-defined state machine with clear ownership boundaries
- **Configuration**: Unified resolution with explicit precedence (Phases 3-4 complete)
- **Testing**: ~45% architectural coverage; orchestrator/agents tested, tools/memory/config gaps
- **Documentation**: Strong (canonical contracts, onboarding guides, execution narrative)
- **Observability**: Interface-defined but minimally implemented
- **Memory/RAG**: Basic implementation, deterministic fallback, limited retention policies
- **Security**: Sandbox profiles declared but enforcement incomplete

**Key Architectural Strengths**:
1. Protocol-driven contracts prevent implicit behavior
2. Local-first execution with deterministic defaults
3. Profile-based isolation boundaries
4. Explicit failure modes and retry semantics
5. Immutable execution context with trace continuity

**Critical Gaps Blocking Production Scale**:
1. Tool registry security boundaries untested (70% gap, 16h estimated)
2. Memory data integrity untested (80% gap, 24h estimated)
3. Configuration precedence untested (100% gap, 16h estimated)
4. Observability integration untested (100% gap, 24h estimated)
5. Async execution model incomplete (mixing sync/async, no backpressure)
6. Sandbox enforcement not validated end-to-end

---

## Phase 1: Open Questions

### Scale & Complexity Growth

**Q1: What is the target request throughput and concurrency level for production deployments?**

**Why it matters**: Current architecture uses thread-safe round-robin with in-memory state. If targeting <100 req/s, current design sufficient. If targeting >1000 req/s:
- Need distributed coordinator with external state (Redis/etcd)
- Round-robin becomes bottleneck; need load-aware routing
- Memory backend needs horizontal scaling (currently single-instance FAISS/Chroma/Qdrant)
- Trace propagation needs distributed tracing infrastructure (current trace_id is string, no span context)

**Architectural impact**: 
- LOW if <100 req/s (current design holds)
- HIGH if >1000 req/s (requires distributed orchestrator, external state, partitioned memory)

**Follow-up questions**:
- Expected peak concurrent orchestrations?
- Acceptable latency budget per request (p50, p95, p99)?
- Memory retention window (1 day, 1 week, indefinite)?

---

**Q2: How complex will orchestration graphs become?**

**Why it matters**: Current PlannerAgent generates linear step sequences. If workflows remain linear (max 10 steps), current design sufficient. If workflows become DAGs with:
- Parallel step execution (fan-out/fan-in)
- Conditional branching (if/then/else logic)
- Loops (retry-until-success, batch processing)
- Sub-orchestrations (nested agent calls)

Then need graph execution engine (LangGraph integration mentioned in ROADMAP.md but not implemented).

**Architectural impact**:
- LOW if workflows stay linear (current PlannerAgent holds)
- HIGH if requiring DAG orchestration (need graph engine, cycle detection, parallel executor)

**Current evidence**: `AgentPlan` is `List[dict]` (linear), `WorkerAgent.execute()` iterates sequentially. No parallel execution infrastructure.

**Follow-up questions**:
- Will workflows require parallel tool execution?
- Are conditional branches needed (route based on previous step results)?
- Should orchestrator support sub-orchestrations (agent calling agent)?

---

**Q3: What is the stability vs. experimentation tradeoff for agent behaviors?**

**Why it matters**: System design emphasizes deterministic behavior (`temperature=0.0` by default, hashing embedder, offline-first). If prioritizing:
- **Stability**: Lock down model versions, freeze tool schemas, strict policy enforcement
- **Experimentation**: Hot-swap models, A/B test prompts, evolving tool signatures

These require different architectures.

**Architectural impact**:
- Stability: Current design excellent (deterministic defaults, explicit contracts, policy enforcement)
- Experimentation: Need versioned tool registry, model A/B testing, prompt variant tracking, observability for experiment analysis

**Current state**: Strong stability bias (deterministic defaults, frozen contracts), limited experimentation infrastructure (no A/B framework, no prompt versioning).

**Follow-up questions**:
- Should tool schemas be versioned (allow gradual migration)?
- Is model A/B testing required (same request, different models)?
- Should prompts be externalizable (edit without code changes)?

---

### Flexibility & Constraints

**Q4: Where is flexibility intentionally limited, and why?**

**Why it matters**: Several design decisions restrict flexibility:
1. Tool imports restricted to `cuga.modular.tools.*` (security boundary)
2. Synchronous execution model (no async tool handlers)
3. Single embedder per VectorMemory (no multi-embedding retrieval)
4. Profile-scoped memory isolation (no cross-profile queries)
5. Budget enforcement as middleware (no per-tool budgets)

Understanding *why* these limits exist determines whether relaxing them is safe.

**Architectural impact**:
- If limits are security boundaries → must preserve (or require major security review)
- If limits are simplicity tradeoffs → can relax incrementally with safeguards

**Current uncertainty**:
- Is tool import restriction enforced at runtime (dynamic loader check)?
- Can async tool handlers be added without breaking WorkerAgent contract?
- Should cross-profile queries be allowed with explicit authorization?

**Follow-up questions**:
- Which constraints are security-critical vs. simplicity tradeoffs?
- What is the risk tolerance for relaxing constraints (fail-safe vs. fail-secure)?
- Should policy enforcement be pluggable (allow custom policy engines)?

---

**Q5: What security, privacy, or compliance requirements constrain architecture?**

**Why it matters**: Repository emphasizes security-first design (sandboxes, allowlists, budget caps, PII redaction). If deploying in regulated environments (HIPAA, GDPR, SOC2):
- May require audit logs with immutability guarantees
- May need data residency constraints (memory must stay in-region)
- May require access control (RBAC for tools/profiles)
- May need encryption at rest (memory/config storage)
- May require provenance tracking (who authorized which tool call)

These requirements fundamentally shape data flow and storage architecture.

**Architectural impact**:
- LOW if self-hosted non-regulated environments
- HIGH if regulated (need audit infrastructure, access control, encryption, compliance reporting)

**Current state**: Basic security (sandboxes, redaction, budget caps), no audit log infrastructure, no RBAC, no encryption at rest.

**Follow-up questions**:
- Will system handle PII/PHI/payment data?
- Are audit logs required for compliance?
- Is multi-tenancy required (isolated customer environments)?
- Should tool/profile access be role-based?

---

### Testing & Observability

**Q6: What observability granularity is required for production debugging?**

**Why it matters**: Current BaseEmitter interface is minimal (`emit(payload: Dict)`). If debugging production issues requires:
- Span-level tracing (OpenTelemetry semantic conventions)
- Structured metrics (Prometheus/StatsD)
- Distributed tracing across services (trace context propagation)
- Replay-driven debugging (capture inputs, replay deterministically)
- Real-time alerting (anomaly detection, threshold alerts)

Then need comprehensive observability implementation, not just interface.

**Architectural impact**:
- LOW if logs + basic traces sufficient (current BaseEmitter adequate)
- MEDIUM if need structured metrics (add MetricsEmitter alongside BaseEmitter)
- HIGH if need distributed tracing + replay (requires OTEL integration, span storage, replay engine)

**Current gap**: Observability interface exists, minimal implementation (LangfuseEmitter/OpenInferenceEmitter are stubs). Testing coverage 0%.

**Follow-up questions**:
- Should traces be sampled (1% for cost control) or always-on?
- Is real-time debugging required (tail logs, live metrics)?
- Should system support trace replay (deterministic re-execution)?

---

**Q7: What testing strategy balances coverage vs. execution time?**

**Why it matters**: Current test coverage ~45% with 139 tests (~70 unit, ~56 integration, ~13 scenario). Full coverage would require:
- Unit tests for all layers (tools, memory, config, observability) → +150 tests
- Integration tests for all component pairs → +100 tests
- Scenario tests for all orchestration patterns → +50 tests
- Total: ~440 tests (3x current), estimated 30-60 min CI time

Need strategy: fast-feedback subset vs. comprehensive nightly suite.

**Architectural impact**:
- Test organization (fast unit tests, slower integration/scenario tests in separate markers)
- CI pipeline design (PR checks vs. nightly vs. pre-release)
- Test data management (fixtures, factories, test databases)

**Current state**: Tests not organized by speed; no CI time budgets defined.

**Follow-up questions**:
- What is acceptable PR check time (5 min, 15 min, 30 min)?
- Should tests be parallelizable (currently assume serial execution)?
- Is mutation testing required (detect untested code paths)?

---

### Backwards Compatibility

**Q8: What is the backwards compatibility commitment for contracts?**

**Why it matters**: System defines canonical protocols (OrchestratorProtocol, AgentLifecycleProtocol, AgentProtocol, RoutingAuthority, ExecutionContext). If these contracts change:
- Breaking changes → require major version bumps, migration guides, deprecation cycles
- Additive changes → safe to add optional fields, new methods with defaults
- Behavioral changes → subtle bugs if agents rely on undocumented behavior

Need clear compatibility policy to guide evolution.

**Architectural impact**:
- High compatibility commitment → slower evolution, careful deprecation, parallel implementations
- Low compatibility commitment → faster iteration, breaking changes acceptable, users handle migration

**Current state**: No explicit compatibility policy documented. Contracts marked "Canonical" suggest high commitment, but no versioning/deprecation process defined.

**Follow-up questions**:
- Should contracts be semantically versioned?
- How long must deprecated features be supported (1 release, 6 months, 1 year)?
- Should breaking changes require RFC process?

---

**Q9: Can existing agents/tools be migrated incrementally to new contracts?**

**Why it matters**: Repository has multiple agent implementations:
- `src/cuga/modular/agents.py`: PlannerAgent, WorkerAgent, CoordinatorAgent (current)
- `src/cuga/agents/`: Controller, Executor, lifecycle implementations (canonical protocols)
- `src/cuga/backend/`: FastAPI-wrapped agents
- `src/cuga/mcp/`: MCP server lifecycle

If contracts change, all implementations must migrate. Incremental migration (both old + new coexist during transition) vs. big-bang migration (all change simultaneously).

**Architectural impact**:
- Incremental: Need adapter layers, dual implementations, compatibility shims
- Big-bang: Simpler codebase but higher risk, longer feature freeze

**Current state**: Unclear if `modular/agents.py` conforms to canonical `agents/` protocols. No migration plan documented.

**Follow-up questions**:
- Should old agents be deprecated (remove `modular/agents.py`)?
- Is adapter pattern acceptable (wrap old agents in new protocol)?
- How long should dual implementations coexist?

---

## Phase 2: Proposed Future Work

### Category 1: Infrastructure & Correctness (High Priority)

---

#### F1: Complete Test Coverage for Untested Layers

**Description**: Implement comprehensive tests for tools, memory, config, observability layers currently at 0-30% coverage.

**Motivation**: 
- Tool registry security boundaries untested → potential security vulnerabilities
- Memory data integrity untested → risk of data corruption, cross-profile leakage
- Config precedence untested → runtime surprises from unexpected value sources
- Observability untested → broken tracing in production

Per `docs/testing/COVERAGE_MATRIX.md`:
- Tools: 30% coverage, need +60 tests (registry resolution, sandbox isolation, allowlist/denylist enforcement)
- Memory: 20% coverage, need +80 tests (vector storage, RAG retrieval, persistence, profile isolation)
- Config: 0% coverage, need +60 tests (7-layer precedence, deep merge, provenance, env validation)
- Observability: 0% coverage, need +40 tests (trace propagation, span collection, emitter integration)

**Impact on Architecture**: LOW (tests validate existing design, no structural changes)

**Implementation Complexity**: MEDIUM
- Tools: 16h (allowlist enforcement, sandbox policy validation, dynamic import restrictions)
- Memory: 24h (vector backend integration, profile isolation, retention policies)
- Config: 16h (precedence chain, Dynaconf/Hydra integration, mode validation)
- Observability: 24h (OTEL integration, LangFuse/LangSmith real traces, span ordering)
- Total: 80h (~2 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Tests may reveal bugs in core logic (good but requires fixes)
- Risk: Coverage targets may be arbitrary (better metric: critical path coverage)
- Tradeoff: Time spent testing vs. new features

**Recommendation**: **CORE** - Critical for production deployment. Block v1.0 release until tools/memory/config reach 80% coverage. Observability can remain 50% if wrapped with defensive guards.

**Implementation Phases**:
1. Tools tests (Week 1): Registry resolution, allowlist enforcement, sandbox policies
2. Config tests (Week 1): Precedence chain, Dynaconf integration, env validators
3. Memory tests (Week 2): Vector backends, profile isolation, persistence
4. Observability tests (Week 2): Basic tracing, span propagation (defer deep OTEL integration)

---

#### F2: Async-First Execution Model

**Description**: Convert synchronous execution paths to async/await with proper backpressure and cancellation support.

**Motivation**:
Current architecture mixes sync/async:
- `OrchestratorProtocol.orchestrate()` returns `AsyncIterator` (async)
- `PlannerAgent.plan()` is synchronous (blocks)
- `WorkerAgent.execute()` is synchronous (blocks)
- `VectorMemory.search()` is synchronous (blocks I/O)
- Tool handlers are synchronous (no `async def handler(...)`)

This prevents:
- Concurrent tool execution (parallel steps in a plan)
- Non-blocking memory queries (RAG retrieval blocks executor)
- Graceful cancellation (user stops request mid-execution)
- Backpressure (fast producer, slow consumer)

**Impact on Architecture**: HIGH
- All agent methods become `async def`
- Tool handler signature changes: `async def handler(inputs, context) -> Any`
- VectorMemory becomes async: `async def search()`, `async def remember()`
- Backward incompatibility: All existing tools must migrate

**Implementation Complexity**: HIGH
- Refactor PlannerAgent, WorkerAgent, CoordinatorAgent to async (8h)
- Update tool handler signature + migrate existing tools (16h)
- Async VectorMemory with backend-specific async clients (12h)
- Add cancellation tokens (CancellationToken pattern) (8h)
- Update all tests to use `pytest-asyncio` (8h)
- Migration guide for custom tools/agents (4h)
- Total: 56h (~1.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Breaking change for all existing tools (requires migration guide, deprecation cycle)
- Risk: Async bugs harder to debug (race conditions, deadlocks)
- Risk: Performance regression if not careful (async overhead for CPU-bound tasks)
- Tradeoff: Complexity vs. scalability (async enables concurrency but adds cognitive load)

**Recommendation**: **OPTIONAL** initially, **CORE** long-term if:
- Targeting >100 req/s throughput
- Workflows require parallel tool execution
- Tools perform I/O (DB queries, API calls, file operations)

**Implementation Approach**:
1. Add `async` variants alongside sync methods (e.g., `plan()` + `plan_async()`)
2. Deprecate sync methods with warnings
3. Migrate internal usage to async over 2 releases
4. Remove sync methods in major version bump

**Compatibility Strategy**:
- Phase 1 (v1.1): Add async methods, keep sync methods working
- Phase 2 (v1.2): Warn on sync method usage
- Phase 3 (v2.0): Remove sync methods

---

#### F3: End-to-End Sandbox Enforcement Validation

**Description**: Implement comprehensive tests validating sandbox profile enforcement (allowlists, denylists, read-only mounts, resource limits) from registry entry to tool execution.

**Motivation**:
Registry declares sandbox profiles (`py/node slim|full`, `orchestrator`) with:
- Read-only mounts
- `/workdir` pinning for exec scopes
- Allowlisted tool imports (`cuga.modular.tools.*`)
- Denylisted modules (network, filesystem, eval/exec)

But enforcement is untested:
- Does registry actually reject tools outside allowlist?
- Are read-only mounts enforced (or can tools write anyway)?
- Do resource limits (CPU/memory/time) actually terminate runaway tools?
- Can tools bypass import restrictions with `importlib.import_module()`?

**Impact on Architecture**: LOW (validates existing security boundaries, no structural changes)

**Implementation Complexity**: MEDIUM
- Registry allowlist enforcement tests: 8h (dynamic import checks, module blocking)
- Sandbox policy validation tests: 12h (read-only mounts, resource limits, workdir pinning)
- End-to-end security tests: 16h (attempt to bypass restrictions, red-team scenarios)
- Documentation updates: 4h (document enforcement guarantees, attack surface)
- Total: 40h (~1 engineer-week)

**Risks/Tradeoffs**:
- Risk: Tests may reveal enforcement gaps (need fixes before claiming security)
- Risk: Over-restrictive policies break legitimate tools (need policy tuning)
- Tradeoff: Security hardening vs. developer friction

**Recommendation**: **CORE** - Critical for production deployment in multi-tenant or untrusted-tool scenarios. Block production use until sandbox enforcement validated.

**Test Scenarios**:
1. **Allowlist Bypass**: Tool attempts `import os` (should fail)
2. **Dynamic Import Bypass**: Tool uses `importlib.import_module("os")` (should fail)
3. **Read-Only Violation**: Tool writes to read-only mount (should fail)
4. **Resource Exhaustion**: Tool infinite loop (should timeout)
5. **Network Egress**: Tool attempts HTTP request (should fail unless profile allows)
6. **Filesystem Escape**: Tool attempts `../../etc/passwd` (should fail)

---

#### F4: Configuration Integration with Dynaconf/Hydra

**Description**: Complete Phase 3 by integrating ConfigResolver with existing Dynaconf/Hydra loaders, eliminating dual config systems.

**Motivation**:
Phase 3 created ConfigResolver but left it alongside existing loaders:
- Dynaconf (`src/cuga/config.py`) loads `settings.toml`, `.env`, eval configs
- Hydra (`src/cuga/mcp_v2/registry/loader.py`) loads MCP registry with composition
- ConfigResolver (`src/cuga/config/resolver.py`) enforces precedence but not integrated

This creates:
- Dual config access paths (some code uses Dynaconf, some uses ConfigResolver)
- Unclear which takes precedence when both define same key
- Testing complexity (mock both systems)
- Migration friction (developers unsure which to use)

**Impact on Architecture**: MEDIUM
- Unified config access via single entry point
- Dynaconf/Hydra become implementation details (ConfigSources)
- All config reads go through ConfigResolver
- Provenance tracking works for all config keys

**Implementation Complexity**: MEDIUM
- Create DynaconfSource implementing ConfigSource interface (8h)
- Create HydraSource implementing ConfigSource interface (8h)
- Add backward compatibility shim (config.py delegates to resolver) (4h)
- Migrate internal usage to ConfigResolver (12h)
- Update tests to use ConfigResolver fixtures (8h)
- Documentation updates (4h)
- Total: 44h (~1 engineer-week)

**Risks/Tradeoffs**:
- Risk: Behavior changes if precedence differs (need careful validation)
- Risk: Performance regression (ConfigResolver adds overhead)
- Tradeoff: Unified API vs. migration cost

**Recommendation**: **CORE** - Marked as Phase 3 incomplete in todo1.md. Essential for config observability (provenance tracking) and testing (deterministic overrides).

**Migration Strategy**:
1. ConfigResolver wraps Dynaconf/Hydra (no behavior changes)
2. Add tests comparing old vs. new (ensure parity)
3. Migrate internal usage module-by-module
4. Deprecate direct Dynaconf/Hydra access
5. Remove Dynaconf/Hydra from public API (internal only)

---

### Category 2: Observability & Operations (Medium Priority)

---

#### F5: Distributed Tracing with OpenTelemetry

**Description**: Replace BaseEmitter stub with full OpenTelemetry integration (spans, metrics, context propagation).

**Motivation**:
Current observability:
- `trace_id` propagates as string (no span context)
- BaseEmitter.emit() sends unstructured dicts
- No span hierarchy (parent/child relationships lost)
- No metrics collection (request counts, latencies, error rates)
- No sampling (100% or 0%, no configurable sampling)

For production debugging need:
- Structured spans (start/end, attributes, events)
- Parent/child span relationships (orchestrator → planner → worker → tool)
- Automatic context propagation (trace_id + span_id across process boundaries)
- Metrics (request rate, latency histograms, error rate by failure mode)
- Sampling (1% for cost control, 100% for errors/slow requests)

**Impact on Architecture**: MEDIUM
- ExecutionContext gains OTEL span context (trace_id + span_id + trace_flags)
- All agent methods wrapped in spans
- Tool handlers auto-instrumented
- Metrics emitted at lifecycle boundaries

**Implementation Complexity**: MEDIUM
- OpenTelemetry SDK integration (setup, exporters) (8h)
- Span wrapper decorators (@traced, @instrumented) (8h)
- ExecutionContext span context integration (6h)
- Metrics collection (counters, histograms, gauges) (8h)
- Sampling configuration (4h)
- Documentation + runbooks (6h)
- Total: 40h (~1 engineer-week)

**Risks/Tradeoffs**:
- Risk: Overhead from tracing (mitigate with sampling)
- Risk: OTEL complexity (mitigate with sensible defaults)
- Tradeoff: Observability depth vs. runtime cost

**Recommendation**: **OPTIONAL** initially, **CORE** for production at scale. Defer until after test coverage complete (F1) to avoid instrumenting untested code.

**Implementation Phases**:
1. Basic OTEL setup (spans only, no metrics) (Week 1)
2. Span hierarchy + context propagation (Week 2)
3. Metrics collection (Week 3)
4. Sampling + advanced features (Week 4)

---

#### F6: Memory Retention & Lifecycle Policies

**Description**: Add configurable retention policies for VectorMemory (TTL, size limits, cleanup jobs).

**Motivation**:
Current VectorMemory:
- Unbounded growth (no cleanup)
- No TTL (entries live forever)
- No size limits (can exhaust memory/disk)
- No archival (old entries deleted, not archived)

For production need:
- TTL: Delete entries older than N days
- Size limits: Keep last N entries per profile
- Cleanup jobs: Periodic background cleanup
- Archival: Move old entries to cold storage (S3, etc.)

**Impact on Architecture**: LOW
- Add retention policy config (TTL, max_entries)
- Add cleanup scheduler (periodic job)
- Add archival backend interface (S3Backend, etc.)

**Implementation Complexity**: LOW
- Retention policy dataclass (2h)
- Cleanup scheduler (4h)
- TTL enforcement (4h)
- Size limit enforcement (4h)
- Tests (6h)
- Documentation (2h)
- Total: 22h (~0.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Aggressive cleanup deletes valuable data (need conservative defaults)
- Tradeoff: Memory cost vs. retrieval quality (older entries may be relevant)

**Recommendation**: **OPTIONAL** for v1.0, **CORE** for production deployments (prevents unbounded growth).

**Default Policy** (conservative):
```yaml
retention:
  ttl: 30d  # 30 days
  max_entries_per_profile: 10000
  cleanup_interval: 1h
  archival: disabled  # require explicit opt-in
```

---

#### F7: Agent Performance Profiling & Bottleneck Analysis

**Description**: Add built-in profiling for agent execution (time per stage, tool latency, memory allocation).

**Motivation**:
Current system has no built-in profiling:
- No visibility into which tools are slow
- No breakdown of time per lifecycle stage (plan, route, execute, aggregate)
- No memory allocation tracking
- Developers must add manual timing code

For performance optimization need:
- Per-tool latency percentiles (p50, p95, p99)
- Per-stage timing (how much time in planning vs. execution?)
- Memory allocation per agent/tool
- Flamegraphs for hotspot identification

**Impact on Architecture**: LOW
- Add timing decorators
- Add memory profiler hooks
- Expose profiling API (start/stop profiling, dump stats)

**Implementation Complexity**: LOW
- Timing decorators (4h)
- Memory profiling (optional, using tracemalloc) (4h)
- Profiling API (2h)
- Flamegraph export (4h)
- Documentation (2h)
- Total: 16h (~0.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Profiling overhead (mitigate with on-demand enabling)
- Tradeoff: Performance visibility vs. runtime cost

**Recommendation**: **OPTIONAL** - Useful for optimization but not critical for correctness. Implement after observability (F5) to leverage existing instrumentation.

---

### Category 3: Extensibility & Developer Experience (Lower Priority)

---

#### F8: Tool Schema Versioning & Gradual Migration

**Description**: Add version field to ToolSpec, support multiple versions of same tool, enable gradual migration.

**Motivation**:
Current ToolSpec has no version:
```python
@dataclass
class ToolSpec:
    name: str
    description: str
    handler: Callable
```

If tool signature changes (add parameter, change return type):
- Breaking change for all users
- Must update all call sites simultaneously (big-bang migration)
- No graceful degradation (old calls fail)

With versioning:
```python
@dataclass
class ToolSpec:
    name: str
    version: str  # "1.0.0"
    description: str
    handler: Callable
```

Registry can host multiple versions:
- `my_tool@1.0.0` (old signature)
- `my_tool@2.0.0` (new signature)

Agents specify version in plan:
```python
{"tool": "my_tool@2.0.0", "input": {...}}
```

**Impact on Architecture**: MEDIUM
- ToolRegistry keys change from `name` to `name@version`
- Plan steps include version
- Deprecation warnings for old versions
- Routing can auto-upgrade (v1 → v2 if compatible)

**Implementation Complexity**: MEDIUM
- Add version field to ToolSpec (2h)
- Update registry to store name@version (4h)
- Update plan step format to include version (4h)
- Add version resolution logic (latest, explicit, range) (6h)
- Add deprecation warnings (4h)
- Migration guide (4h)
- Tests (8h)
- Total: 32h (~1 engineer-week)

**Risks/Tradeoffs**:
- Risk: Complexity in managing multiple versions (registry bloat)
- Risk: Version mismatch errors (agent requests v3, only v1/v2 available)
- Tradeoff: Flexibility vs. simplicity

**Recommendation**: **OPTIONAL** - Valuable for long-term evolution but not critical for v1.0. Implement after tool testing complete (F1) to avoid versioning untested tools.

---

#### F9: Graph-Based Orchestration (LangGraph Integration)

**Description**: Replace linear plan sequences with DAG-based orchestration supporting parallel execution, conditional branching, loops.

**Motivation**:
Current PlannerAgent generates linear sequences:
```python
plan = [step1, step2, step3]  # Sequential only
```

For complex workflows need:
- Parallel execution: Run step2 and step3 concurrently
- Conditional branching: If step1 succeeds, run step2, else run step3
- Loops: Retry step2 until success (max N attempts)
- Sub-orchestrations: Step2 calls another agent

LangGraph provides graph execution engine:
```python
from langgraph.graph import Graph

graph = Graph()
graph.add_node("step1", handler1)
graph.add_node("step2", handler2)
graph.add_node("step3", handler3)
graph.add_edge("step1", "step2")  # step1 → step2
graph.add_edge("step1", "step3")  # step1 → step3 (parallel)
graph.add_conditional_edges("step2", condition, {"success": "step4", "failure": "step5"})
```

**Impact on Architecture**: HIGH
- PlannerAgent generates graph instead of list
- Need graph executor (parallel worker pool, condition evaluator)
- Need cycle detection (prevent infinite loops)
- Need failure handling per graph node
- Execution context needs graph state (current node, visited nodes)

**Implementation Complexity**: HIGH
- LangGraph integration (12h)
- Graph planner (replaces linear planner) (16h)
- Graph executor (parallel execution, condition evaluation) (20h)
- Cycle detection + safeguards (8h)
- Migration from linear plans (12h)
- Tests (20h)
- Documentation (8h)
- Total: 96h (~2.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Increased complexity (debugging graph execution harder than linear)
- Risk: Performance overhead (graph coordination cost)
- Risk: Breaking change (existing linear plans need migration)
- Tradeoff: Expressiveness vs. simplicity

**Recommendation**: **OPTIONAL** - Defer until clear use cases requiring DAG orchestration. Mentioned in ROADMAP.md but no concrete requirements yet.

**Preconditions**:
- Async execution model (F2) complete (graph executor needs async)
- Test coverage (F1) complete (don't add complexity to untested system)
- Real workflow examples requiring DAG (validate demand)

---

#### F10: Policy Engine Extensibility

**Description**: Make PolicyEnforcer pluggable, allow custom policy engines (OPA, Cedar, custom Python).

**Motivation**:
Current PolicyEnforcer loads YAML policies from `configurations/policies/`:
```python
class PolicyEnforcer:
    def __init__(self, policy_root: Path):
        self.policy_root = policy_root
        self._cache: Dict[str, ProfilePolicy] = {}
```

For complex policies need:
- External policy engines (Open Policy Agent, AWS Cedar)
- Dynamic policy updates (no restart required)
- Policy versioning (A/B test policies)
- Policy composition (combine multiple policy sources)

**Impact on Architecture**: MEDIUM
- Define PolicyEngine protocol
- PolicyEnforcer delegates to engine
- Support multiple engines (YAML, OPA, Cedar, custom)

**Implementation Complexity**: MEDIUM
- PolicyEngine protocol (4h)
- OPA adapter (8h)
- Cedar adapter (8h)
- Policy composition (6h)
- Dynamic reload (4h)
- Tests (12h)
- Documentation (4h)
- Total: 46h (~1 engineer-week)

**Risks/Tradeoffs**:
- Risk: External dependencies (OPA/Cedar SDKs)
- Risk: Performance (remote policy evaluation latency)
- Tradeoff: Flexibility vs. complexity

**Recommendation**: **OPTIONAL** - Only if policy complexity justifies external engine. Current YAML policies sufficient for most use cases.

**Preconditions**:
- Concrete use case requiring external policy engine
- Performance budget for policy evaluation (latency acceptable?)

---

#### F11: Hot-Reloadable Tool Registry

**Description**: Support dynamic tool registration/unregistration without restarting orchestrator.

**Motivation**:
Current ToolRegistry loads tools at initialization:
```python
registry = ToolRegistry([tool1, tool2, tool3])
```

Changes require restart. For development/staging need:
- Add tools without restart (fast iteration)
- Remove tools without restart (rollback bad tools)
- Update tool handlers without restart (hot-fix)

**Impact on Architecture**: LOW
- ToolRegistry becomes mutable (currently immutable list)
- Add `register(tool)`, `unregister(name)`, `update(tool)` methods
- Add change listeners (notify agents of registry changes)

**Implementation Complexity**: LOW
- Mutable registry (4h)
- Registration API (4h)
- Change listeners (4h)
- Thread safety (6h)
- Tests (8h)
- Documentation (2h)
- Total: 28h (~1 engineer-week)

**Risks/Tradeoffs**:
- Risk: Race conditions (agent uses tool mid-unregistration)
- Risk: Stale references (agent caches tool, registry updates)
- Tradeoff: Development speed vs. complexity

**Recommendation**: **OPTIONAL** - Useful for development but not critical for production (production should deploy immutable tool sets).

**Implementation Strategy**:
- Development mode: Hot reload enabled
- Production mode: Hot reload disabled (fail-safe)

---

#### F12: Model Provider Abstraction Hardening

**Description**: Formalize provider abstraction (currently implicit), add provider-agnostic retry/fallback/quota.

**Motivation**:
Current provider logic scattered:
- `src/cuga/providers/watsonx.py`: WatsonxProvider
- `src/cuga/llm/`: LLMManager with fallback logic
- Backend hardcodes provider-specific details

Need unified provider interface:
```python
class LLMProvider(Protocol):
    async def generate(self, prompt: str, config: ModelConfig) -> str: ...
    async def embed(self, text: str) -> List[float]: ...
    def get_models(self) -> List[ModelInfo]: ...
```

With cross-cutting concerns:
- Retry on rate limit (exponential backoff)
- Fallback to secondary provider (watsonx → openai)
- Quota tracking (tokens used per period)
- Circuit breaker (disable failing provider)

**Impact on Architecture**: MEDIUM
- Define LLMProvider protocol
- Wrap providers in retry/fallback/quota middleware
- Unified config (provider list with priorities)

**Implementation Complexity**: MEDIUM
- LLMProvider protocol (4h)
- Provider wrappers (watsonx, openai, anthropic) (12h)
- Retry middleware (6h)
- Fallback middleware (6h)
- Quota tracking (8h)
- Circuit breaker (6h)
- Tests (16h)
- Documentation (4h)
- Total: 62h (~1.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Abstraction leaks (provider-specific features not exposed)
- Risk: Performance overhead (middleware layers)
- Tradeoff: Portability vs. provider-specific optimization

**Recommendation**: **OPTIONAL** - Current provider usage is basic (generate text). Defer until multi-provider fallback is required use case.

---

### Category 4: Documentation & Knowledge Transfer (Ongoing)

---

#### F13: Architectural Decision Records (ADRs)

**Description**: Document major design decisions (why async, why profile isolation, why local-first) in structured ADR format.

**Motivation**:
Repository has extensive documentation but lacks decision rationale:
- WHY is tool import restricted to `cuga.modular.tools.*`? (Security boundary, but not documented)
- WHY is temperature default 0.0? (Determinism, but not explained)
- WHY synchronous execution? (Simplicity, but trade-offs not discussed)

ADRs capture decision context:
```markdown
# ADR-001: Restrict Tool Imports to cuga.modular.tools.*

Status: Accepted  
Date: 2025-12-31  
Deciders: Security Team, Architecture Team

## Context
Dynamic tool loading enables extensibility but risks arbitrary code execution.

## Decision
Restrict dynamic imports to cuga.modular.tools.* namespace.

## Consequences
- Positive: Security boundary, audit trail, allowlist enforcement
- Negative: Less flexible, custom tools require packaging
- Alternatives Considered: Sandboxed imports, signature verification
```

**Impact on Architecture**: NONE (documentation only)

**Implementation Complexity**: LOW
- ADR template (2h)
- Retrospective ADRs for major decisions (16h, ~8 decisions)
- Process for new ADRs (2h)
- Total: 20h (~0.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Stale ADRs if not maintained
- Tradeoff: Documentation burden vs. knowledge retention

**Recommendation**: **CORE** - Essential for long-term maintainability. Start with 5-10 critical decisions, grow incrementally.

**Proposed ADR Topics**:
1. Local-first execution (offline priority)
2. Synchronous vs. async execution model
3. Profile-based isolation boundaries
4. Tool import restrictions
5. Deterministic defaults (temperature=0.0)
6. Protocol-driven contracts (why protocols not abstract classes)
7. Configuration precedence order
8. Failure mode taxonomy
9. Memory backend selection (FAISS/Chroma/Qdrant)
10. Observability interface (why BaseEmitter not concrete)

---

#### F14: Onboarding Path for New Contributors

**Description**: Expand `docs/DEVELOPER_ONBOARDING.md` with progressive exercises (tool → agent → orchestrator → custom policy).

**Motivation**:
Current onboarding guide is comprehensive (90 minutes, hands-on examples) but single-path. New contributors have different backgrounds:
- Backend engineers: Understand FastAPI, need agent concepts
- Data scientists: Understand LLMs, need orchestration concepts
- DevOps engineers: Understand deployment, need architecture concepts

Need multiple learning paths:
- **Quick Start** (30 min): Run example, modify prompt
- **Tool Developer** (60 min): Create custom tool, register, test
- **Agent Developer** (90 min): Implement custom agent, wire lifecycle
- **Orchestration Developer** (120 min): Build custom orchestrator, routing policy
- **Platform Developer** (180 min): Deploy production stack, monitoring, policies

**Impact on Architecture**: NONE (documentation only)

**Implementation Complexity**: LOW
- Learning path definitions (4h)
- Progressive exercises (12h)
- Prerequisites + skill checks (4h)
- Total: 20h (~0.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Outdated exercises as code evolves
- Tradeoff: Onboarding quality vs. maintenance burden

**Recommendation**: **OPTIONAL** - Current single-path onboarding adequate for now. Expand when multiple contributor personas identified.

---

#### F15: Production Runbooks & Troubleshooting Guides

**Description**: Create operational runbooks for common production issues (high latency, memory leaks, failed tools, budget exhausted).

**Motivation**:
Documentation focuses on architecture/design, lacks operational guidance:
- **Symptom**: High latency (p95 > 10s)
  - **Diagnosis**: Check planner ranking time, tool execution time, memory search time
  - **Remediation**: Increase max_steps cap, optimize tool handlers, tune embedder
  
- **Symptom**: Memory leak (RSS grows unbounded)
  - **Diagnosis**: Check VectorMemory store size, trace leak sources
  - **Remediation**: Enable retention policy, investigate tool resource leaks

- **Symptom**: Tool execution fails (timeout, error)
  - **Diagnosis**: Check sandbox logs, resource limits, allowlist violations
  - **Remediation**: Increase timeout, relax resource limits, fix tool code

**Impact on Architecture**: NONE (documentation only)

**Implementation Complexity**: LOW
- Runbook template (2h)
- Common issue runbooks (12h, ~6 issues)
- Diagnostic scripts (8h)
- Total: 22h (~0.5 engineer-weeks)

**Risks/Tradeoffs**:
- Risk: Runbooks become outdated
- Tradeoff: Operational support vs. documentation burden

**Recommendation**: **CORE** - Essential for production operations. Start with 5 most common issues, expand based on real incidents.

**Proposed Runbooks**:
1. High Latency Diagnosis
2. Memory Leak Investigation
3. Tool Execution Failures
4. Budget Exhaustion Handling
5. Trace Propagation Failures
6. Configuration Precedence Debugging

---

## Prioritization Matrix

| Feature ID | Name | Priority | Impact | Complexity | Est. Hours | Dependencies |
|------------|------|----------|--------|------------|------------|--------------|
| F1 | Complete Test Coverage | **CORE** | LOW | MEDIUM | 80h | None |
| F3 | Sandbox Enforcement Validation | **CORE** | LOW | MEDIUM | 40h | None |
| F4 | Config Integration (Phase 3) | **CORE** | MEDIUM | MEDIUM | 44h | None |
| F13 | Architectural Decision Records | **CORE** | NONE | LOW | 20h | None |
| F15 | Production Runbooks | **CORE** | NONE | LOW | 22h | None |
| F2 | Async-First Execution | **OPTIONAL→CORE** | HIGH | HIGH | 56h | F1 |
| F5 | Distributed Tracing (OTEL) | **OPTIONAL→CORE** | MEDIUM | MEDIUM | 40h | F1 |
| F6 | Memory Retention Policies | **OPTIONAL→CORE** | LOW | LOW | 22h | F1 |
| F7 | Performance Profiling | **OPTIONAL** | LOW | LOW | 16h | F5 |
| F8 | Tool Schema Versioning | **OPTIONAL** | MEDIUM | MEDIUM | 32h | F1 |
| F9 | Graph Orchestration (LangGraph) | **OPTIONAL** | HIGH | HIGH | 96h | F2, F1 |
| F10 | Policy Engine Extensibility | **OPTIONAL** | MEDIUM | MEDIUM | 46h | None |
| F11 | Hot-Reloadable Registry | **OPTIONAL** | LOW | LOW | 28h | None |
| F12 | Provider Abstraction Hardening | **OPTIONAL** | MEDIUM | MEDIUM | 62h | None |
| F14 | Expanded Onboarding Paths | **OPTIONAL** | NONE | LOW | 20h | None |

**Total Estimated Effort**:
- CORE features: 206h (~5 engineer-weeks)
- OPTIONAL→CORE features: 118h (~3 engineer-weeks)
- OPTIONAL features: 300h (~7.5 engineer-weeks)
- **Total**: 624h (~15.5 engineer-weeks / ~4 months with 1 engineer)

---

## Recommended Sequencing

### Phase A: Production Readiness (Weeks 1-5)
**Goal**: Block production deployment gaps

1. **F1**: Complete test coverage (tools, memory, config, observability) — 80h
2. **F3**: Sandbox enforcement validation (security boundaries) — 40h
3. **F4**: Config integration with Dynaconf/Hydra (Phase 3 complete) — 44h
4. **F13**: Architectural Decision Records (document design rationale) — 20h
5. **F15**: Production runbooks (operational support) — 22h

**Total**: 206h (~5 weeks)

**Blockers Resolved**:
- Test coverage >80% (tools, memory, config)
- Sandbox security validated
- Config system unified
- Operational documentation complete

---

### Phase B: Scalability Foundations (Weeks 6-10)
**Goal**: Enable scale beyond 100 req/s

1. **F2**: Async-first execution (non-blocking I/O) — 56h
2. **F5**: Distributed tracing (OTEL integration) — 40h
3. **F6**: Memory retention policies (prevent unbounded growth) — 22h

**Total**: 118h (~3 weeks)

**Capabilities Enabled**:
- Concurrent tool execution
- Non-blocking memory queries
- Structured observability
- Bounded memory growth

---

### Phase C: Advanced Features (Weeks 11-18)
**Goal**: Enable complex workflows and extensibility

1. **F8**: Tool schema versioning (gradual migration) — 32h
2. **F9**: Graph orchestration (DAG workflows) — 96h
3. **F12**: Provider abstraction hardening (multi-provider fallback) — 62h

**Total**: 190h (~5 weeks)

**Capabilities Enabled**:
- DAG workflows (parallel, conditional, loops)
- Tool versioning (backward compatibility)
- Provider fallback (resilience)

---

### Phase D: Polish & Optimization (Weeks 19-22)
**Goal**: Developer experience and performance optimization

1. **F7**: Performance profiling (hotspot analysis) — 16h
2. **F10**: Policy engine extensibility (OPA/Cedar) — 46h
3. **F11**: Hot-reloadable registry (fast iteration) — 28h
4. **F14**: Expanded onboarding paths (multi-persona) — 20h

**Total**: 110h (~3 weeks)

---

## Decision Criteria

When evaluating proposed features:

1. **Does it block production deployment?** → CORE priority
2. **Does it prevent architectural debt?** → CORE priority
3. **Does it enable scale (>100 req/s)?** → OPTIONAL→CORE
4. **Does it improve developer experience?** → OPTIONAL
5. **Does it add speculative value?** → DEFER

**Risk Appetite**:
- Security: Zero tolerance (sandbox enforcement CORE)
- Correctness: Zero tolerance (test coverage CORE)
- Performance: Moderate tolerance (async OPTIONAL→CORE)
- Complexity: Low tolerance (defer LangGraph until proven need)

**Backward Compatibility**:
- Breaking changes require major version bump (v1 → v2)
- Deprecation cycle: 2 releases or 6 months minimum
- Migration guides required for all breaking changes

---

## Conclusion

The cugar-agent system has strong architectural foundations (protocol-driven contracts, deterministic execution, clear boundaries) but requires focused investment in **testing** (F1, F3), **config unification** (F4), and **documentation** (F13, F15) before production deployment at scale.

The async execution model (F2) and distributed tracing (F5) become critical as request volume grows, but should be deferred until test coverage is complete to avoid instrumenting untested code.

Advanced features like graph orchestration (F9) and policy extensibility (F10) should wait for concrete use cases demonstrating need—premature abstraction adds complexity without validated value.

**Immediate Next Steps**:
1. Answer open questions (Q1-Q9) to refine priorities
2. Begin Phase A (Production Readiness): F1 → F3 → F4 → F13 → F15
3. Reassess after Phase A based on production learnings
4. Consider Phases B-D based on scale requirements and use cases

The ~15 week roadmap assumes single engineer full-time; adjust timeline for team size and competing priorities.
