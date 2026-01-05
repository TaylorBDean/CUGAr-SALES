# Canonical Routing Authority

## Overview

Routing logic in CUGAR agent system was previously **distributed across multiple locations** with no clear decision authority. This document defines the **single source of truth** for "who decides what runs next" through the `RoutingAuthority` interface.

---

## Problem Statement

**Before Routing Authority:**

```
┌─────────────────────────────────────────────────────────────┐
│  DISTRIBUTED ROUTING (Anti-Pattern)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ CoordinatorAgent │    │   Coordinator    │             │
│  │  .dispatch()     │    │   .run()         │             │
│  │  - round-robin   │    │   - round-robin  │  (Duplicate)│
│  └──────────────────┘    └──────────────────┘             │
│                                                             │
│  ┌──────────────────┐    ┌──────────────────┐             │
│  │ PlanController   │    │  Frontend Mode   │             │
│  │  Command(goto=)  │    │  supervisor/     │  (Conflict) │
│  └──────────────────┘    │  single          │             │
│                          └──────────────────┘             │
│                                                             │
│  ┌──────────────────────────────────────────────────┐     │
│  │  routing/guards.yaml (policy routing unused)     │     │
│  └──────────────────────────────────────────────────┘     │
└─────────────────────────────────────────────────────────────┘

Problems:
❌ No single authority - multiple coordinators
❌ LangGraph Command routing bypasses orchestrator
❌ Frontend makes routing decisions backend must honor
❌ Duplicate round-robin logic in two coordinators
❌ No clear contract for routing decisions
```

**After Routing Authority:**

```
┌─────────────────────────────────────────────────────────────┐
│  CENTRALIZED ROUTING (Canonical)                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│           ┌────────────────────────────┐                   │
│           │   RoutingAuthority         │                   │
│           │  (Single Source of Truth)  │                   │
│           └────────────┬───────────────┘                   │
│                        │                                    │
│         ┌──────────────┼──────────────┐                    │
│         ▼              ▼              ▼                    │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐              │
│  │  Agent   │   │  Worker  │   │   Tool   │              │
│  │ Routing  │   │ Routing  │   │ Routing  │              │
│  └──────────┘   └──────────┘   └──────────┘              │
│         │              │              │                    │
│         └──────────────┴──────────────┘                    │
│                        │                                    │
│                        ▼                                    │
│           ┌────────────────────────────┐                   │
│           │  OrchestratorProtocol      │                   │
│           │  .make_routing_decision()  │                   │
│           └────────────────────────────┘                   │
│                                                             │
│  All routing flows through RoutingAuthority ✅             │
└─────────────────────────────────────────────────────────────┘

Benefits:
✅ Single decision authority
✅ Pluggable routing policies
✅ Clean orchestrator contract
✅ Eliminates duplicate logic
✅ Explicit routing decisions with justification
```

---

## Architecture

### Core Components

#### 1. **RoutingAuthority** (Abstract Interface)

The canonical interface all routing implementations MUST implement:

```python
class RoutingAuthority(ABC):
    @abstractmethod
    def route_to_agent(
        self,
        context: RoutingContext,
        agents: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Route request to agent."""
        ...
    
    @abstractmethod
    def route_to_worker(
        self,
        context: RoutingContext,
        workers: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Route task to worker."""
        ...
    
    @abstractmethod
    def route_to_tool(
        self,
        context: RoutingContext,
        tools: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Route action to tool."""
        ...
```

**Design Principles:**
- **Single Responsibility**: Routing decisions only, no execution
- **Immutable Context**: `RoutingContext` is frozen dataclass
- **Explicit Decisions**: All decisions return `RoutingDecision` with justification
- **Pluggable**: Authority delegates to `RoutingPolicy` implementations

#### 2. **RoutingContext** (Immutable)

Routing context passed through all routing operations:

```python
@dataclass(frozen=True)
class RoutingContext:
    trace_id: str
    profile: str
    goal: Optional[str] = None
    task: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    parent_context: Optional[RoutingContext] = None
```

**Immutability Guarantees:**
- `frozen=True` prevents mutation
- Context updates create new instances via `.with_goal()`, `.with_task()`
- Parent context preserved for nested routing decisions
- Trace ID propagates through all routing operations

#### 3. **RoutingDecision** (Explicit Record)

Immutable routing decision with full justification:

```python
@dataclass
class RoutingDecision:
    strategy: RoutingStrategy              # Strategy used
    decision_type: RoutingDecisionType     # Type of decision
    selected: RoutingCandidate             # Selected candidate
    reason: str                            # Justification
    alternatives: List[RoutingCandidate]   # Other options
    fallback: Optional[RoutingCandidate]   # Fallback if selected fails
    confidence: float = 1.0                # Confidence (0.0-1.0)
    metadata: Dict[str, Any] = field(default_factory=dict)
```

**Observability Benefits:**
- Every decision includes human-readable reason
- Alternatives documented for debugging
- Confidence score enables monitoring
- Metadata carries routing-specific context

#### 4. **RoutingPolicy** (Pluggable Strategy)

Protocol for routing strategy implementations:

```python
class RoutingPolicy(Protocol):
    def evaluate(
        self,
        context: RoutingContext,
        candidates: List[RoutingCandidate],
    ) -> RoutingDecision:
        """Evaluate candidates and return routing decision."""
        ...
```

**Built-in Policies:**

**A. `RoundRobinPolicy`** (Thread-Safe)
```python
policy = RoundRobinPolicy()
decision = policy.evaluate(context, [worker1, worker2, worker3])
# Result: worker1 (counter=1)
# Next call: worker2 (counter=2)
# Next call: worker3 (counter=3)
# Next call: worker1 (counter=4) - wraps around
```

**B. `CapabilityBasedPolicy`** (Matching)
```python
policy = CapabilityBasedPolicy()
context = RoutingContext(
    trace_id="abc",
    profile="prod",
    constraints={"required_capabilities": ["research", "web"]},
)
candidates = [
    RoutingCandidate(id="1", capabilities=["research", "web", "api"]),
    RoutingCandidate(id="2", capabilities=["code", "analysis"]),
]
decision = policy.evaluate(context, candidates)
# Result: candidate 1 (2/2 capability match = 100%)
```

---

## Integration with OrchestratorProtocol

`OrchestratorProtocol` delegates routing to `RoutingAuthority`:

```python
class ReferenceOrchestrator(OrchestratorProtocol):
    def __init__(
        self,
        routing_authority: RoutingAuthority,
        agents: List[Any],
        ...
    ):
        self.routing_authority = routing_authority
        self.agents = agents
    
    def make_routing_decision(
        self,
        task: str,
        context: ExecutionContext,
        available_agents: List[str],
    ) -> RoutingDecision:
        """Delegate to routing authority."""
        # Convert ExecutionContext → RoutingContext
        routing_context = RoutingContext(
            trace_id=context.trace_id,
            profile=context.profile,
            task=task,
            metadata=context.metadata,
        )
        
        # Convert agent names → RoutingCandidates
        candidates = [
            RoutingCandidate(
                id=name,
                name=name,
                type="agent",
                capabilities=agent.capabilities,
            )
            for name, agent in self.agents.items()
            if name in available_agents
        ]
        
        # Routing authority makes decision
        return self.routing_authority.route_to_agent(
            routing_context,
            candidates,
        )
```

**Flow:**
1. Orchestrator receives task in `ExecutionContext`
2. Orchestrator converts to `RoutingContext` + `RoutingCandidate` list
3. Orchestrator delegates to `routing_authority.route_to_agent()`
4. `RoutingAuthority` evaluates candidates via `RoutingPolicy`
5. `RoutingDecision` returned with justification
6. Orchestrator uses selected candidate and logs decision

---

## Migration Guide

### Phase 1: Update CoordinatorAgent (Modular)

**Before:**
```python
@dataclass
class CoordinatorAgent:
    planner: PlannerAgent
    workers: List[WorkerAgent]
    _next_worker_idx: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def dispatch(self, goal: str, trace_id: Optional[str] = None) -> AgentResult:
        plan = self.planner.plan(goal, metadata={...})
        worker = self._select_worker()  # Internal routing logic
        result = worker.execute(plan.steps, metadata={...})
        return AgentResult(output=result.output, trace=traces)
    
    def _select_worker(self) -> WorkerAgent:
        with self._lock:
            worker = self.workers[self._next_worker_idx]
            self._next_worker_idx = (self._next_worker_idx + 1) % len(self.workers)
        return worker
```

**After:**
```python
from cuga.orchestrator.routing import (
    RoutingAuthority,
    RoutingCandidate,
    RoutingContext,
    create_routing_authority,
)

@dataclass
class CoordinatorAgent:
    planner: PlannerAgent
    workers: List[WorkerAgent]
    routing_authority: RoutingAuthority = field(
        default_factory=lambda: create_routing_authority(
            worker_strategy=RoutingStrategy.ROUND_ROBIN
        )
    )
    
    def dispatch(self, goal: str, trace_id: Optional[str] = None) -> AgentResult:
        plan = self.planner.plan(goal, metadata={...})
        
        # Create routing context
        context = RoutingContext(
            trace_id=trace_id or "default",
            profile=self.planner.config.profile,
            goal=goal,
        )
        
        # Convert workers to candidates
        candidates = [
            RoutingCandidate(
                id=str(idx),
                name=f"worker-{idx}",
                type="worker",
            )
            for idx, _ in enumerate(self.workers)
        ]
        
        # Routing authority makes decision
        decision = self.routing_authority.route_to_worker(context, candidates)
        
        # Use selected worker
        worker_idx = int(decision.selected.id)
        worker = self.workers[worker_idx]
        result = worker.execute(plan.steps, metadata={...})
        
        # Log routing decision
        traces.append({
            "event": "routing_decision",
            "strategy": decision.strategy.value,
            "selected": decision.selected.name,
            "reason": decision.reason,
            "trace_id": trace_id,
        })
        
        return AgentResult(output=result.output, trace=traces)
```

### Phase 2: Update Coordinator (Legacy)

**Before:**
```python
class Coordinator:
    def __init__(self, workers: Iterable[Any], tracer: InMemoryTracer | None = None) -> None:
        self.workers = list(workers)
        self._lock = threading.Lock()
        self._index = 0
        self.tracer = tracer or InMemoryTracer()
    
    def _next_worker(self) -> Any:
        with self._lock:
            worker = self.workers[self._index % len(self.workers)]
            self._index += 1
            return worker
```

**After:**
```python
from cuga.orchestrator.routing import (
    RoutingAuthority,
    RoutingCandidate,
    RoutingContext,
    create_routing_authority,
)

class Coordinator:
    def __init__(
        self,
        workers: Iterable[Any],
        routing_authority: Optional[RoutingAuthority] = None,
        tracer: InMemoryTracer | None = None,
    ) -> None:
        self.workers = list(workers)
        self.routing_authority = routing_authority or create_routing_authority()
        self.tracer = tracer or InMemoryTracer()
    
    async def run(self, plan: List[Any], trace_id: str) -> AsyncIterator[Dict[str, Any]]:
        propagate_trace(trace_id)
        for step in plan:
            # Create routing context
            context = RoutingContext(
                trace_id=trace_id,
                profile="default",
                task=step.tool,
            )
            
            # Convert workers to candidates
            candidates = [
                RoutingCandidate(
                    id=str(idx),
                    name=worker.name,
                    type="worker",
                )
                for idx, worker in enumerate(self.workers)
            ]
            
            # Routing authority decides
            decision = self.routing_authority.route_to_worker(context, candidates)
            worker_idx = int(decision.selected.id)
            worker = self.workers[worker_idx]
            
            span = self.tracer.start_span("worker.dispatch", trace_id=trace_id, tool=step.tool)
            result = await worker.execute(step, trace_id=trace_id)
            span.end(status="ok")
            yield {
                "worker": worker.name,
                "result": result,
                "routing_decision": decision.reason,
                "trace_id": trace_id,
            }
            await asyncio.sleep(0)
```

### Phase 3: Eliminate LangGraph Command Routing

**Before (Anti-Pattern):**
```python
class PlanControllerNode(BaseNode):
    @staticmethod
    async def node_handler(...) -> Command[Literal[...]]:
        # Node directly decides routing
        if state.sub_task_type == 'web':
            return Command(update=state.model_dump(), goto="BrowserPlannerAgent")
        else:
            return Command(update=state.model_dump(), goto="APIPlannerAgent")
```

**After (Delegated):**
```python
from cuga.orchestrator.routing import (
    RoutingAuthority,
    RoutingCandidate,
    RoutingContext,
)

class PlanControllerNode(BaseNode):
    def __init__(self, routing_authority: RoutingAuthority):
        self.routing_authority = routing_authority
    
    async def node_handler(self, state: AgentState, ...) -> Command[Literal[...]]:
        # Create routing context
        context = RoutingContext(
            trace_id=state.trace_id,
            profile=state.profile,
            task=state.sub_task,
            constraints={"task_type": state.sub_task_type},
        )
        
        # Define available agents
        candidates = [
            RoutingCandidate(
                id="browser",
                name="BrowserPlannerAgent",
                type="agent",
                capabilities=["web"],
            ),
            RoutingCandidate(
                id="api",
                name="APIPlannerAgent",
                type="agent",
                capabilities=["api"],
            ),
        ]
        
        # Routing authority decides
        decision = self.routing_authority.route_to_agent(context, candidates)
        
        # Use decision (LangGraph Command still needed for compatibility)
        return Command(
            update={
                **state.model_dump(),
                "routing_decision": decision.reason,
            },
            goto=decision.selected.name,
        )
```

---

## Routing Strategies

### Supported Strategies

| Strategy | Use Case | Deterministic | State |
|----------|----------|---------------|-------|
| `ROUND_ROBIN` | Load distribution | ✅ Yes | Counter |
| `CAPABILITY` | Skill matching | ✅ Yes | Stateless |
| `LOAD_BALANCED` | Dynamic load | ❌ No | Metrics |
| `PRIORITY` | Rule-based | ✅ Yes | Config |
| `LEARNED` | ML-based | ❌ No | Model |
| `MANUAL` | Explicit | ✅ Yes | Stateless |

### Strategy Selection Guide

**Use `ROUND_ROBIN` when:**
- Even load distribution desired
- All workers have identical capabilities
- Simplicity and predictability preferred
- Example: Homogeneous worker pool

**Use `CAPABILITY` when:**
- Agents have distinct capabilities
- Task requirements vary
- Matching skills to tasks needed
- Example: Specialist agents (web, API, research)

**Use `LOAD_BALANCED` when:**
- Workers have varying capacity
- Real-time load metrics available
- Optimal resource utilization critical
- Example: Elastic worker pool with autoscaling

**Use `PRIORITY` when:**
- Business rules determine routing
- SLA requirements differ by task type
- Explicit precedence rules exist
- Example: Premium vs standard service tiers

---

## Testing

### Routing Compliance Tests

```python
def test_routing_authority_centralizes_decisions():
    """Verify all routing goes through RoutingAuthority."""
    authority = PolicyBasedRoutingAuthority()
    context = RoutingContext(trace_id="test", profile="prod")
    candidates = [
        RoutingCandidate(id="1", name="worker-1", type="worker"),
        RoutingCandidate(id="2", name="worker-2", type="worker"),
    ]
    
    decision = authority.route_to_worker(context, candidates)
    
    assert isinstance(decision, RoutingDecision)
    assert decision.selected in candidates
    assert decision.reason  # Must have justification
    assert 0.0 <= decision.confidence <= 1.0

def test_orchestrator_delegates_routing():
    """Verify orchestrator delegates to RoutingAuthority."""
    authority = create_routing_authority()
    orchestrator = ReferenceOrchestrator(
        routing_authority=authority,
        agents={"agent1": ..., "agent2": ...},
    )
    
    # Orchestrator MUST call routing_authority, not make decision
    with patch.object(authority, 'route_to_agent') as mock_route:
        mock_route.return_value = RoutingDecision(...)
        
        orchestrator.make_routing_decision(
            task="test",
            context=ExecutionContext(...),
            available_agents=["agent1", "agent2"],
        )
        
        mock_route.assert_called_once()

def test_no_agent_routing_bypass():
    """Verify agents cannot bypass routing authority."""
    # Agents MUST NOT have internal routing logic
    # All routing MUST go through RoutingAuthority
    
    coordinator = CoordinatorAgent(
        planner=...,
        workers=[...],
        routing_authority=authority,
    )
    
    # Coordinator MUST NOT have _select_worker() method
    assert not hasattr(coordinator, '_select_worker')
    
    # Coordinator MUST delegate to routing_authority
    result = coordinator.dispatch(goal="test")
    # Verify routing decision logged in traces
    assert any(
        event["event"] == "routing_decision"
        for event in result.trace
    )
```

---

## FAQ

### Q: Does this replace OrchestratorProtocol's make_routing_decision()?

**A:** No - `OrchestratorProtocol.make_routing_decision()` **delegates** to `RoutingAuthority`. The orchestrator's method converts its `ExecutionContext` to `RoutingContext`, then calls `routing_authority.route_to_agent/worker/tool()`. This separates orchestration concerns (lifecycle, coordination) from routing concerns (selection logic).

### Q: Can agents make their own routing decisions?

**A:** No - agents MUST NOT contain routing logic. All routing decisions MUST flow through `RoutingAuthority`. This prevents distributed routing logic and ensures clean separation of concerns.

### Q: How does this work with LangGraph Command routing?

**A:** LangGraph `Command(goto=...)` is still used for graph navigation, but the **decision** of where to go comes from `RoutingAuthority`. The node handler delegates to routing authority, gets a `RoutingDecision`, and uses the selected target in the `Command`.

### Q: What happens to routing/guards.yaml?

**A:** `routing/guards.yaml` becomes **policy configuration** for `RoutingAuthority`. Instead of being unused, it configures routing policies (which agents can handle which tasks, capability requirements, priority rules, etc.).

### Q: How do I add custom routing strategies?

**A:** Implement `RoutingPolicy` protocol:

```python
class MyCustomPolicy:
    def evaluate(
        self,
        context: RoutingContext,
        candidates: List[RoutingCandidate],
    ) -> RoutingDecision:
        # Custom routing logic
        selected = custom_selection_logic(context, candidates)
        return RoutingDecision(
            strategy=RoutingStrategy.MANUAL,
            decision_type=RoutingDecisionType.AGENT_SELECTION,
            selected=selected,
            reason="Custom logic selected based on XYZ",
            confidence=0.8,
        )

authority = PolicyBasedRoutingAuthority(agent_policy=MyCustomPolicy())
```

### Q: How does frontend routing (supervisor/single mode) integrate?

**A:** Frontend configuration becomes **routing policy configuration**. Instead of frontend deciding routing, it configures the `RoutingAuthority` policy:

```python
# Frontend sends mode configuration to backend
POST /api/config/agent-mode
{"mode": "single", "selectedAgent": "research-agent"}

# Backend configures routing authority
if config.mode == "single":
    # Manual routing to selected agent only
    authority = PolicyBasedRoutingAuthority(
        agent_policy=ManualPolicy(fixed_agent=config.selectedAgent)
    )
else:
    # Supervisor mode with capability-based routing
    authority = PolicyBasedRoutingAuthority(
        agent_policy=CapabilityBasedPolicy()
    )
```

---

## Benefits Summary

✅ **Single Source of Truth** - All routing decisions through `RoutingAuthority`  
✅ **Clean Separation** - Orchestration ≠ Routing ≠ Execution  
✅ **Pluggable Strategies** - Swap routing policies without changing orchestrators  
✅ **Explicit Decisions** - Every routing decision documented with justification  
✅ **Testable** - Mock `RoutingAuthority` for deterministic testing  
✅ **Observable** - Routing decisions logged with trace_id propagation  
✅ **Eliminates Duplication** - No more multiple coordinators with duplicate logic  
✅ **Type-Safe** - Protocol-based with full type hints  

---

## Next Steps

1. **Implement in Modular Agents** - Update `CoordinatorAgent` per migration guide
2. **Update Reference Orchestrator** - Show delegation pattern  
3. **Migrate Legacy Coordinator** - Update `src/cuga/coordinator/core.py`
4. **Policy Configuration** - Wire `routing/guards.yaml` to routing policies
5. **Frontend Integration** - Convert mode selection to routing policy configuration
6. **Testing** - Add routing compliance tests to CI
7. **Documentation** - Update architecture docs with routing authority

---

## See Also

- `src/cuga/orchestrator/routing.py` - Routing authority implementation
- `src/cuga/orchestrator/protocol.py` - OrchestratorProtocol integration
- `docs/orchestrator/ORCHESTRATOR_CONTRACT.md` - Orchestration contract
- `docs/agents/AGENT_IO_CONTRACT.md` - Agent I/O contracts
- `AGENTS.md` - Guardrails and policies
