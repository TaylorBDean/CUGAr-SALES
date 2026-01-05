# Orchestrator Hardening Roadmap

**Status**: Active Development  
**Target Date**: 2026-01-15 (2 weeks)  
**Owner**: Core Architecture Team  
**Goal**: 100% production-hardened orchestrator before modular tool integration

---

## Executive Summary

**Current State**: 
- ✅ OrchestratorProtocol fully defined with ReferenceOrchestrator
- ✅ Tool execution infrastructure ready (WorkerAgent with observability)
- ⚠️ CoordinatorAgent is simplified dispatcher, not full orchestrator
- ⚠️ Advanced features defined but not integrated (30% complete)

**Target State**:
- ✅ CoordinatorAgent implements OrchestratorProtocol (100%)
- ✅ All authorities integrated (RoutingAuthority, PlanningAuthority, AuditTrail)
- ✅ Retry/failure handling with partial result preservation
- ✅ Approval gates (HITL) for sensitive operations
- ✅ Comprehensive tool integration documentation
- ✅ 100% test coverage for orchestration paths

**Timeline**: 10 tasks, ~20-25 hours, 2 weeks with parallel work

---

## Current Architecture Analysis

### What's Already Excellent ✅

```
src/cuga/orchestrator/
├── protocol.py              ✅ OrchestratorProtocol (canonical contract)
├── reference.py             ✅ ReferenceOrchestrator (working implementation)
├── planning.py              ✅ PlanningAuthority, Plan, ToolBudget
├── routing.py               ✅ RoutingAuthority, RoutingPolicy interfaces
├── failure_modes.py         ✅ FailureMode, RetryPolicy, PartialResult
└── protocol.py              ✅ ExecutionContext, LifecycleStage, ErrorPropagation

src/cuga/modular/
├── tools.py                 ✅ ToolRegistry, ToolSpec (allowlist enforcement)
├── memory.py                ✅ VectorMemory (profile isolation)
└── agents.py                ⚠️ CoordinatorAgent (needs orchestrator upgrade)

tests/
├── test_orchestrator_protocol.py    ✅ 18/20 tests passing
├── test_failure_modes.py            ✅ 60+ tests
├── test_routing_authority.py        ✅ 50+ tests
└── scenario/test_agent_composition.py ✅ 13 E2E tests
```

### Critical Gaps ⚠️

**1. CoordinatorAgent is Not a Full Orchestrator**
```python
# Current (Simplified Dispatcher)
class CoordinatorAgent:
    def dispatch(self, goal: str) -> AgentResult:
        plan = self.planner.plan(goal)              # Direct call
        worker = self._select_worker()              # Hardcoded round-robin
        result = worker.execute(plan.steps)         # No retry logic
        return result                                # No partial results

# Target (Full Orchestrator)
class CoordinatorAgent(OrchestratorProtocol):
    async def orchestrate(self, goal: str, context: ExecutionContext):
        yield {"stage": LifecycleStage.INITIALIZE, ...}
        
        # Delegate to PlanningAuthority
        plan = await self.planning_authority.create_plan(goal, context)
        yield {"stage": LifecycleStage.PLAN, ...}
        
        # Delegate to RoutingAuthority
        decision = self.routing_authority.route(task, context, workers)
        self.audit_trail.record(decision)           # Record to audit
        yield {"stage": LifecycleStage.ROUTE, ...}
        
        # Execute with RetryPolicy
        try:
            result = await self.retry_policy.execute(
                lambda: worker.execute(step, context),
                failure_mode_handler=self._classify_error
            )
            yield {"stage": LifecycleStage.EXECUTE, ...}
        except Exception as e:
            partial = self._preserve_partial_results(completed_steps)
            raise OrchestrationError(stage=EXECUTE, partial_result=partial)
        
        yield {"stage": LifecycleStage.COMPLETE, ...}
```

**2. Authorities Defined but Not Used**
- RoutingAuthority exists (`src/cuga/orchestrator/routing.py`) but CoordinatorAgent uses hardcoded round-robin
- PlanningAuthority exists (`src/cuga/orchestrator/planning.py`) but CoordinatorAgent calls `planner.plan()` directly
- AuditTrail defined but no persistent storage backend implemented
- RetryPolicy defined but no integration in WorkerAgent.execute()

**3. Missing Human-in-the-Loop (HITL)**
- No ApprovalPolicy interface
- No approval gates before sensitive operations
- No approval request/response flow
- No timeout handling for approval waits

**4. No Partial Result Preservation**
- Failures lose all intermediate results
- No continuation from partial state
- No `partial_success` flag in AgentResponse

---

## Implementation Roadmap

### Phase 1: Core Orchestrator Hardening (Week 1)

#### Task 1: Migrate CoordinatorAgent to OrchestratorProtocol ⭐ CRITICAL
**Priority**: P0 (Blocking)  
**Estimated Time**: 2-3 hours  
**Dependencies**: None

**Changes**:
```python
# File: src/cuga/modular/agents.py

@dataclass
class CoordinatorAgent(OrchestratorProtocol):
    """
    Production orchestrator implementing canonical OrchestratorProtocol.
    
    Responsibilities:
    - Lifecycle management (Initialize → Plan → Route → Execute → Complete)
    - Authority delegation (routing, planning, audit)
    - Failure handling with retry/recovery
    - Trace propagation and observability
    """
    
    planner: PlannerAgent
    workers: List[WorkerAgent]
    memory: VectorMemory
    routing_authority: RoutingAuthority
    planning_authority: PlanningAuthority
    audit_trail: AuditTrail
    retry_policy: RetryPolicy = field(default_factory=ExponentialBackoffPolicy)
    
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Full orchestration with lifecycle stage emissions."""
        # Emit INITIALIZE
        yield {"stage": LifecycleStage.INITIALIZE, "data": {}, "context": context}
        
        # Emit PLAN (delegate to PlanningAuthority)
        plan = await self.planning_authority.create_plan(goal, context)
        self.audit_trail.record_plan(plan, context)
        yield {"stage": LifecycleStage.PLAN, "data": {"plan": plan}, "context": context}
        
        # Execute steps with routing + retry
        for step in plan.steps:
            # Emit ROUTE (delegate to RoutingAuthority)
            decision = self.routing_authority.route_to_agent(step, context, self.workers)
            self.audit_trail.record_decision(decision, context)
            yield {"stage": LifecycleStage.ROUTE, "data": {"decision": decision}, "context": context}
            
            # Emit EXECUTE (with retry policy)
            try:
                result = await self.retry_policy.execute(
                    lambda: self._execute_step(step, decision.target, context),
                    context=context,
                )
                yield {"stage": LifecycleStage.EXECUTE, "data": {"result": result}, "context": context}
            except Exception as e:
                await self._handle_execution_error(e, error_strategy, context)
        
        # Emit COMPLETE
        yield {"stage": LifecycleStage.COMPLETE, "data": {}, "context": context}
    
    def make_routing_decision(
        self, task: str, context: ExecutionContext, available_agents: List[str]
    ) -> RoutingDecision:
        """Delegate routing decision to authority."""
        return self.routing_authority.route_to_agent(task, context, available_agents)
    
    async def handle_error(
        self, error: OrchestrationError, strategy: ErrorPropagation
    ) -> Optional[Dict[str, Any]]:
        """Handle orchestration errors per strategy."""
        failure_mode = self._classify_error(error)
        
        if strategy == ErrorPropagation.FAIL_FAST:
            raise error
        elif strategy == ErrorPropagation.RETRY:
            if failure_mode.retryable:
                return await self.retry_policy.retry(error.operation, context)
            raise error
        elif strategy == ErrorPropagation.CONTINUE:
            self._preserve_partial_results(error.context)
            return {"stage": LifecycleStage.FAILED, "error": str(error), "partial": True}
        
        raise error
```

**Tests**:
```python
# File: tests/test_coordinator_orchestrator.py

class TestCoordinatorOrchestrator:
    """Test CoordinatorAgent as full OrchestratorProtocol implementation."""
    
    @pytest.mark.asyncio
    async def test_implements_orchestrator_protocol(self):
        """CoordinatorAgent implements OrchestratorProtocol."""
        assert isinstance(coordinator, OrchestratorProtocol)
    
    @pytest.mark.asyncio
    async def test_lifecycle_stages_emitted_in_order(self):
        """All lifecycle stages emitted in correct order."""
        stages = []
        async for event in coordinator.orchestrate(goal, context):
            stages.append(event["stage"])
        
        assert stages[0] == LifecycleStage.INITIALIZE
        assert stages[1] == LifecycleStage.PLAN
        assert LifecycleStage.ROUTE in stages
        assert LifecycleStage.EXECUTE in stages
        assert stages[-1] == LifecycleStage.COMPLETE
    
    @pytest.mark.asyncio
    async def test_delegates_to_routing_authority(self):
        """Routing decisions delegated to RoutingAuthority."""
        decision = coordinator.make_routing_decision(task, context, workers)
        assert decision.reasoning is not None
        assert decision.alternatives is not None
    
    @pytest.mark.asyncio
    async def test_delegates_to_planning_authority(self):
        """Planning delegated to PlanningAuthority."""
        # Verify planner.plan() NOT called directly
        # Verify planning_authority.create_plan() called
        ...
```

**Acceptance Criteria**:
- [ ] CoordinatorAgent implements OrchestratorProtocol
- [ ] All lifecycle stages emitted in correct order
- [ ] Routing decisions delegated to RoutingAuthority
- [ ] Planning decisions delegated to PlanningAuthority
- [ ] Tests pass: 10+ tests for lifecycle compliance

---

#### Task 2: Integrate RoutingAuthority ⭐ HIGH
**Priority**: P0 (Blocking)  
**Estimated Time**: 1-2 hours  
**Dependencies**: Task 1

**Changes**:
```python
# File: src/cuga/modular/agents.py

@dataclass
class CoordinatorAgent(OrchestratorProtocol):
    # Add routing_authority field
    routing_authority: RoutingAuthority = field(
        default_factory=lambda: PolicyBasedRoutingAuthority(
            policy=RoundRobinPolicy()  # Default, can be swapped
        )
    )
    
    def _select_worker(self) -> WorkerAgent:
        """DEPRECATED: Use routing_authority instead."""
        warnings.warn(
            "Direct worker selection deprecated. Use routing_authority.route_to_agent().",
            DeprecationWarning
        )
        # Fallback to round-robin for backward compatibility
        with self._lock:
            worker = self.workers[self._next_worker_idx % len(self.workers)]
            self._next_worker_idx += 1
            return worker
```

**Factory Function**:
```python
# File: src/cuga/modular/agents.py

def create_coordinator(
    planner: PlannerAgent,
    workers: List[WorkerAgent],
    memory: VectorMemory,
    *,
    routing_policy: str = "round_robin",  # "round_robin" | "capability" | "load_balanced"
    planning_mode: str = "default",        # "default" | "budget_aware" | "memory_augmented"
    audit_backend: str = "json",           # "json" | "sqlite" | "none"
) -> CoordinatorAgent:
    """
    Factory function for creating production CoordinatorAgent.
    
    Args:
        routing_policy: Routing strategy (round_robin, capability, load_balanced)
        planning_mode: Planning strategy (default, budget_aware, memory_augmented)
        audit_backend: Audit trail storage backend
        
    Returns:
        Fully configured CoordinatorAgent
        
    Example:
        >>> coordinator = create_coordinator(
        ...     planner=planner,
        ...     workers=[worker1, worker2],
        ...     memory=memory,
        ...     routing_policy="capability",
        ...     audit_backend="sqlite"
        ... )
    """
    # Create routing authority
    if routing_policy == "round_robin":
        policy = RoundRobinPolicy()
    elif routing_policy == "capability":
        policy = CapabilityBasedPolicy()
    elif routing_policy == "load_balanced":
        policy = LoadBalancedPolicy()
    else:
        raise ValueError(f"Unknown routing policy: {routing_policy}")
    
    routing_authority = PolicyBasedRoutingAuthority(policy=policy)
    
    # Create planning authority
    planning_authority = PlanningAuthority(planner=planner, memory=memory)
    
    # Create audit trail
    if audit_backend == "json":
        audit_trail = JSONAuditTrail(path="./audit_logs")
    elif audit_backend == "sqlite":
        audit_trail = SQLiteAuditTrail(db_path="./audit.db")
    else:
        audit_trail = NoOpAuditTrail()
    
    return CoordinatorAgent(
        planner=planner,
        workers=workers,
        memory=memory,
        routing_authority=routing_authority,
        planning_authority=planning_authority,
        audit_trail=audit_trail,
    )
```

**Tests**:
```python
# File: tests/test_coordinator_routing.py

class TestCoordinatorRouting:
    def test_pluggable_routing_policy(self):
        """Routing policy can be swapped at runtime."""
        coordinator = create_coordinator(
            planner, workers, memory,
            routing_policy="capability"
        )
        assert isinstance(coordinator.routing_authority.policy, CapabilityBasedPolicy)
    
    def test_routing_decisions_recorded_to_audit(self):
        """All routing decisions persisted to audit trail."""
        coordinator.make_routing_decision(task, context, workers)
        
        decisions = coordinator.audit_trail.get_decisions(trace_id=context.trace_id)
        assert len(decisions) > 0
        assert decisions[0].reasoning is not None
```

**Acceptance Criteria**:
- [ ] RoutingAuthority integrated into CoordinatorAgent
- [ ] Pluggable routing policies (round_robin, capability, load_balanced)
- [ ] Routing decisions recorded to AuditTrail
- [ ] Factory function with routing_policy parameter
- [ ] Tests pass: 5+ routing integration tests

---

#### Task 3: Integrate PlanningAuthority ⭐ HIGH
**Priority**: P0 (Blocking)  
**Estimated Time**: 1-2 hours  
**Dependencies**: Task 1

**Changes**:
```python
# File: src/cuga/modular/agents.py

@dataclass
class CoordinatorAgent(OrchestratorProtocol):
    planning_authority: PlanningAuthority = field(default=None)
    
    def __post_init__(self):
        if self.planning_authority is None:
            self.planning_authority = PlanningAuthority(
                planner=self.planner,
                memory=self.memory
            )
    
    async def orchestrate(self, goal: str, context: ExecutionContext):
        # ...
        
        # Use PlanningAuthority instead of direct planner.plan()
        plan = await self.planning_authority.create_plan(
            goal=goal,
            context=context,
            budget=ToolBudget(ceiling=100, policy="warn"),
        )
        
        # Record plan to audit trail
        self.audit_trail.record_plan(plan, context)
        
        # ...
```

**Acceptance Criteria**:
- [ ] PlanningAuthority integrated into CoordinatorAgent
- [ ] ToolBudget tracking per plan
- [ ] Plan state machine (Created → Routed → Executing → Completed)
- [ ] Planning decisions recorded to AuditTrail
- [ ] Tests pass: 5+ planning integration tests

---

#### Task 4: Add RetryPolicy Integration ⭐ HIGH
**Priority**: P1 (Important)  
**Estimated Time**: 2 hours  
**Dependencies**: None (can be done in parallel)

**Changes**:
```python
# File: src/cuga/modular/agents.py

@dataclass
class WorkerAgent:
    retry_policy: Optional[RetryPolicy] = None
    
    def __post_init__(self):
        if self.retry_policy is None:
            self.retry_policy = ExponentialBackoffPolicy(
                base_delay=1.0,
                max_attempts=3,
                max_delay=30.0,
            )
    
    async def execute_with_retry(
        self,
        steps: Iterable[dict],
        metadata: Optional[dict] = None
    ) -> AgentResult:
        """Execute steps with automatic retry on transient failures."""
        completed_steps = []
        trace = []
        
        for idx, step in enumerate(steps):
            try:
                # Wrap execution in retry policy
                result = await self.retry_policy.execute(
                    operation=lambda: self._execute_single_step(step, metadata),
                    failure_classifier=self._classify_failure,
                    context={"step_index": idx, "trace_id": metadata.get("trace_id")},
                )
                completed_steps.append(result)
                
            except Exception as e:
                # Classify error
                failure_mode = self._classify_failure(e)
                
                # Preserve partial results
                partial = PartialResult(
                    completed_steps=completed_steps,
                    failed_step=step,
                    error=str(e),
                    failure_mode=failure_mode,
                )
                
                # Emit partial result event
                emit_event(PartialResultEvent.create(
                    trace_id=metadata.get("trace_id"),
                    partial_result=partial,
                ))
                
                # Re-raise with partial results attached
                raise ToolExecutionError(
                    f"Step {idx} failed: {e}",
                    partial_result=partial,
                ) from e
        
        return AgentResult(output=completed_steps[-1], trace=trace)
    
    def _classify_failure(self, error: Exception) -> FailureMode:
        """Classify error into FailureMode for retry decisions."""
        if isinstance(error, TimeoutError):
            return FailureMode.RESOURCE  # Retryable
        elif isinstance(error, ConnectionError):
            return FailureMode.SYSTEM  # Retryable
        elif isinstance(error, ValueError):
            return FailureMode.USER  # Not retryable
        elif isinstance(error, PermissionError):
            return FailureMode.POLICY  # Not retryable
        else:
            return FailureMode.AGENT  # Retryable
```

**Tests**:
```python
# File: tests/test_worker_retry.py

class TestWorkerRetry:
    @pytest.mark.asyncio
    async def test_retries_transient_failures(self):
        """Worker retries transient failures automatically."""
        # Tool that fails twice, then succeeds
        call_count = 0
        def flaky_tool(inputs, ctx):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Transient failure")
            return "success"
        
        worker.registry.register(ToolSpec(name="flaky", handler=flaky_tool))
        result = await worker.execute_with_retry([{"tool": "flaky"}])
        
        assert call_count == 3
        assert result.output == "success"
    
    @pytest.mark.asyncio
    async def test_preserves_partial_results_on_failure(self):
        """Partial results preserved when step fails."""
        steps = [
            {"tool": "step1"},  # Succeeds
            {"tool": "step2"},  # Succeeds
            {"tool": "step3"},  # Fails permanently
        ]
        
        try:
            await worker.execute_with_retry(steps)
        except ToolExecutionError as e:
            partial = e.partial_result
            assert len(partial.completed_steps) == 2
            assert partial.failed_step["tool"] == "step3"
```

**Acceptance Criteria**:
- [ ] RetryPolicy integrated into WorkerAgent
- [ ] FailureMode classification (agent/system/resource/policy/user)
- [ ] Automatic retry with exponential backoff
- [ ] Partial result preservation on failure
- [ ] Tests pass: 8+ retry scenarios

---

### Phase 2: Advanced Features (Week 2)

#### Task 5: Implement AuditTrail Integration ⭐ MEDIUM
**Priority**: P1 (Important)  
**Estimated Time**: 2-3 hours  
**Dependencies**: Task 2, Task 3

**Implementation**:
```python
# File: src/cuga/orchestrator/audit.py

@dataclass
class AuditTrail(ABC):
    """Persistent audit trail for orchestration decisions."""
    
    @abstractmethod
    def record_plan(self, plan: Plan, context: ExecutionContext) -> None:
        """Record planning decision."""
        ...
    
    @abstractmethod
    def record_decision(self, decision: RoutingDecision, context: ExecutionContext) -> None:
        """Record routing decision."""
        ...
    
    @abstractmethod
    def get_decisions(self, trace_id: str) -> List[RoutingDecision]:
        """Retrieve all decisions for trace_id."""
        ...

class JSONAuditTrail(AuditTrail):
    """JSON file-based audit trail."""
    
    def __init__(self, path: str = "./audit_logs"):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
    
    def record_decision(self, decision: RoutingDecision, context: ExecutionContext):
        """Append decision to JSON file."""
        filepath = self.path / f"{context.trace_id}.jsonl"
        with open(filepath, "a") as f:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "trace_id": context.trace_id,
                "decision": dataclasses.asdict(decision),
                "context": dataclasses.asdict(context),
            }
            f.write(json.dumps(entry) + "\n")

class SQLiteAuditTrail(AuditTrail):
    """SQLite-based audit trail for production use."""
    
    def __init__(self, db_path: str = "./audit.db"):
        self.db = sqlite3.connect(db_path)
        self._create_tables()
    
    def _create_tables(self):
        self.db.execute("""
            CREATE TABLE IF NOT EXISTS decisions (
                id INTEGER PRIMARY KEY,
                timestamp TEXT NOT NULL,
                trace_id TEXT NOT NULL,
                decision_type TEXT NOT NULL,
                target TEXT NOT NULL,
                reasoning TEXT,
                alternatives TEXT,
                context TEXT
            )
        """)
```

**Acceptance Criteria**:
- [ ] AuditTrail interface with record/query methods
- [ ] JSONAuditTrail implementation (file-based)
- [ ] SQLiteAuditTrail implementation (database)
- [ ] Integrated into CoordinatorAgent
- [ ] Tests pass: 10+ audit trail tests

---

#### Task 6: Implement Approval Gates (HITL) ⭐ MEDIUM
**Priority**: P2 (Nice to have)  
**Estimated Time**: 3-4 hours  
**Dependencies**: Task 1

**Implementation**:
```python
# File: src/cuga/orchestrator/approval.py

@dataclass
class ApprovalPolicy:
    """Policy for human-in-the-loop approval gates."""
    
    approval_required: Callable[[str, Dict], bool]  # (tool_name, inputs) -> bool
    timeout_seconds: float = 300.0  # 5 minutes
    
    def requires_approval(self, tool_name: str, inputs: Dict) -> bool:
        """Check if tool execution requires approval."""
        return self.approval_required(tool_name, inputs)

@dataclass
class ApprovalRequest:
    """Approval request for human review."""
    
    request_id: str
    tool_name: str
    inputs: Dict[str, Any]
    context: ExecutionContext
    reasoning: str
    requested_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

@dataclass
class ApprovalResponse:
    """Human approval decision."""
    
    request_id: str
    approved: bool
    reviewer: str
    reasoning: Optional[str] = None
    responded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

class ApprovalManager:
    """Manages approval request/response flow."""
    
    def __init__(self, policy: ApprovalPolicy):
        self.policy = policy
        self._pending: Dict[str, ApprovalRequest] = {}
        self._responses: Dict[str, ApprovalResponse] = {}
    
    async def request_approval(
        self,
        tool_name: str,
        inputs: Dict,
        context: ExecutionContext,
    ) -> ApprovalResponse:
        """Request human approval and wait for response."""
        request = ApprovalRequest(
            request_id=str(uuid.uuid4()),
            tool_name=tool_name,
            inputs=inputs,
            context=context,
            reasoning=f"Tool '{tool_name}' requires approval per policy",
        )
        
        self._pending[request.request_id] = request
        
        # Emit approval_requested event
        emit_event(ApprovalEvent.create_requested(
            trace_id=context.trace_id,
            request_id=request.request_id,
            tool_name=tool_name,
        ))
        
        # Wait for response with timeout
        try:
            response = await asyncio.wait_for(
                self._wait_for_response(request.request_id),
                timeout=self.policy.timeout_seconds,
            )
            
            # Emit approval_received event
            emit_event(ApprovalEvent.create_received(
                trace_id=context.trace_id,
                request_id=request.request_id,
                approved=response.approved,
            ))
            
            return response
            
        except asyncio.TimeoutError:
            # Emit approval_timeout event
            emit_event(ApprovalEvent.create_timeout(
                trace_id=context.trace_id,
                request_id=request.request_id,
            ))
            raise ApprovalTimeoutError(
                f"Approval request {request.request_id} timed out after {self.policy.timeout_seconds}s"
            )
    
    def submit_response(self, response: ApprovalResponse) -> None:
        """Submit human approval response."""
        self._responses[response.request_id] = response
        del self._pending[response.request_id]
```

**Integration with WorkerAgent**:
```python
# File: src/cuga/modular/agents.py

@dataclass
class WorkerAgent:
    approval_manager: Optional[ApprovalManager] = None
    
    async def execute(self, steps, metadata):
        for step in steps:
            tool_name = step["tool"]
            inputs = step.get("input", {})
            
            # Check if approval required
            if self.approval_manager and self.approval_manager.policy.requires_approval(tool_name, inputs):
                response = await self.approval_manager.request_approval(
                    tool_name=tool_name,
                    inputs=inputs,
                    context=context,
                )
                
                if not response.approved:
                    raise ApprovalDeniedError(
                        f"Tool '{tool_name}' execution denied by {response.reviewer}: {response.reasoning}"
                    )
            
            # Execute tool
            result = self._execute_tool(tool_name, inputs, context)
```

**Acceptance Criteria**:
- [ ] ApprovalPolicy interface with requires_approval()
- [ ] ApprovalManager with request/response flow
- [ ] Timeout handling for approval waits
- [ ] Integrated into WorkerAgent
- [ ] Approval events emitted (requested/received/timeout)
- [ ] Tests pass: 8+ approval gate tests

---

#### Task 7: Implement Partial Result Preservation ⭐ MEDIUM
**Priority**: P1 (Important)  
**Estimated Time**: 2 hours  
**Dependencies**: Task 4

**Implementation**: Already started in Task 4, enhance with:
- Resume from partial state
- Serialize/deserialize partial results
- Recovery workflow

**Acceptance Criteria**:
- [ ] PartialResult with completed_steps, failed_step, recovery_plan
- [ ] Serialization/deserialization support
- [ ] Resume execution from partial state
- [ ] Tests pass: 5+ partial result tests

---

### Phase 3: Documentation & Testing (Ongoing)

#### Task 8: Create Modular Tool Integration Guide ⭐ CRITICAL
**Priority**: P0 (Blocking for tool integration)  
**Estimated Time**: 2-3 hours  
**Dependencies**: Task 1-7 (document after implementation)

**Deliverables**:
1. `docs/tools/MODULAR_TOOL_INTEGRATION.md` (architecture guide)
2. `docs/tools/TOOL_CREATION_GUIDE.md` (step-by-step tutorial)
3. `docs/tools/examples/` (example tools with full lifecycle)

**Content Outline**:
```markdown
# Modular Tool Integration Guide

## Overview
The orchestrator provides a plugin-style architecture for adding tools without modifying core code.

## Tool Handler Contract
Every tool must implement:
- Signature: `(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any`
- Located in: `src/cuga/modular/tools/<category>/<tool_name>.py`
- Allowlist: Must be in `cuga.modular.tools.*` namespace

## Registration Process
1. Create tool handler function
2. Define ToolSpec with parameters
3. Register in ToolRegistry
4. Add tests
5. (Optional) Configure approval policy
6. (Optional) Set budget limits

## Example: Adding a Web Search Tool
[Complete step-by-step example]

## Testing Requirements
- Unit tests for handler logic
- Integration tests with WorkerAgent
- Scenario tests for E2E workflows

## Security Checklist
- [ ] Handler in allowlisted namespace
- [ ] Parameter validation with schemas
- [ ] No eval/exec usage
- [ ] SafeClient for network I/O
- [ ] Secrets via environment only
- [ ] Budget limits configured
- [ ] Approval policy for sensitive ops
```

**Acceptance Criteria**:
- [ ] Complete tool integration architecture documented
- [ ] Step-by-step tutorial with examples
- [ ] 3+ example tools with full lifecycle
- [ ] Security checklist included
- [ ] Testing requirements documented

---

#### Task 9: Add Integration Tests for Full Orchestration ⭐ HIGH
**Priority**: P0 (Blocking)  
**Estimated Time**: 3-4 hours  
**Dependencies**: Task 1-7

**Test Coverage**:
```python
# File: tests/integration/test_full_orchestration.py

class TestFullOrchestration:
    """Integration tests for complete orchestration flow."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_with_all_authorities(self):
        """Full orchestration with routing/planning/audit authorities."""
        coordinator = create_coordinator(
            planner=planner,
            workers=[worker1, worker2],
            memory=memory,
            routing_policy="capability",
            audit_backend="json",
        )
        
        context = ExecutionContext(trace_id="test-e2e", profile="demo")
        
        stages = []
        async for event in coordinator.orchestrate("complex goal", context):
            stages.append(event["stage"])
        
        # Verify lifecycle stages
        assert stages == [INITIALIZE, PLAN, ROUTE, EXECUTE, AGGREGATE, COMPLETE]
        
        # Verify audit trail populated
        decisions = coordinator.audit_trail.get_decisions("test-e2e")
        assert len(decisions) > 0
    
    @pytest.mark.asyncio
    async def test_retry_recovery_from_transient_failure(self):
        """Orchestrator recovers from transient failures with retry."""
        ...
    
    @pytest.mark.asyncio
    async def test_approval_gate_blocks_sensitive_operation(self):
        """Approval gate blocks tool execution until approved."""
        ...
    
    @pytest.mark.asyncio
    async def test_partial_result_preservation_on_failure(self):
        """Partial results preserved and recoverable on failure."""
        ...
```

**Target Coverage**: 15+ integration tests covering all orchestration paths

**Acceptance Criteria**:
- [ ] 15+ integration tests covering all authorities
- [ ] Test retry logic with failure modes
- [ ] Test approval gates with HITL simulation
- [ ] Test partial result preservation
- [ ] All tests passing
- [ ] Coverage >95% for orchestration paths

---

#### Task 10: Update Architecture Documentation ⭐ MEDIUM
**Priority**: P1 (Important)  
**Estimated Time**: 1-2 hours  
**Dependencies**: Task 1-9

**Files to Update**:
- `ARCHITECTURE.md` (orchestrator section)
- `AGENTS.md` (coordinator → orchestrator migration)
- `docs/orchestrator/README.md` (usage examples)
- `docs/testing/COVERAGE_MATRIX.md` (orchestrator to 100%)
- `README.md` (quick start examples)

**Acceptance Criteria**:
- [ ] All architecture docs reflect new orchestration
- [ ] Usage examples with all authorities
- [ ] Migration guide from simple coordinator
- [ ] Coverage matrix shows 100% orchestrator coverage
- [ ] README quick start updated

---

## Success Criteria

### Definition of Done

**Orchestrator is 100% production-ready when:**

1. ✅ **Core Implementation**
   - [ ] CoordinatorAgent implements OrchestratorProtocol
   - [ ] All lifecycle stages emitted (Initialize → Complete)
   - [ ] All authorities integrated (routing, planning, audit)
   - [ ] Retry logic with failure mode classification
   - [ ] Approval gates for HITL
   - [ ] Partial result preservation

2. ✅ **Test Coverage**
   - [ ] >95% code coverage for orchestration paths
   - [ ] 15+ integration tests for full orchestration
   - [ ] 50+ unit tests for individual components
   - [ ] All scenario tests passing (13 existing + new)

3. ✅ **Documentation**
   - [ ] Tool integration guide complete
   - [ ] Architecture docs updated
   - [ ] Usage examples with all features
   - [ ] API reference complete

4. ✅ **Verification**
   - [ ] All tests passing (unit + integration + scenario)
   - [ ] No TODO/FIXME in production code
   - [ ] Code review by 2+ team members
   - [ ] Security audit passed

### Metrics

**Before Hardening**:
- OrchestratorProtocol: Defined but CoordinatorAgent doesn't implement it
- Routing: Hardcoded round-robin (30% complete)
- Planning: Direct planner.plan() calls (30% complete)
- Audit: Defined but no backends (30% complete)
- Retry: Defined but not integrated (0% complete)
- Approval: Not implemented (0% complete)
- Partial Results: Not preserved (0% complete)
- Test Coverage: 88% critical paths, gaps in orchestration

**After Hardening**:
- OrchestratorProtocol: ✅ Fully implemented by CoordinatorAgent (100%)
- Routing: ✅ Pluggable policies via RoutingAuthority (100%)
- Planning: ✅ ToolBudget tracking via PlanningAuthority (100%)
- Audit: ✅ JSON + SQLite backends (100%)
- Retry: ✅ Integrated with failure mode classification (100%)
- Approval: ✅ HITL gates with timeout handling (100%)
- Partial Results: ✅ Preserved and recoverable (100%)
- Test Coverage: ✅ >95% orchestration paths (100%)

---

## Timeline

**Total Estimated Time**: 20-25 hours  
**Target Completion**: 2026-01-15 (2 weeks)

### Week 1 (Core Hardening)
- **Day 1-2**: Task 1 (CoordinatorAgent migration) - 2-3 hours
- **Day 2**: Task 2 (RoutingAuthority) - 1-2 hours
- **Day 3**: Task 3 (PlanningAuthority) - 1-2 hours
- **Day 3-4**: Task 4 (RetryPolicy) - 2 hours
- **Day 5**: Task 9 (Start integration tests) - 1-2 hours

### Week 2 (Advanced Features + Documentation)
- **Day 6-7**: Task 5 (AuditTrail) - 2-3 hours
- **Day 7-8**: Task 6 (Approval Gates) - 3-4 hours
- **Day 8**: Task 7 (Partial Results) - 2 hours
- **Day 9-10**: Task 8 (Tool Integration Guide) - 2-3 hours
- **Day 10**: Task 9 (Finish integration tests) - 1-2 hours
- **Day 11**: Task 10 (Documentation) - 1-2 hours
- **Day 12-13**: Code review, testing, polish

---

## Next Steps

1. **Review this roadmap** with team
2. **Prioritize tasks** if timeline needs compression
3. **Assign ownership** for each task
4. **Start with Task 1** (CoordinatorAgent migration)
5. **Run tests continuously** to catch regressions
6. **Update this document** as tasks complete

---

**Last Updated**: 2026-01-02  
**Status**: Active Development  
**Owner**: Core Architecture Team  
**Questions?**: See `docs/orchestrator/README.md` or file an issue
