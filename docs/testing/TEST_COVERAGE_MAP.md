# Test Coverage Map

**Status**: Canonical Reference  
**Last Updated**: 2025-12-31  
**Audience**: Contributors, QA engineers, maintainers

---

## 📋 Overview

This document provides a comprehensive test coverage map aligned with major architectural components of the CUGAR agent system. It shows what's tested, what's not, coverage gaps, and priorities for additional testing.

### Coverage Summary

| Component | Unit Tests | Integration Tests | Scenario Tests | Coverage % | Status |
|-----------|-----------|-------------------|----------------|------------|--------|
| **Orchestrator** | 35+ | 5+ | 8+ | 80% | ✅ Good |
| **Agents** | 30+ | 10+ | 8+ | 70% | ⚠️ Needs Improvement |
| **Routing** | 25+ | 5+ | 3+ | 85% | ✅ Good |
| **Failure Modes** | 60+ | 10+ | 5+ | 90% | ✅ Excellent |
| **Agent Lifecycle** | 30+ | 5+ | 3+ | 75% | ✅ Good |
| **Agent Contracts** | 35+ | 8+ | 2+ | 80% | ✅ Good |
| **Tools/Registry** | 10+ | 5+ | 1+ | 30% | ❌ Critical Gap |
| **Memory/RAG** | 5+ | 0 | 1+ | 20% | ❌ Critical Gap |
| **Configuration** | 0 | 0 | 0 | 0% | ❌ Untested |
| **Observability** | 0 | 0 | 0 | 0% | ❌ Untested |

**Overall Coverage**: ~60% (estimated from architectural layers)

---

## 🎯 Component Coverage Breakdown

### 1. Orchestrator (80% Coverage) ✅

**Location**: `src/cuga/orchestrator/`, `tests/test_orchestrator_protocol.py`

#### ✅ What's Tested

**Lifecycle Compliance** (15 tests):
```python
# tests/test_orchestrator_protocol.py
✓ test_lifecycle_stages_in_order          # Stages emitted in correct order
✓ test_terminal_stage_is_final            # COMPLETE/FAILED/CANCELLED are terminal
✓ test_initialize_before_plan             # INITIALIZE must precede PLAN
✓ test_plan_before_route                  # PLAN must precede ROUTE
✓ test_route_before_execute               # ROUTE must precede EXECUTE
✓ test_execute_may_repeat                 # EXECUTE can repeat for multi-step
✓ test_aggregate_before_complete          # AGGREGATE before terminal stage
✓ test_invalid_stage_transitions          # Invalid transitions raise error
✓ test_lifecycle_events_include_context   # All events include ExecutionContext
✓ test_lifecycle_stage_enum               # LifecycleStage enum values
✓ test_orchestrate_yields_events          # orchestrate() is async generator
✓ test_orchestrate_error_propagation      # Errors propagate correctly
✓ test_orchestrate_cancellation           # User cancellation handling
✓ test_orchestrate_timeout                # Timeout handling
✓ test_orchestrate_with_error_strategy    # Error strategy parameter
```

**Trace Propagation** (10 tests):
```python
✓ test_trace_id_preserved                 # trace_id flows through all events
✓ test_profile_preserved                  # profile preserved
✓ test_context_immutability               # ExecutionContext is immutable
✓ test_trace_id_required                  # trace_id is mandatory
✓ test_nested_orchestration_trace         # parent_context chaining
✓ test_trace_id_propagation_to_workers    # trace_id passed to workers
✓ test_trace_id_propagation_to_tools      # trace_id passed to tools
✓ test_trace_context_vars                 # Context vars propagate
✓ test_span_hierarchy                     # Spans nested correctly
✓ test_trace_correlation                  # Events correlate by trace_id
```

**Routing** (10 tests):
```python
✓ test_routing_decision_deterministic     # Same inputs → same decision
✓ test_routing_decision_includes_reason   # Decisions justified
✓ test_routing_decision_has_fallback      # Fallback specified
✓ test_routing_decision_logged            # Decisions logged
✓ test_make_routing_decision_signature    # Correct signature
✓ test_routing_delegates_to_authority     # Delegates to RoutingAuthority
✓ test_no_orchestrator_routing_bypass     # Must use RoutingAuthority
✓ test_routing_decision_metadata          # Metadata included
✓ test_routing_target_validation          # Target must be in available list
✓ test_routing_with_empty_targets         # Error if no targets
```

#### ❌ What's NOT Tested

**Missing Tests** (estimated 20% gap):
- [ ] Error propagation with partial results preservation
- [ ] Long-running orchestration (>5 minutes)
- [ ] Orchestration pausing and resuming
- [ ] Memory pressure handling during orchestration
- [ ] Concurrent orchestrations with shared resources
- [ ] Orchestration metrics collection
- [ ] Orchestration abort/cleanup
- [ ] Custom error strategies beyond built-ins
- [ ] Orchestration state snapshots
- [ ] Recovery from orchestrator crashes

**Priority**: Medium (production-ready for most use cases)

---

### 2. Agents (70% Coverage) ⚠️

**Location**: `src/cuga/agents/`, `src/cuga/modular/agents.py`, `tests/test_agent_*.py`

#### ✅ What's Tested

**Agent Lifecycle** (30+ tests):
```python
# tests/test_agent_lifecycle.py
✓ test_initial_state                      # Agents start UNINITIALIZED
✓ test_startup_transitions_to_ready       # startup() → READY
✓ test_startup_idempotency                # startup() safe to call multiple times
✓ test_shutdown_transitions_to_terminated # shutdown() → TERMINATED
✓ test_shutdown_idempotency               # shutdown() safe to call multiple times
✓ test_shutdown_never_raises              # shutdown() never throws
✓ test_startup_failure_cleanup            # Rollback on startup error
✓ test_ephemeral_state_cleared_on_shutdown # AGENT state cleared
✓ test_context_manager_lifecycle          # async with agent: ...
✓ test_context_manager_cleanup_on_error   # Cleanup on exception
✓ test_state_ownership_agent              # AGENT state boundaries
✓ test_state_ownership_memory             # MEMORY state boundaries
✓ test_state_ownership_orchestrator       # ORCHESTRATOR state boundaries
✓ test_metrics_collection                 # Lifecycle metrics
✓ test_requires_state_decorator_allows    # @requires_state works
✓ test_requires_state_decorator_blocks    # @requires_state blocks invalid
✓ test_agent_lifecycle_context_manager    # Context manager protocol
✓ test_agent_lifecycle_with_config        # Config support
✓ test_lifecycle_config_timeout           # Timeout configuration
✓ test_lifecycle_config_retry             # Retry configuration
✓ test_full_lifecycle                     # Complete lifecycle
✓ test_concurrent_agents                  # Multiple agents concurrently
✓ test_startup_error_propagation          # Error propagation
✓ test_shutdown_error_logged_not_raised   # Shutdown errors logged
✓ test_agent_lifecycle_compliance         # Compliance test suite
✓ test_all_agents_comply                  # All agents tested
```

**Agent Contracts (I/O)** (35+ tests):
```python
# tests/test_agent_contracts.py
✓ test_agent_request_required_fields      # AgentRequest validation
✓ test_agent_request_optional_fields      # Optional fields
✓ test_agent_request_with_all_fields      # Complete request
✓ test_agent_request_validation           # Schema validation
✓ test_agent_request_to_dict              # Serialization
✓ test_agent_request_from_dict            # Deserialization
✓ test_agent_response_success             # Success response
✓ test_agent_response_error               # Error response
✓ test_agent_response_partial             # Partial success
✓ test_agent_response_validation          # Schema validation
✓ test_agent_response_is_success          # Status checking
✓ test_agent_response_is_recoverable      # Recoverable flag
✓ test_agent_accepts_request              # Agent processes AgentRequest
✓ test_agent_returns_response             # Agent returns AgentResponse
✓ test_agent_propagates_trace_id          # trace_id flows through
✓ test_agent_handles_errors_without_raising # Errors returned, not raised
✓ test_agent_returns_structured_errors    # Error structure
✓ test_agent_includes_trace_events        # Trace events included
✓ test_agent_includes_metadata            # Metadata included
✓ test_timeout_error_structure            # Timeout errors
✓ test_validate_request_valid             # Request validation
✓ test_validate_request_invalid           # Invalid request
✓ test_validate_response_valid            # Response validation
✓ test_validate_response_invalid          # Invalid response
✓ test_request_roundtrip                  # Serialization roundtrip
✓ test_response_roundtrip                 # Serialization roundtrip
✓ test_agent_io_compliance                # Compliance suite
✓ test_all_agents_comply                  # All agents tested
```

**Agent Composition (Scenario Tests)** (8 tests):
```python
# tests/scenario/test_agent_composition.py
✓ test_multi_agent_dispatch               # Round-robin coordination
✓ test_memory_augmented_planning          # Memory influences planning
✓ test_profile_based_isolation            # Profile isolation
✓ test_error_recovery_with_retries        # Retry logic
✓ test_streaming_execution                # Event streaming
✓ test_stateful_conversations             # Session persistence
✓ test_complex_workflow                   # Multi-step pipeline
✓ test_nested_coordination                # Parent → child orchestrators
```

#### ❌ What's NOT Tested

**Missing Tests** (estimated 30% gap):
- [ ] PlannerAgent tool ranking algorithm correctness
- [ ] PlannerAgent memory search integration
- [ ] WorkerAgent sandbox execution with real sandboxes
- [ ] WorkerAgent budget enforcement
- [ ] CoordinatorAgent worker failure handling
- [ ] CoordinatorAgent worker health checking
- [ ] Agent hot-reload / dynamic registration
- [ ] Agent versioning and migration
- [ ] Agent resource limits (memory, CPU)
- [ ] Agent telemetry and instrumentation
- [ ] Agent-to-agent communication patterns
- [ ] Agent capability discovery
- [ ] Agent pool management
- [ ] Agent load balancing beyond round-robin
- [ ] Agent graceful degradation

**Priority**: High (core functionality needs more coverage)

---

### 3. Routing (85% Coverage) ✅

**Location**: `src/cuga/orchestrator/routing.py`, `tests/test_routing_authority.py`

#### ✅ What's Tested

**Routing Context** (3 tests):
```python
# tests/test_routing_authority.py
✓ test_context_is_frozen                  # RoutingContext immutable
✓ test_context_with_goal                  # Goal-based routing
✓ test_context_with_task                  # Task-based routing
```

**Routing Decision** (3 tests):
```python
✓ test_decision_requires_reason           # Reason mandatory
✓ test_decision_validates_confidence      # Confidence in [0, 1]
✓ test_decision_with_alternatives         # Alternative targets
```

**Round-Robin Policy** (4 tests):
```python
✓ test_round_robin_cycles_workers         # Cycles through workers
✓ test_round_robin_filters_unavailable    # Filters unavailable
✓ test_round_robin_no_candidates_error    # Error if none available
✓ test_round_robin_thread_safe            # Thread-safe counter
```

**Capability-Based Policy** (2 tests):
```python
✓ test_capability_matches_requirements    # Matches capabilities
✓ test_capability_no_requirements         # Handles no requirements
```

**Routing Authority** (3 tests):
```python
✓ test_authority_delegates_to_agent_policy   # Agent routing delegation
✓ test_authority_delegates_to_worker_policy  # Worker routing delegation
✓ test_authority_defaults                    # Default policies
```

**Routing Compliance** (3 tests):
```python
✓ test_no_agent_routing_bypass            # Agents must use authority
✓ test_orchestrator_delegates_routing     # Orchestrators delegate
✓ test_no_fastapi_routing_decisions       # FastAPI cannot route
```

**Routing Observability** (1 test):
```python
✓ test_routing_decision_logged            # Decisions logged
```

#### ❌ What's NOT Tested

**Missing Tests** (estimated 15% gap):
- [ ] Load-based routing policy
- [ ] Geographic/affinity-based routing
- [ ] Custom routing policies
- [ ] Routing policy chaining
- [ ] Routing decision caching
- [ ] Routing with degraded workers
- [ ] Routing fallback chain execution
- [ ] Routing metrics collection

**Priority**: Low (core functionality well-covered)

---

### 4. Failure Modes (90% Coverage) ✅

**Location**: `src/cuga/orchestrator/failures.py`, `tests/test_failure_modes.py`

#### ✅ What's Tested

**Failure Classification** (25+ tests):
```python
# tests/test_failure_modes.py
✓ test_agent_validation_failure           # AGENT_VALIDATION
✓ test_agent_timeout_failure              # AGENT_TIMEOUT
✓ test_agent_logic_failure                # AGENT_LOGIC
✓ test_agent_contract_failure             # AGENT_CONTRACT
✓ test_agent_state_failure                # AGENT_STATE
✓ test_system_network_failure             # SYSTEM_NETWORK
✓ test_system_timeout_failure             # SYSTEM_TIMEOUT
✓ test_system_crash_failure               # SYSTEM_CRASH
✓ test_system_oom_failure                 # SYSTEM_OOM
✓ test_system_disk_failure                # SYSTEM_DISK
✓ test_resource_tool_unavailable          # RESOURCE_TOOL_UNAVAILABLE
✓ test_resource_api_unavailable           # RESOURCE_API_UNAVAILABLE
✓ test_resource_memory_full               # RESOURCE_MEMORY_FULL
✓ test_resource_quota                     # RESOURCE_QUOTA
✓ test_resource_circuit_open              # RESOURCE_CIRCUIT_OPEN
✓ test_policy_security                    # POLICY_SECURITY
✓ test_policy_budget                      # POLICY_BUDGET
✓ test_policy_allowlist                   # POLICY_ALLOWLIST
✓ test_policy_rate_limit                  # POLICY_RATE_LIMIT
✓ test_user_invalid_input                 # USER_INVALID_INPUT
✓ test_user_cancelled                     # USER_CANCELLED
✓ test_user_permission                    # USER_PERMISSION
✓ test_partial_tool_failures              # PARTIAL_TOOL_FAILURES
✓ test_partial_step_failures              # PARTIAL_STEP_FAILURES
✓ test_partial_timeout                    # PARTIAL_TIMEOUT
```

**Failure Properties** (10 tests):
```python
✓ test_failure_mode_category              # Correct category
✓ test_failure_mode_retryable             # Retryable flag
✓ test_failure_mode_terminal              # Terminal flag
✓ test_failure_mode_partial_results       # Partial results flag
✓ test_failure_mode_severity              # Severity level
✓ test_auto_detect_from_exception         # Auto-detection
✓ test_classify_connection_error          # Connection errors
✓ test_classify_timeout_error             # Timeout errors
✓ test_classify_validation_error          # Validation errors
✓ test_classify_unknown_error             # Unknown errors
```

**Retry Policies** (15 tests):
```python
✓ test_exponential_backoff_policy         # Exponential backoff
✓ test_exponential_backoff_with_jitter    # Jitter randomization
✓ test_exponential_backoff_max_delay      # Max delay cap
✓ test_exponential_backoff_max_attempts   # Max attempts
✓ test_linear_backoff_policy              # Linear backoff
✓ test_no_retry_policy                    # No retry
✓ test_retry_generator                    # Generator pattern
✓ test_retry_attempt_metadata             # Attempt metadata
✓ test_should_retry_logic                 # Retry decision logic
✓ test_retry_with_circuit_breaker         # Circuit breaker integration
✓ test_retry_exhausted                    # Max attempts reached
✓ test_retry_policy_from_failure_mode     # Policy from mode
✓ test_custom_retry_policy                # Custom policies
✓ test_conditional_retry                  # Conditional retry
✓ test_retry_with_timeout                 # Retry + timeout
```

**Partial Results** (5 tests):
```python
✓ test_partial_result_capture             # Capture partial results
✓ test_partial_result_recovery            # Recovery from partial
✓ test_partial_result_metadata            # Metadata preservation
✓ test_partial_result_serialization       # Serialization
✓ test_partial_result_aggregation         # Aggregation logic
```

**Error Context** (5 tests):
```python
✓ test_error_context_capture              # Full context capture
✓ test_error_context_stack_trace          # Stack traces
✓ test_error_context_cause_chain          # Cause chains
✓ test_error_context_recovery_suggestions # Suggestions
✓ test_error_context_runbook_urls         # Runbook links
```

#### ❌ What's NOT Tested

**Missing Tests** (estimated 10% gap):
- [ ] Failure mode statistics/analytics
- [ ] Failure trend detection
- [ ] Failure correlation analysis
- [ ] Cascading failure detection
- [ ] Failure recovery patterns
- [ ] Custom failure mode registration

**Priority**: Low (excellent coverage)

---

### 5. Tools & Registry (30% Coverage) ❌

**Location**: `src/cuga/modular/tools/`, `src/cuga/registry/`, `tests/unit/test_registry_sandboxing.py`

#### ✅ What's Tested

**Registry Loading** (1 test):
```python
# tests/unit/test_registry_sandboxing.py
✓ test_registry_loading                   # Load registry.yaml
```

**Sandbox Execution** (7 tests):
```python
✓ test_successful_execution               # Tool executes successfully
✓ test_runtime_error_capture              # Errors captured
✓ test_wall_clock_timeout                 # Wall clock timeout
✓ test_cpu_time_limit                     # CPU time limit
✓ test_memory_limit                       # Memory limit
✓ test_non_existent_tool                  # Missing tool error
✓ test_tool_with_no_sandbox               # No sandbox config
```

#### ❌ What's NOT Tested (70% GAP - CRITICAL)

**Tool Registration**:
- [ ] Dynamic tool registration
- [ ] Tool allowlist enforcement
- [ ] Tool denylist enforcement
- [ ] Tool version management
- [ ] Tool capability metadata
- [ ] Tool discovery
- [ ] Tool hot-reload
- [ ] Tool deprecation warnings

**Tool Execution**:
- [ ] Tool input validation
- [ ] Tool output validation
- [ ] Tool parameter schemas
- [ ] Tool handler signature checking
- [ ] Tool execution tracing
- [ ] Tool execution metrics
- [ ] Tool budget tracking
- [ ] Tool concurrency limits

**Sandbox Profiles**:
- [ ] py-slim profile isolation
- [ ] py-full profile isolation
- [ ] node-slim profile isolation
- [ ] node-full profile isolation
- [ ] Sandbox mount validation
- [ ] Sandbox read-only enforcement
- [ ] Sandbox workdir pinning
- [ ] Sandbox network restrictions

**Tool Security**:
- [ ] Import allowlist enforcement (`cuga.modular.tools.*`)
- [ ] Import denylist enforcement
- [ ] Path traversal prevention
- [ ] Code injection prevention
- [ ] Environment variable isolation
- [ ] Resource exhaustion prevention

**Tool Integration**:
- [ ] MCP tool integration
- [ ] HTTP tool integration
- [ ] Custom tool plugins
- [ ] Tool composition
- [ ] Tool chaining

**Priority**: **CRITICAL** (security boundaries untested, production blocker)

---

### 6. Memory & RAG (20% Coverage) ❌

**Location**: `src/cuga/modular/memory.py`, `src/cuga/rag/`, `tests/scenario/test_agent_composition.py`

#### ✅ What's Tested

**Memory in Workflows** (2 scenario tests):
```python
# tests/scenario/test_agent_composition.py
✓ test_memory_augmented_planning          # Memory influences planning
✓ test_stateful_conversations             # Session persistence
```

#### ❌ What's NOT Tested (80% GAP - CRITICAL)

**Vector Memory**:
- [ ] VectorMemory initialization
- [ ] VectorMemory search (similarity)
- [ ] VectorMemory remember (insertion)
- [ ] VectorMemory forget (deletion)
- [ ] VectorMemory update
- [ ] VectorMemory metadata filtering
- [ ] VectorMemory score thresholds
- [ ] VectorMemory top-k retrieval
- [ ] VectorMemory profile isolation
- [ ] VectorMemory persistence
- [ ] VectorMemory backend switching (local/chroma/qdrant)

**Embeddings**:
- [ ] Deterministic hashing embedder
- [ ] Embedding dimension validation
- [ ] Embedding normalization
- [ ] Embedding offline enforcement
- [ ] Custom embedder registration

**RAG Operations**:
- [ ] Document ingestion
- [ ] Document chunking
- [ ] Document metadata extraction
- [ ] Query augmentation
- [ ] Context retrieval
- [ ] Source attribution
- [ ] Relevance scoring

**Memory Backends**:
- [ ] Local (in-memory) backend
- [ ] Chroma backend integration
- [ ] Qdrant backend integration
- [ ] Weaviate backend integration
- [ ] Milvus backend integration
- [ ] Backend failover
- [ ] Backend health checks

**Profile Isolation**:
- [ ] Cross-profile leakage prevention
- [ ] Profile-scoped search
- [ ] Profile cleanup
- [ ] Profile migration

**Priority**: **CRITICAL** (data persistence untested, production blocker)

---

### 7. Configuration (0% Coverage) ❌

**Location**: `src/cuga/config/`, `src/cuga/modular/config.py`, `configs/`

#### ❌ What's NOT Tested (100% GAP - CRITICAL)

**Config Resolution**:
- [ ] Precedence layers (CLI → env → .env → YAML → TOML → defaults)
- [ ] Deep merge for dicts
- [ ] Override for lists/scalars
- [ ] Schema validation
- [ ] Provenance tracking
- [ ] Config hot-reload
- [ ] Config validation errors
- [ ] Config defaults

**Config Sources**:
- [ ] Hydra registry loading
- [ ] Dynaconf settings loading
- [ ] YAML config parsing
- [ ] TOML config parsing
- [ ] .env file parsing
- [ ] Environment variable parsing
- [ ] CLI argument parsing

**Config Management**:
- [ ] Config profiles
- [ ] Config inheritance
- [ ] Config overrides
- [ ] Config encryption (secrets)
- [ ] Config versioning
- [ ] Config migration

**Environment Modes**:
- [ ] Local mode validation
- [ ] Service mode validation
- [ ] MCP mode validation
- [ ] Test mode defaults
- [ ] Required vars per mode
- [ ] Optional vars per mode

**Priority**: **CRITICAL** (configuration untested, production blocker)

---

### 8. Observability (0% Coverage) ❌

**Location**: `src/cuga/observability/`, `docs/observability/OBSERVABILITY_GUIDE.md`

#### ❌ What's NOT Tested (100% GAP - CRITICAL)

**Structured Logging**:
- [ ] JSON log format validation
- [ ] Required fields (trace_id, level, etc.)
- [ ] PII redaction
- [ ] Secret redaction (password, token, api_key)
- [ ] Log level filtering
- [ ] Log output routing (stdout/file)
- [ ] Log rotation
- [ ] Log aggregation

**Distributed Tracing**:
- [ ] OpenTelemetry span creation
- [ ] Span hierarchy (parent/child)
- [ ] Trace context propagation (async)
- [ ] Trace context propagation (threads)
- [ ] Trace sampling
- [ ] Trace export (OTLP)
- [ ] LangFuse integration
- [ ] LangSmith integration

**Metrics**:
- [ ] Prometheus metric registration
- [ ] Counter increments
- [ ] Histogram observations
- [ ] Gauge updates
- [ ] Metric labels
- [ ] Metric cardinality limits
- [ ] Metric scraping endpoint

**Error Introspection**:
- [ ] ErrorContext capture
- [ ] Stack trace preservation
- [ ] Cause chain capture
- [ ] Recovery suggestions
- [ ] Runbook URL generation
- [ ] Error storage
- [ ] Error querying

**Replayable Traces**:
- [ ] Trace recording
- [ ] Trace storage
- [ ] Trace replay
- [ ] Trace step-through
- [ ] Trace state inspection

**Priority**: **CRITICAL** (observability untested, production blocker)

---

## 🎯 Test Type Breakdown

### Unit Tests

**Definition**: Test individual functions/classes in isolation with mocked dependencies.

**Current Count**: ~150 tests

**Coverage**:
- ✅ Orchestrator protocol: 35 tests
- ✅ Agent lifecycle: 30 tests
- ✅ Agent contracts: 35 tests
- ✅ Routing: 25 tests
- ✅ Failure modes: 60 tests
- ⚠️ Tools/registry: 10 tests
- ❌ Memory: 0 tests
- ❌ Configuration: 0 tests
- ❌ Observability: 0 tests

**Gaps**: Tools, memory, configuration, observability completely untested.

---

### Integration Tests

**Definition**: Test component interactions with real dependencies (databases, external services).

**Current Count**: ~50 tests (embedded in unit/scenario tests)

**Coverage**:
- ✅ Orchestrator + Agents: 10 tests
- ✅ Agents + Memory: 5 tests (scenario tests)
- ✅ Routing + Workers: 8 tests
- ⚠️ Tools + Sandbox: 5 tests
- ❌ Memory + Backends: 0 tests
- ❌ Config + Sources: 0 tests
- ❌ Observability + Exporters: 0 tests

**Gaps**: No integration tests for memory backends, config sources, observability exporters.

---

### Scenario/E2E Tests

**Definition**: Test complete workflows from entry to exit with real components.

**Current Count**: ~15 tests

**Coverage**:
```python
# tests/scenario/test_agent_composition.py (8 tests)
✓ Multi-agent dispatch (CrewAI/AutoGen patterns)
✓ Memory-augmented planning
✓ Profile-based isolation
✓ Error recovery with retries
✓ Streaming execution
✓ Stateful conversations
✓ Complex workflows (5+ steps)
✓ Nested coordination

# tests/scenario/test_stateful_agent.py (7 tests)
✓ Session state persistence
✓ Conversation continuity
✓ Context carryover
✓ Multi-turn interactions
✓ State cleanup
✓ Concurrent sessions
✓ State isolation
```

**Gaps**: No scenario tests for:
- [ ] CLI mode end-to-end
- [ ] FastAPI mode end-to-end
- [ ] MCP mode end-to-end
- [ ] RAG query workflow
- [ ] Tool composition workflow
- [ ] Observability integration
- [ ] Error recovery patterns (comprehensive)

---

## 📊 Coverage by Architectural Layer

### Layer 1: Transport (FastAPI)

**Coverage**: ~40%

**Tested**:
- ✅ Routing delegation (no routing logic in FastAPI)
- ✅ Budget enforcement concept (via tests)

**Untested**:
- [ ] HTTP request parsing
- [ ] SSE streaming
- [ ] Authentication (X-Token)
- [ ] Budget middleware (AGENT_BUDGET_CEILING)
- [ ] Trace propagation (X-Trace-Id)
- [ ] Error response formatting
- [ ] Rate limiting
- [ ] Request validation

**Priority**: High

---

### Layer 2: Orchestration

**Coverage**: ~75%

**Tested**:
- ✅ Lifecycle management (80%)
- ✅ Routing authority (85%)
- ✅ Error propagation (90%)
- ✅ Trace continuity (80%)

**Untested**:
- [ ] Orchestration metrics
- [ ] Orchestration pausing
- [ ] State snapshots
- [ ] Recovery from crashes

**Priority**: Medium

---

### Layer 3: Agents

**Coverage**: ~70%

**Tested**:
- ✅ Lifecycle (75%)
- ✅ I/O contracts (80%)
- ✅ Multi-agent composition (70%)

**Untested**:
- [ ] PlannerAgent algorithm
- [ ] WorkerAgent sandboxing
- [ ] CoordinatorAgent failure handling
- [ ] Agent pool management

**Priority**: High

---

### Layer 4: Tools & Execution

**Coverage**: ~25%

**Tested**:
- ✅ Basic sandbox execution (30%)

**Untested**:
- [ ] Tool registration (0%)
- [ ] Tool security (0%)
- [ ] Tool budget tracking (0%)
- [ ] MCP integration (0%)

**Priority**: **CRITICAL**

---

### Layer 5: Memory & RAG

**Coverage**: ~15%

**Tested**:
- ✅ Memory in workflows (20%)

**Untested**:
- [ ] VectorMemory operations (0%)
- [ ] Embeddings (0%)
- [ ] RAG operations (0%)
- [ ] Backend integrations (0%)

**Priority**: **CRITICAL**

---

### Layer 6: Configuration

**Coverage**: 0%

**Tested**: None

**Untested**: Everything

**Priority**: **CRITICAL**

---

### Layer 7: Observability

**Coverage**: 0%

**Tested**: None

**Untested**: Everything

**Priority**: **CRITICAL**

---

## 🚨 Critical Gaps (Production Blockers)

### Gap 1: Tool Security Boundaries

**Risk**: High - Malicious or buggy tools could escape sandbox, access unauthorized resources.

**Untested**:
- Import allowlist enforcement (`cuga.modular.tools.*`)
- Import denylist (external modules)
- Path traversal prevention
- Code injection prevention
- Sandbox read-only mount enforcement

**Impact**: Security vulnerability, potential data breach.

**Effort**: 16 hours (20 tests)

**Priority**: **CRITICAL** - Blocks production deployment

---

### Gap 2: Memory Data Integrity

**Risk**: High - Memory operations untested, could corrupt data or leak across profiles.

**Untested**:
- VectorMemory CRUD operations
- Profile isolation (cross-profile leakage)
- Backend persistence
- Data consistency

**Impact**: Data loss, privacy violation, incorrect results.

**Effort**: 24 hours (30 tests)

**Priority**: **CRITICAL** - Blocks production deployment

---

### Gap 3: Configuration Precedence

**Risk**: Medium - Config bugs could lead to incorrect behavior, security misconfig.

**Untested**:
- Config resolution order
- Environment variable validation
- Required vs optional vars per mode
- Config schema validation

**Impact**: Runtime errors, security misconfigurations.

**Effort**: 16 hours (20 tests)

**Priority**: **HIGH** - Reduces deployment reliability

---

### Gap 4: Observability Integration

**Risk**: Medium - Cannot debug production issues without observability.

**Untested**:
- Structured logging
- Trace propagation
- Metrics collection
- Error introspection

**Impact**: Difficult to debug production issues, poor operational visibility.

**Effort**: 24 hours (30 tests)

**Priority**: **HIGH** - Reduces operational effectiveness

---

## 📈 Recommended Test Priorities

### Phase 1: Critical Path Coverage (40 hours)

**Goal**: Cover production blockers

1. **Tool Security** (16 hours)
   - Import allowlist/denylist enforcement
   - Sandbox isolation validation
   - Path traversal prevention
   - Resource limit enforcement

2. **Memory Operations** (24 hours)
   - VectorMemory CRUD
   - Profile isolation
   - Backend persistence
   - Search/retrieve accuracy

**Success Criteria**: 80% coverage for tools and memory layers.

---

### Phase 2: Configuration & Observability (40 hours)

**Goal**: Cover operational requirements

1. **Configuration** (16 hours)
   - Config resolution precedence
   - Environment mode validation
   - Schema validation
   - Config hot-reload

2. **Observability** (24 hours)
   - Structured logging tests
   - Trace propagation tests
   - Metrics collection tests
   - Error introspection tests

**Success Criteria**: 60% coverage for config and observability.

---

### Phase 3: Integration Suite (40 hours)

**Goal**: Cover end-to-end workflows

1. **Entry Point Tests** (20 hours)
   - CLI mode E2E
   - FastAPI mode E2E
   - MCP mode E2E

2. **Workflow Tests** (20 hours)
   - RAG query workflow
   - Tool composition workflow
   - Error recovery patterns
   - Performance/load tests

**Success Criteria**: All major workflows tested E2E.

---

## 🛠️ Testing Infrastructure

### Test Fixtures

**Location**: `tests/conftest.py` (implied)

**Available Fixtures**:
- `orchestrator` - Test orchestrator instance
- `context` - ExecutionContext for tests
- `agent_implementation` - Parametrized agent fixtures

**Missing Fixtures**:
- [ ] `memory_backend` - Real memory backends
- [ ] `tool_registry` - Pre-configured registry
- [ ] `sandbox_profile` - Sandbox profiles
- [ ] `config_resolver` - Config resolver
- [ ] `observability_emitter` - Observability exporters

---

### Test Utilities

**Available**:
- Compliance test suites (lifecycle, contracts, routing)
- Mock implementations (agents, workers)

**Missing**:
- [ ] Trace verification utilities
- [ ] Memory assertion helpers
- [ ] Config test builders
- [ ] Sandbox test harnesses
- [ ] Observability test collectors

---

### CI/CD Integration

**Status**: Partially configured

**Available**:
- `.github/workflows/tests.yml` (implied)
- Test execution on PR

**Missing**:
- [ ] Coverage reporting
- [ ] Coverage gates (80% minimum)
- [ ] Performance regression tests
- [ ] Chaos/fuzz testing
- [ ] Test result dashboards

---

## 📚 Test Documentation

### Test Organization

```
tests/
├── __init__.py
├── conftest.py                          # Fixtures (needs expansion)
├── test_orchestrator_protocol.py       # ✅ Orchestrator (35 tests)
├── test_agent_lifecycle.py             # ✅ Lifecycle (30 tests)
├── test_agent_contracts.py             # ✅ Contracts (35 tests)
├── test_routing_authority.py           # ✅ Routing (25 tests)
├── test_failure_modes.py               # ✅ Failures (60 tests)
├── unit/
│   ├── test_registry_sandboxing.py     # ⚠️ Registry (10 tests)
│   ├── test_tools.py                   # ❌ Missing
│   ├── test_memory.py                  # ❌ Missing
│   ├── test_config.py                  # ❌ Missing
│   └── test_observability.py           # ❌ Missing
├── integration/                         # ❌ Missing directory
│   ├── test_memory_backends.py         # ❌ Missing
│   ├── test_config_sources.py          # ❌ Missing
│   └── test_observability_exporters.py # ❌ Missing
└── scenario/
    ├── test_agent_composition.py       # ✅ Composition (8 tests)
    ├── test_stateful_agent.py          # ✅ Stateful (7 tests)
    ├── test_cli_workflow.py            # ❌ Missing
    ├── test_fastapi_workflow.py        # ❌ Missing
    ├── test_mcp_workflow.py            # ❌ Missing
    ├── test_rag_workflow.py            # ❌ Missing
    └── test_error_recovery.py          # ❌ Missing
```

---

### Test Naming Conventions

**Current Conventions**:
- Unit tests: `test_<component>_<behavior>`
- Compliance tests: `test_<component>_compliance`
- Scenario tests: `test_<use_case>`

**Examples**:
```python
# Unit test
def test_orchestrator_lifecycle_stages_in_order():
    ...

# Compliance test
async def test_agent_lifecycle_compliance(agent: AgentLifecycleProtocol):
    ...

# Scenario test
async def test_multi_agent_dispatch_with_error_recovery():
    ...
```

---

## 🔍 Coverage Measurement

### Running Coverage Reports

```bash
# Run tests with coverage
pytest --cov=src/cuga --cov-report=html --cov-report=term

# View HTML report
open htmlcov/index.html

# Coverage by component
pytest --cov=src/cuga/orchestrator --cov-report=term
pytest --cov=src/cuga/agents --cov-report=term
pytest --cov=src/cuga/modular/tools --cov-report=term
```

### Coverage Goals

| Component | Current | Target | Gap |
|-----------|---------|--------|-----|
| Orchestrator | 80% | 85% | 5% |
| Agents | 70% | 85% | 15% |
| Routing | 85% | 90% | 5% |
| Failures | 90% | 95% | 5% |
| **Tools** | **30%** | **80%** | **50%** ❌ |
| **Memory** | **20%** | **80%** | **60%** ❌ |
| **Config** | **0%** | **70%** | **70%** ❌ |
| **Observability** | **0%** | **70%** | **70%** ❌ |
| **Overall** | **60%** | **80%** | **20%** |

---

## 📋 Related Documentation

- **[Scenario Testing Guide](SCENARIO_TESTING.md)** - End-to-end test patterns
- **[Orchestrator Interface](../orchestrator/README.md)** - Orchestrator testing requirements
- **[Agent Lifecycle](../agents/AGENT_LIFECYCLE.md)** - Lifecycle testing requirements
- **[Observability Guide](../observability/OBSERVABILITY_GUIDE.md)** - Observability testing patterns
- **[Enterprise Workflows](../examples/ENTERPRISE_WORKFLOWS.md)** - Workflow testing examples

---

**For questions or contributions, see [CONTRIBUTING.md](../../CONTRIBUTING.md).**
