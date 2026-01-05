# Repository To-Do (v1.0.0 SHIPPED ✅ → v1.3.2 Orchestrator Hardening)

**Last Updated:** 2026-01-03  
**v1.0.0 Status:** ✅ **SHIPPED** (Infrastructure Release - Observability & Guardrails Ready)  
**v1.1 Status:** ✅ **COMPLETED** (Agent Integration - 2026-01-02)  
**v1.3.2 Status:** 90% Complete (Orchestrator Hardening - 9/10 tasks done)

---

## ✅ v1.3.2 Orchestrator Hardening (90% Complete - 9/10 Tasks)

**Goal:** Production-ready orchestrator with retry, audit, approval, and recovery mechanisms

**Test Coverage:** 168/168 tests passing (100%)

### Completed Tasks

1. ✅ **Task #1: OrchestratorProtocol (v1.3.0)** - 31 tests
   - ExecutionContext with trace_id propagation
   - Lifecycle stages (initialize → plan → route → execute → aggregate → complete)
   - Immutable context with with_* update methods
   - Status: Complete

2. ✅ **Task #2: RoutingAuthority (v1.3.0)** - 20 tests
   - PolicyBasedRoutingAuthority with pluggable routing policies
   - RoundRobinPolicy, CapabilityBasedPolicy, LoadBalancedPolicy
   - Routing decisions with audit trail integration
   - Status: Complete

3. ✅ **Task #3: PlanningAuthority (v1.3.1)** - 18 tests
   - Plan creation with state machine transitions (CREATED → VALIDATED → EXECUTING → COMPLETED/FAILED)
   - ToolBudget tracking (cost_ceiling, call_ceiling, token_ceiling)
   - Budget enforcement with warnings and blocking
   - Status: Complete

4. ✅ **Task #4: RetryPolicy (v1.3.1)** - 18 tests
   - Exponential backoff, linear backoff, no-retry strategies
   - Transient failure detection (ConnectionError, TimeoutError, etc.)
   - Max attempt tracking with backoff delays
   - Status: Complete

5. ✅ **Task #5: AuditTrail (v1.3.2)** - 17 tests
   - SQLite backend for persistent audit records
   - DecisionRecord with trace-based queries
   - Planning, routing, execution decision recording
   - Status: Complete

6. ✅ **Task #6: Approval Gates (v1.3.2)** - 26 tests
   - Manual approval with HITL integration
   - Auto-approve on timeout
   - Approval policy enforcement
   - Status: Complete

7. ✅ **Task #7: Partial Result Preservation (v1.3.2)** - 22 tests
   - Checkpoint-based recovery after failures
   - Partial result extraction from exceptions
   - Recovery strategy suggestions
   - Status: Complete

8. ✅ **Task #8: Tool Documentation (v1.3.1)** - 1,440+ lines
   - Comprehensive tool contract documentation
   - API reference for all orchestrator components
   - Integration patterns and best practices
   - Status: Complete

9. ✅ **Task #9: Full Integration Tests (v1.3.2)** - 16 tests ← **COMPLETED 2026-01-03**
   - End-to-end orchestration scenarios
   - Retry + approval + audit + recovery integration
   - Concurrent execution with trace isolation
   - Status: Complete (see `TASK_9_COMPLETION.md`)

### Pending Tasks

10. ⏳ **Task #10: Architecture Documentation (v1.3.2)** - Estimated 1-2 hours
    - Update `ARCHITECTURE.md` with completed orchestrator features
    - Update `AGENTS.md` with CoordinatorAgent/WorkerAgent enhancements
    - Update `docs/orchestrator/README.md` with full feature matrix
    - Create deployment guide for orchestrator configuration
    - Document best practices and usage patterns

**Overall Progress:** 90% (9/10 tasks complete)  
**Test Statistics:** 168 orchestrator tests passing (100%)  
**Next:** Task #10 (Architecture Documentation)

---

## ✅ External Data Integration - 100% Complete (Phases 1-4)

**Goal:** Complete external data adapter coverage for sales intelligence

**Status:** ✅ **COMPLETE** - All 10 adapters production-ready (2026-01-04)

### Phase 1-3 Complete (5 adapters)
- [x] IBM Sales Cloud adapter (360 LOC, mock tests) - 🔴 Critical
- [x] Salesforce adapter (650 LOC, 11 tests) - 🔴 Critical
- [x] ZoomInfo adapter (565 LOC, 13 tests) - 🟡 High
- [x] Clearbit adapter (476 LOC, 19 tests) - 🟢 Medium
- [x] HubSpot adapter (501 LOC, 19 tests) - 🟡 High

### Phase 4 Complete (5 adapters - NEW) 🎉
- [x] 6sense adapter (570 LOC, 15 tests) - 🟢 Medium - Predictive intent scoring
- [x] Apollo.io adapter (450 LOC, 12 tests) - 🟢 Medium - Contact enrichment & email verification
- [x] Pipedrive adapter (420 LOC, 12 tests) - 🟢 Medium - SMB CRM integration
- [x] Crunchbase adapter (410 LOC, 12 tests) - 🔵 Low - Funding intelligence
- [x] BuiltWith adapter (350 LOC, 10 tests) - 🔵 Low - Technology tracking

### Infrastructure Complete
- [x] Factory routing for all 10 adapters with hot-swap (mock ↔ live)
- [x] Interactive setup wizard (`src/cuga/frontend/setup_wizard.py`, 450 LOC)
- [x] Setup validation script (`scripts/setup_data_feeds.py`) extended for Phase 4
- [x] SafeClient integration (enforced timeouts, retry, URL redaction) - 100% compliant
- [x] Observability integration (trace_id propagation, structured events)
- [x] Comprehensive unit tests (123 tests total, all using mocks)

### Documentation Complete
- [x] QUICK_REFERENCE.md updated with Phase 4 examples (~97 lines of usage code)
- [x] QUICK_TEST_GUIDE.md updated with Phase 4 setup instructions (~200 lines)
- [x] PHASE_4_FINAL_SUMMARY.md - comprehensive completion summary
- [x] CHANGELOG.md updated with Phase 4 additions
- [x] README.md updated with 100% coverage announcement
- [x] EXTERNAL_DATA_FEEDS_STATUS.md updated to 100%

**Statistics:**
- **Adapters:** 10/10 (100% coverage)
- **Total LOC:** 4,752 across all adapters
- **Unit Tests:** 123 (all passing, all using mocks)
- **Signal Types:** 32 unique buying signals
- **AGENTS.md Compliance:** 90% (production-ready)

**Outcome:** Complete external data platform ready for production deployment with comprehensive testing, documentation, and security-first design.

---

## ✅ v1.0.0 Completed Tasks (SHIPPED 2026-01-02)

### Governance & Guardrails ✅
- [x] Guardrails enforcement system (allowlist-first, parameter schemas, risk tiers, budget tracking)
- [x] HTTP hardening with SafeClient (enforced timeouts, automatic retry, URL redaction)
- [x] Secrets management (env-only, CI scanning with trufflehog + gitleaks, `.env.example` parity)
- [x] Eval/exec elimination (AST-based safe_eval_expression, SafeCodeExecutor with allowlists)
- [x] Root `AGENTS.md` aligned with guardrail enforcement (sandbox deny-by-default, PII redaction, approval gates)
- [x] Guardrail CI gate (registry/AGENTS edits fail unless docs updated and `scripts/verify_guardrails.py` passes)

### Registry & Sandbox Enablement ✅
- [x] Registry-driven hot-swap flow (tool replacements via registry edits only, deterministic ordering)
- [x] Sandbox profiles enforced per registry entry (py/node slim/full, read-only mounts, `/workdir` pinning)
- [x] Observability and budget enforcement env keys wired (`AGENT_*`, `OTEL_*`, LangFuse/LangSmith)

### Observability & Tracing ✅
- [x] Comprehensive observability system (OTEL integration, Prometheus `/metrics`, Grafana dashboard with 12 panels)
- [x] Golden signals tracking (success rate, latency P50/P95/P99, tool error rate, mean steps per task, approval wait time)
- [x] Structured events (14 event types: plan, route, tool_call, budget, approval, execution, memory)
- [x] PII-safe logging with automatic redaction (secret/token/password keys recursively redacted)
- [x] Trace propagation (`trace_id` flows through all operations, thread-safe collector)
- [x] FastAPI backend `/metrics` endpoint wired (lines 92-100 in `src/cuga/backend/app.py`)
- [x] Guardrails module emits budget/approval events (`src/cuga/backend/guardrails/policy.py`)

### Configuration & Testing ✅
- [x] Config precedence enforcement (CLI > env > .env > YAML > TOML > defaults with ConfigResolver)
- [x] Config precedence tests (40+ tests validating resolution order and provenance tracking)
- [x] Tools/registry coverage (tests for tool selection, parameter validation, budget tracking)
- [x] Memory/RAG coverage (tests for profile isolation, retention, vector backend switching)
- [x] Observability tests (36 tests for events, golden signals, collector integration)
- [x] Guardrails tests (30+ tests for allowlists, schemas, egress, budget, approval)

### Deployment & Documentation ✅
- [x] Kubernetes manifests (deployment, services, configmaps, secrets, namespace, health checks)
- [x] Docker-compose image pinning (CI blocks `:latest` tags)
- [x] PRODUCTION_READINESS.md updated (rollout/rollback procedures, resource requirements)
- [x] SECURITY.md updated (6 new sections: sandbox, parameters, network egress, PII, approvals, secrets)
- [x] CHANGELOG.md v1.0.0 release notes with **Known Limitations section** (infrastructure-first release)
- [x] USAGE.md updated (config precedence, guardrail examples)
- [x] PROTOCOL_INTEGRATION_STATUS.md created (protocol status, v1.1 roadmap)
- [x] V1_0_0_COMPLETION_SUMMARY.md with infrastructure status and v1.1 routing
- [x] AGENTS.md section 9 added with detailed v1.1 implementation routing

**Total v1.0.0 Work:** 8 major tasks, 2,640+ test lines, 130+ tests, 7 documentation files updated

---

## ⚠️ v1.0.0 Known Limitations (Documented)

**What Works (Production-Ready):**
- ✅ Observability infrastructure (collector, exporters, /metrics endpoint)
- ✅ Guardrails emit events (budget/approval operations)
- ✅ FastAPI backend integration
- ✅ Deployment manifests

**What's Missing (v1.1 Target):**
- ❌ Modular agents (`src/cuga/modular/agents.py`) don't emit events
- ❌ Agents use legacy `InMemoryTracer` instead of `ObservabilityCollector`
- ❌ No guardrail enforcement in agent execution paths

**Impact:** Infrastructure deployable, agents run "dark" (no plan/route/execute events in /metrics)

**See:** `CHANGELOG.md` "Known Limitations" section for detailed analysis and mitigation strategies

---

## 📋 v1.1 Roadmap (Agent Integration - PRIORITY)

### Goal: Wire Observability & Guardrails into Modular Agents

**Target Timeline:** 2-4 days  
**Estimated Effort:** 9-12 hours (1.5-2 days implementation + testing/docs)

### Phase 1: Agent Observability Integration (Days 1-2)

#### Task 1.1: Wire PlannerAgent (30 min)
- [ ] Add `emit_event()` import to `src/cuga/modular/agents.py`
- [ ] Emit `plan_created` event in `PlannerAgent.plan()` with step_count, tool_list
- [ ] Test: Validate event emitted with correct metadata

#### Task 1.2: Wire WorkerAgent (2-3 hours)
- [ ] Add `emit_event()` and `get_collector()` imports
- [ ] Add `GuardrailPolicy` parameter to `__init__()` (default policy if None)
- [ ] Emit `tool_call_start` before each tool execution
- [ ] Check `can_afford()` before tool call (emit `budget_exceeded` if blocked)
- [ ] Validate parameters against `ParameterSchema` (raise ValidationError if invalid)
- [ ] Emit `tool_call_complete` on success (include duration_ms)
- [ ] Emit `tool_call_error` on failure (include error type)
- [ ] Call `budget.spend()` after successful execution
- [ ] Test: Validate events, budget enforcement, parameter validation

#### Task 1.3: Wire CoordinatorAgent (30 min)
- [ ] Add `emit_event()` import
- [ ] Emit `route_decision` event in `dispatch()` with worker selection reasoning
- [ ] Test: Validate event emitted with routing metadata

#### Task 1.4: Replace InMemoryTracer (30 min)
- [ ] Replace `InMemoryTracer` with `get_collector()` in all agent classes
- [ ] Update imports (remove legacy tracer)
- [ ] Test: Validate no import errors, agents work as before

### Phase 2: Integration Testing (Day 2)

#### Task 2.1: End-to-End Tests (3-4 hours)
- [ ] Create `tests/integration/test_agent_observability.py` (~200 lines)
- [ ] Test: Full plan execution emits events in correct order (plan → route → tool_call)
- [ ] Test: Budget enforcement blocks tool calls when ceiling reached
- [ ] Test: Parameter validation rejects invalid inputs
- [ ] Test: `/metrics` endpoint includes agent-generated metrics
- [ ] Test: Golden signals populated from real agent operations
- [ ] Test: trace_id propagates through all events

### Phase 3: Documentation (Day 3)

#### Task 3.1: Write Agent Integration Guide (2-3 hours)
- [ ] Create `docs/observability/AGENT_INTEGRATION.md` (~300 lines)
- [ ] Code examples for each agent class (PlannerAgent, WorkerAgent, CoordinatorAgent)
- [ ] Event types and expected metadata
- [ ] Budget enforcement examples
- [ ] Parameter validation examples
- [ ] Troubleshooting guide

#### Task 3.2: Update Existing Docs
- [ ] Remove "Known Limitations" section from `CHANGELOG.md`
- [ ] Add `## [1.1.0] - 2026-01-16` section to `CHANGELOG.md`
- [ ] Update `docs/observability/OBSERVABILITY_SLOS.md` (remove v1.0.0 limitation notes)
- [ ] Rename `V1_0_0_COMPLETION_SUMMARY.md` → `V1_1_0_COMPLETION_SUMMARY.md`
- [ ] Update status from "Infrastructure Release" to "Full Integration"

### Phase 4: Release (Day 3-4)

#### Task 4.1: Validation
- [ ] Run full test suite: `pytest tests/ -v`
- [ ] Validate `/metrics` includes agent data
- [ ] Check Grafana dashboard shows agent metrics
- [ ] Verify golden signals populated

#### Task 4.2: Merge & Tag
- [ ] Create PR: `feature/v1.1-agent-observability`
- [ ] Code review (focus on event emission, budget enforcement)
- [ ] Merge to main
- [ ] Tag v1.1.0
- [ ] Update `README.md` badge: "v1.1.0 - Full Integration"

---

## 📖 v1.1 Detailed Implementation Reference

**See:**
- `CHANGELOG.md` "v1.1 Roadmap" section for complete code examples (PlannerAgent, WorkerAgent, CoordinatorAgent)
- `docs/AGENTS.md` section 9 for detailed implementation routing
- `AGENTS.md` section 9 for v1.1 integration summary

**Critical Files:**
- `src/cuga/modular/agents.py` (~100 lines changed)
- `tests/integration/test_agent_observability.py` (NEW, ~200 lines)
- `docs/observability/AGENT_INTEGRATION.md` (NEW, ~300 lines)

---

## 🔮 Future Work (v1.2+)

### Protocol Integration (2-4 weeks)
- [ ] Add audit trail recording for routing/planning decisions
- [ ] Emit observability events at protocol boundaries (plan/route/execute)
- [ ] Update FastAPI app to create `ExecutionContext` from HTTP requests

#### Phase 4: Documentation (Week 4)
- [ ] Create migration guide (`docs/agents/MIGRATION_GUIDE.md`)
- [ ] Add API reference for protocol-compliant agents
- [ ] Create examples showing protocol usage
- [ ] Update AGENTS.md with "Protocol Adoption Status" section

### Scenario Testing (2-3 weeks)

**Goal:** End-to-end scenario tests validating orchestration with real components

**Approach:** 8 enterprise workflows with minimal mocks

- [ ] Create `tests/scenarios/` directory
- [ ] **Scenario 1:** Multi-agent dispatch (planner → coordinator → workers with memory augmentation)
- [ ] **Scenario 2:** Memory-augmented planning (RAG retrieval → plan enrichment → execution)
- [ ] **Scenario 3:** Profile-based isolation (demo vs demo_power vs production profiles)
- [ ] **Scenario 4:** Error recovery (tool failure → retry → fallback → partial success)
- [ ] **Scenario 5:** Stateful conversations (multi-turn with conversation_id continuity)
- [ ] **Scenario 6:** Complex workflows (nested orchestrations with parent_context)
- [ ] **Scenario 7:** Approval gates (budget escalation → HITL approval → continue/reject)
- [ ] **Scenario 8:** Budget enforcement (warn → escalate → block flow)

**Estimated Effort:** 8 scenarios, ~1,200 lines, 2-3 weeks

### Test Coverage Improvements (1-2 weeks)

**Goal:** Raise layer coverage from 30% → 80% (tools), 20% → 80% (memory)

#### Tools Layer Coverage (tools 30% → 80%)
- [ ] Add handler execution tests (success/failure/timeout/retry paths)
- [ ] Add budget tracking validation (cost accumulation, ceiling enforcement)
- [ ] Add parameter validation tests (all ParameterSchema cases: type/range/pattern/enum)
- [ ] Add network egress tests (SafeClient enforcement, allowlist/denylist)
- [ ] **Estimated:** 30 tests, 600 lines, 2 days

#### Memory Layer Coverage (memory 20% → 80%)
- [ ] Add profile isolation tests (no cross-profile leakage with concurrent access)
- [ ] Add retention tests (memory persistence, dirty flush on shutdown)
- [ ] Add vector backend switching tests (Chroma/Qdrant/in-memory fallback)
- [ ] Add embedding determinism tests (local fallback, no remote calls)
- [ ] **Estimated:** 25 tests, 500 lines, 2 days

---

## 🚀 v1.1 Timeline Estimate

| Phase | Work Item | Effort | Dependencies |
|-------|-----------|--------|--------------|
| Week 1 | Protocol shims | 2 days | None (start immediately) |
| Week 1 | Compliance tests | 2 days | Shims complete |
| Week 2-3 | Gradual migration | 5 days | Compliance tests passing |
| Week 2-3 | Scenario testing | 10 days | Parallel with migration |
| Week 3-4 | Coverage improvements | 4 days | Parallel with migration |
| Week 4 | Documentation | 3 days | All work complete |

**Total Estimated Effort:** 26 days (4-5 weeks with parallelization)

**Critical Path:** Protocol shims → Compliance tests → Gradual migration → Documentation

**Parallel Work:** Scenario testing and coverage improvements can happen alongside migration

---

## 🎯 Open Questions for Product Management

Before starting v1.1 work, need input on:

1. **Breaking Changes:** Is it acceptable to change agent signatures if we maintain backward compatibility wrappers?
2. **Migration Timeline:** Can we migrate calling code incrementally over multiple releases, or must it be atomic?
3. **User-Facing Benefits:** What's the user-visible value of protocol compliance? (vs internal architecture cleanup)
4. **Test Coverage Goals:** Is 80% layer coverage sufficient, or should we aim higher for critical paths?
5. **Scenario Testing Scope:** Are 8 scenarios sufficient, or should we cover more enterprise workflows?

---

## 🔧 Ongoing Maintenance & Enhancements

### Planner, Coordinator, and Tooling
- [ ] Finalize LangGraph-first planner/executor wiring with streaming callbacks
- [ ] Standardize lightweight developer checklist for planner/worker/registry changes

### Memory, RAG, and Embeddings
- [ ] Harden vector memory connectors with async batching and retention policies
- [ ] Document scoring semantics and deterministic local fallback search

### Deployment & API Profiles
- [ ] Add FastAPI LangServe-style deployment profile for hosted APIs
- [ ] Provide first-party compose profile with health checks

### Integrations & Adapters
- [ ] Build CrewAI/AutoGen adapters honoring coordinator/worker patterns
- [ ] Develop long-running planning mode inspired by Strands/Semantic Kernel

### Frontend & Workspace
- [ ] Polish frontend workspace/dashboard bundles (registry status, budgets, trace timelines)
- [ ] Ensure embedded asset pipeline stays deterministic

### Registry & Tier Enablement
- [ ] Complete Tier 1 registry composition (compose service mounts/env with health checks)
- [ ] Publish Tier 2 optional modules marked `enabled: false`
- [ ] Track watsonx credential validation and extension-aware registry parsing

## Documentation & Contributor Onboarding
- [x] Create single "System Execution Narrative" document tracing request → routing → agent → memory → response flow for contributor onboarding (completed: `docs/SYSTEM_EXECUTION_NARRATIVE.md` with CLI/FastAPI/MCP examples, complete flow diagrams, debugging tips, 20+ doc references).
- [x] Clarify FastAPI's role in architecture (transport vs orchestrator vs adapter) to prevent mixing transport and orchestration concerns (completed: `docs/architecture/FASTAPI_ROLE.md` defining FastAPI as transport layer only with clear boundaries, delegation patterns, anti-patterns, security roles, testing implications).
- [x] Document orchestrator API interface and agent lifecycle hooks explicitly with formal contract (lifecycle callbacks, failure semantics) (completed: `docs/orchestrator/README.md` - comprehensive API reference consolidating OrchestratorProtocol, lifecycle stages, failure modes, retry semantics, execution context, routing authority, integration patterns, testing requirements into single entry point).
- [x] Provide comprehensive end-to-end workflow examples for enterprise use cases (cross-system automation with error handling and HITL gates) (completed: `docs/examples/ENTERPRISE_WORKFLOWS.md` - 6 enterprise workflows with full implementations: customer onboarding with CRM/billing/approval, incident response with multi-system queries/remediation/escalation, data pipelines, invoice processing, security audits, sales qualification; includes reusable patterns, testing guidance, production checklists).
- [x] Add clear guidelines for observability, logging, tracing, and error introspection during agent execution (completed: `docs/observability/OBSERVABILITY_GUIDE.md` - comprehensive guide with structured logging, distributed tracing (OpenTelemetry/LangFuse/LangSmith), metrics collection (Prometheus/Grafana), error introspection with recovery suggestions, replayable traces for debugging, pre-built dashboards, troubleshooting playbooks for common issues).
- [x] Provide test coverage map aligned with architectural components showing which parts are tested and which aren't (completed: `docs/testing/TEST_COVERAGE_MAP.md` - comprehensive coverage map showing orchestrator 80%, agents 70%, routing 85%, failures 90%, tools 30%, memory 20%, config 0%, observability 0%; identifies critical gaps with priorities: tools security boundaries 70% gap 16h, memory data integrity 80% gap 24h, configuration precedence 100% gap 16h, observability integration 100% gap 24h; provides 3-phase testing roadmap, test fixtures inventory, CI/CD integration status).
- [x] Provide guided walkthrough for newcomers to set up and write first custom agent or extension (completed: `docs/DEVELOPER_ONBOARDING.md` - comprehensive 90-minute hands-on guide covering environment setup, first agent interaction, creating custom calculator tool with registry registration, building MathTutorAgent with lifecycle implementation, wiring components with memory + observability; includes full working examples, troubleshooting section, onboarding checklist, next steps for enhancement).
- Update inline code comments and docstrings to align with canonical contracts (OrchestratorProtocol, AgentLifecycle, ExecutionContext).
- Continue expanding example gallery with additional real-world scenarios (multi-turn conversations, RAG queries, tool composition).

## Release Engineering
- Prepare tagging and release automation aligned to `VERSION.txt` and `CHANGELOG.md` updates.
- Keep migration notes current for any breaking changes across MCP runners, registry behaviors, or sandbox policies.
- [ ] Flesh out Watsonx provider, Langflow export/import, and sandbox hardening
