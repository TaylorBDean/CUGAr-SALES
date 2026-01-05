from __future__ import annotations

import threading
import time
import warnings
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from .config import AgentConfig
from .llm.interface import LLM, MockLLM
from .memory import VectorMemory
from .tools import ToolRegistry, ToolSpec

# Observability infrastructure (v1.1.0+)
from cuga.observability import (
    PlanEvent,
    RouteEvent,
    ToolCallEvent,
    BudgetEvent,
    emit_event,
    get_collector,
)

# Agent lifecycle protocol (v1.2.0+)
from cuga.agents.lifecycle import (
    AgentLifecycleProtocol,
    AgentState,
    StateOwnership,
    LifecycleConfig,
    LifecycleMetrics,
)

# Agent I/O contract (v1.2.0+)
from cuga.agents.contracts import (
    AgentProtocol,
    AgentRequest,
    AgentResponse,
    RequestMetadata,
    ResponseStatus,
    ErrorType,
    success_response,
    error_response,
)

# Orchestrator protocol (v1.3.0+)
from cuga.orchestrator.protocol import (
    OrchestratorProtocol,
    ExecutionContext,
    LifecycleStage,
    RoutingDecision as ProtocolRoutingDecision,  # Protocol's simple routing decision
    OrchestrationError,
    ErrorPropagation,
    AgentLifecycle,
    OrchestratorMetrics,
)

# Routing authority (v1.3.0+)
from cuga.orchestrator.routing import (
    RoutingAuthority,
    PolicyBasedRoutingAuthority,
    RoutingPolicy,
    RoundRobinPolicy,
    CapabilityBasedPolicy,
    RoutingContext,
    RoutingCandidate,
    RoutingStrategy,
    RoutingDecision as FullRoutingDecision,  # Full routing decision with candidates
    create_routing_authority,
)

# Planning authority (v1.3.1+)
from cuga.orchestrator.planning import (
    PlanningAuthority,
    ToolRankingPlanner,
    Plan,
    PlanStep,
    PlanningStage,
    ToolBudget,
    BudgetError,
    create_planning_authority,
)

# Failure modes and retry (v1.3.1+)
from cuga.orchestrator.failures import (
    FailureMode,
    FailureContext,
    FailureCategory,
    FailureSeverity,
    PartialResult,
    RetryPolicy,
    ExponentialBackoffPolicy,
    LinearBackoffPolicy,
    NoRetryPolicy,
    RetryExecutor,
    create_retry_policy,
)

# Audit trail (v1.3.2+)
from cuga.orchestrator.audit import (
    AuditTrail,
    DecisionRecord,
    create_audit_trail,
)

# Legacy imports (deprecated in v1.1.0, will be removed in v1.3.0)
try:
    from .observability import BaseEmitter
    _LEGACY_OBSERVABILITY_AVAILABLE = True
except ImportError:
    BaseEmitter = None  # type: ignore
    _LEGACY_OBSERVABILITY_AVAILABLE = False

# Guardrails infrastructure (optional - only use if available)
try:
    from cuga.backend.guardrails.policy import GuardrailPolicy, budget_guard
    GUARDRAILS_AVAILABLE = True
except ImportError:
    GUARDRAILS_AVAILABLE = False
    GuardrailPolicy = None  # type: ignore
    budget_guard = None  # type: ignore


@dataclass
class AgentPlan:
    steps: List[dict]
    trace: List[dict] = field(default_factory=list)


@dataclass
class AgentResult:
    output: Any
    trace: List[dict] = field(default_factory=list)


@dataclass
class PlannerAgent:
    registry: ToolRegistry
    memory: VectorMemory
    config: AgentConfig = field(default_factory=AgentConfig.from_env)
    llm: LLM = field(default_factory=MockLLM)
    
    # Lifecycle state (v1.2.0+)
    _state: AgentState = field(default=AgentState.UNINITIALIZED, init=False)
    _metrics: LifecycleMetrics = field(default_factory=LifecycleMetrics, init=False)
    _state_lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    # Lifecycle Protocol Implementation (v1.2.0+)
    
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """Initialize planner resources (idempotent, timeout-bounded)."""
        with self._state_lock:
            if self._state in (AgentState.READY, AgentState.BUSY):
                # Already initialized - idempotent
                return
            
            start_time = time.perf_counter()
            self._transition_state(AgentState.INITIALIZING)
            
            try:
                # Load memory state if exists
                # (Memory owns persistent state, we just read it)
                # No allocation needed for PlannerAgent - it's stateless
                
                self._transition_state(AgentState.READY)
                
                # Record startup time
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.startup_time_ms = duration_ms
                
            except Exception as e:
                self._transition_state(AgentState.TERMINATED)
                raise RuntimeError(f"PlannerAgent startup failed: {e}") from e
    
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Clean up planner resources (MUST NOT raise exceptions)."""
        start_time = time.perf_counter()
        
        try:
            with self._state_lock:
                if self._state == AgentState.TERMINATED:
                    return  # Already shut down
                
                self._transition_state(AgentState.SHUTTING_DOWN)
                
                # Persist MEMORY state (dirty flush)
                # PlannerAgent has no AGENT state to discard (stateless)
                
                # Record shutdown time
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.shutdown_time_ms = duration_ms
                
                self._transition_state(AgentState.TERMINATED)
                
        except Exception as e:
            # MUST NOT raise - log error internally
            print(f"Warning: PlannerAgent shutdown error: {e}")
            self._state = AgentState.TERMINATED
    
    def get_state(self) -> AgentState:
        """Get current lifecycle state (thread-safe)."""
        return self._state
    
    def get_metrics(self) -> LifecycleMetrics:
        """Get lifecycle metrics."""
        return self._metrics
    
    def owns_state(self, key: str) -> StateOwnership:
        """Determine who owns a specific state key."""
        # AGENT state (ephemeral, request-scoped)
        if key in ("_state", "_metrics", "_state_lock", "llm", "registry"):
            return StateOwnership.AGENT
        
        # MEMORY state (persistent, cross-request)
        if key in ("memory",):
            return StateOwnership.MEMORY
        
        # ORCHESTRATOR state (coordination, trace propagation)
        if key in ("trace_id", "routing_context", "parent_context"):
            return StateOwnership.ORCHESTRATOR
        
        # Config is shared
        if key == "config":
            return StateOwnership.SHARED
        
        # Unknown - log warning
        print(f"Warning: Unknown state key '{key}' - assuming AGENT ownership")
        return StateOwnership.AGENT
    
    def _transition_state(self, new_state: AgentState) -> None:
        """Transition to new state (must hold _state_lock)."""
        old_state = self._state
        self._state = new_state
        self._metrics.record_transition(old_state, new_state)

    def plan(self, goal: str, metadata: Optional[dict] = None) -> AgentPlan:
        """Create execution plan with observability event emission."""
        metadata = metadata or {}
        profile = metadata.get("profile", self.config.profile)
        trace_id = metadata.get("trace_id", f"plan-{id(self)}-{time.time()}")
        
        # Start timing for duration tracking
        start_time = time.perf_counter()
        
        # Backward compatibility: still populate trace list
        trace = [
            {"event": "plan:start", "goal": goal, "profile": profile, "trace_id": trace_id},
        ]
        
        # Rank and select tools
        scored_tools = self._rank_tools(goal)
        selected = scored_tools[: max(1, min(self.config.max_steps, len(scored_tools)))]
        
        # Build steps
        steps: List[dict] = []
        tool_names: List[str] = []
        for idx, (tool, score) in enumerate(selected):
            tool_names.append(tool.name)
            steps.append(
                {
                    "tool": tool.name,
                    "input": {"text": goal},
                    "reason": f"matched with score {score:.2f}",
                    "trace_id": trace_id,
                    "index": idx,
                }
            )
        
        # Calculate duration
        duration_ms = (time.perf_counter() - start_time) * 1000
        
        # Emit plan_created event to new observability system
        try:
            plan_event = PlanEvent.create(
                trace_id=trace_id,
                goal=goal,
                steps_count=len(steps),
                tools_selected=tool_names,
                duration_ms=duration_ms,
                profile=profile,  # Pass as kwarg, not in attributes dict
                max_steps=self.config.max_steps,
            )
            emit_event(plan_event)
        except Exception as e:
            # Don't fail planning if observability fails
            print(f"Warning: Failed to emit plan_created event: {e}")
        
        # Backward compatibility traces
        trace.append({"event": "plan:steps", "count": len(steps), "trace_id": trace_id})
        
        # Store in memory
        self.memory.remember(goal, metadata={"profile": profile, "trace_id": trace_id})
        
        trace.append({"event": "plan:complete", "profile": profile, "trace_id": trace_id})
        return AgentPlan(steps=steps, trace=trace)
    
    # AgentProtocol I/O Contract (v1.2.0+)
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process agent request with standardized I/O contract.
        
        Provides clean routing interface while maintaining backward compatibility
        with existing plan() method.
        
        Args:
            request: Canonical agent request (goal, task, metadata)
            
        Returns:
            Canonical agent response (status, result, trace, metadata)
        """
        # Validate request
        validation_errors = request.validate()
        if validation_errors:
            return error_response(
                error_type=ErrorType.VALIDATION,
                message=f"Request validation failed: {', '.join(validation_errors)}",
                details={"validation_errors": validation_errors},
                recoverable=False,
                trace=[{"event": "validation_failed", "errors": validation_errors}],
                metadata={"trace_id": request.metadata.trace_id},
            )
        
        start_time = time.perf_counter()
        
        try:
            # Convert AgentRequest to plan() call
            metadata_dict = {
                "profile": request.metadata.profile,
                "trace_id": request.metadata.trace_id,
                "priority": request.metadata.priority,
                **(request.context or {}),
                **(request.inputs or {}),
            }
            
            # Call existing plan() method
            plan_result = self.plan(goal=request.goal, metadata=metadata_dict)
            
            # Convert AgentPlan to AgentResponse
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return success_response(
                result={
                    "steps": plan_result.steps,
                    "steps_count": len(plan_result.steps),
                    "tools_selected": [step["tool"] for step in plan_result.steps],
                },
                trace=plan_result.trace,
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                    "profile": request.metadata.profile,
                    "agent_type": "planner",
                },
            )
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return error_response(
                error_type=ErrorType.EXECUTION,
                message=f"Planning failed: {str(e)}",
                details={"exception": str(e), "exception_type": type(e).__name__},
                recoverable=True,
                trace=[{"event": "plan_error", "error": str(e)}],
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                },
            )

    def _rank_tools(self, goal: str) -> List[tuple[Any, float]]:
        import re

        terms = set(re.split(r"\W+", goal.lower()))
        ranked: List[tuple[Any, float]] = []
        
        # Handle both list-based (tools.py) and dict-based (tools/__init__.py) registries
        tools_iter = self.registry.tools if isinstance(self.registry.tools, list) else self.registry.tools.values()
        
        for tool in tools_iter:
            # Handle both ToolSpec objects and simple tool objects
            tool_name = getattr(tool, 'name', 'unknown')
            tool_desc = getattr(tool, 'description', '')
            corpus_text = f"{tool_name} {tool_desc}".lower()
            corpus = set(re.split(r"\W+", corpus_text))
            overlap = len(terms.intersection(corpus))
            score = overlap / max(len(terms), 1)
            if score > 0:
                ranked.append((tool, score))
        ranked.sort(key=lambda item: item[1], reverse=True)
        return ranked


@dataclass
class WorkerAgent:
    registry: ToolRegistry
    memory: VectorMemory
    observability: Optional[Any] = None  # Legacy BaseEmitter (deprecated in v1.1.0, removed in v1.3.0)
    guardrail_policy: Optional[Any] = None  # GuardrailPolicy if guardrails enabled
    
    # Retry policy (v1.3.1+) - pluggable retry strategies
    retry_policy: Optional[RetryPolicy] = None
    
    # Lifecycle state fields (AgentLifecycleProtocol)
    _state: AgentState = field(default=AgentState.UNINITIALIZED, init=False)
    _metrics: LifecycleMetrics = field(default_factory=LifecycleMetrics, init=False)
    _state_lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self):
        """Initialize defaults and emit deprecation warnings."""
        # Emit deprecation warning if legacy observability is used
        if self.observability is not None:
            warnings.warn(
                "WorkerAgent.observability (BaseEmitter) is deprecated as of v1.1.0 and will be "
                "removed in v1.3.0. All events are now automatically emitted via "
                "cuga.observability.emit_event(). Remove the 'observability' parameter.",
                DeprecationWarning,
                stacklevel=2
            )
        
        # Initialize default retry policy if not provided
        if self.retry_policy is None:
            # Default: Exponential backoff with 3 attempts, starting at 1s
            self.retry_policy = create_retry_policy(
                strategy="exponential",
                max_attempts=3,
                base_delay=1.0,
                max_delay=30.0,
                multiplier=2.0,
                jitter=0.1,
            )
    
    def _detect_failure_mode(self, exc: Exception) -> FailureMode:
        """
        Detect failure mode from exception type and message.
        
        Args:
            exc: Exception to classify
            
        Returns:
            FailureMode classification
        """
        exc_type = type(exc).__name__
        exc_msg = str(exc).lower()
        
        # Check for specific exception types first
        if isinstance(exc, TimeoutError):
            return FailureMode.SYSTEM_TIMEOUT
        elif isinstance(exc, PermissionError):
            return FailureMode.USER_PERMISSION
        elif isinstance(exc, KeyError) and ("not found" in exc_msg or "not registered" in exc_msg):
            return FailureMode.RESOURCE_TOOL_UNAVAILABLE
        
        # Check message patterns
        if "timeout" in exc_type.lower() or "timeout" in exc_msg:
            return FailureMode.SYSTEM_TIMEOUT
        elif "budget" in exc_msg or "quota" in exc_msg:
            return FailureMode.POLICY_BUDGET
        elif "permission" in exc_msg or "unauthorized" in exc_msg or "access denied" in exc_msg:
            return FailureMode.USER_PERMISSION
        elif "validation" in exc_msg or "invalid" in exc_msg:
            return FailureMode.AGENT_VALIDATION
        elif "network" in exc_msg or "connection" in exc_msg:
            return FailureMode.SYSTEM_NETWORK
        elif "not found" in exc_msg or "unavailable" in exc_msg:
            return FailureMode.RESOURCE_TOOL_UNAVAILABLE
        else:
            # Default to PARTIAL_STEP_FAILURES for mid-execution errors
            # (more recoverable than AGENT_LOGIC)
            return FailureMode.PARTIAL_STEP_FAILURES
    
    def _suggest_recovery(self, failure_mode: FailureMode, completion_ratio: float) -> str:
        """
        Suggest recovery strategy based on failure mode and progress.
        
        Args:
            failure_mode: Failure mode classification
            completion_ratio: Ratio of completed steps (0.0-1.0)
            
        Returns:
            Recovery strategy ("retry_failed", "skip_failed", "manual", "abort", "retry_all")
        """
        # Terminal failures require manual intervention (highest priority)
        if failure_mode.terminal:
            return "manual"
        
        # Non-retryable failures require manual intervention or abort
        if not failure_mode.retryable:
            return "manual"
        
        # High completion ratio - retry only failed steps
        if completion_ratio >= 0.75:
            return "retry_failed"
        
        # Medium completion - retry from checkpoint
        if completion_ratio >= 0.25:
            return "retry_from_checkpoint"
        
        # Low completion with retryable failure - full retry
        if completion_ratio < 0.25:
            return "retry_all"
        
        return "abort"
    
    def _execute_tool_with_retry(
        self,
        tool: Any,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any],
        trace_id: str,
    ) -> Any:
        """
        Execute single tool with retry logic.
        
        Wraps tool execution with RetryPolicy for automatic retry on transient failures.
        Classifies errors with FailureMode and preserves partial results.
        
        Args:
            tool: Tool from registry
            tool_name: Tool identifier
            tool_input: Tool input parameters
            context: Execution context (profile, trace_id)
            trace_id: Trace identifier for observability
            
        Returns:
            Tool execution result
            
        Raises:
            Exception: If all retries exhausted or terminal failure
        """
        attempt = 0
        last_error: Optional[Exception] = None
        
        while attempt <= self.retry_policy.get_max_attempts():
            try:
                # Execute tool handler
                result = tool.handler(tool_input, context)
                
                # Success - log if this was a retry
                if attempt > 0:
                    # TODO: Emit retry_succeeded event via observability
                    pass
                
                return result
            
            except Exception as exc:
                last_error = exc
                
                # Create failure context for classification
                failure_ctx = FailureContext.from_exception(
                    exc=exc,
                    stage=LifecycleStage.EXECUTE,
                    context=None,  # We don't have ExecutionContext in WorkerAgent
                )
                failure_ctx.retry_count = attempt
                failure_ctx.metadata.update({
                    "tool_name": tool_name,
                    "trace_id": trace_id,
                })
                
                # Check if terminal failure
                if failure_ctx.mode.terminal:
                    # Terminal failures don't retry
                    raise exc
                
                # Check if should retry
                if not self.retry_policy.should_retry(failure_ctx):
                    # No more retries
                    raise exc
                
                # Calculate delay
                delay = self.retry_policy.get_delay(attempt)
                
                # Log retry attempt
                # TODO: Emit retry_attempt event via observability
                
                # Wait before retry
                if delay > 0:
                    time.sleep(delay)
                
                attempt += 1
        
        # All retries exhausted - raise last error
        if last_error:
            raise last_error
        
        # Should never reach here
        raise RuntimeError(f"Retry logic failure for tool {tool_name}")

    def execute(
        self,
        steps: Iterable[dict],
        metadata: Optional[dict] = None,
        partial_result: Optional[PartialResult] = None,
    ) -> AgentResult:
        """
        Execute steps with observability, guardrail enforcement, and partial result preservation.
        
        Enhanced in v1.3.2 to track partial results for failure recovery. Each step's result
        is saved incrementally, allowing workflows to resume from the last successful step.
        
        Args:
            steps: Steps to execute (list of dicts with "tool" and "input")
            metadata: Execution metadata (profile, trace_id, etc.)
            partial_result: Optional PartialResult to resume from (skips completed steps)
            
        Returns:
            AgentResult with output and trace
            
        Raises:
            Exception: On failure, with PartialResult attached if available
        """
        metadata = metadata or {}
        profile = metadata.get("profile", self.memory.profile)
        trace_id = metadata.get("trace_id", f"exec-{id(self)}-{time.time()}")
        trace: List[dict] = []
        output: Any = None
        
        # Convert steps to list for counting and indexing
        steps_list = list(steps)
        total_steps = len(steps_list)
        
        # Initialize or reuse partial result tracker
        if partial_result is None:
            partial_result = PartialResult.create_empty(
                total_steps=total_steps,
                trace_id=trace_id,
            )
        
        # Determine starting index (skip completed steps if resuming)
        start_idx = len(partial_result.completed_steps)
        if start_idx > 0:
            print(f"Resuming from step {start_idx}/{total_steps} (skipped {start_idx} completed steps)")
        
        for idx, step in enumerate(steps_list[start_idx:], start=start_idx):
            tool_name = step["tool"]
            tool_input = step.get("input", {})
            
            # Get tool from registry
            try:
                tool = self.registry.get(tool_name)
                if tool is None:
                    raise KeyError(tool_name)
            except (KeyError, ValueError):
                error_msg = f"Tool {tool_name} not registered"
                
                # Emit error event
                try:
                    error_event = ToolCallEvent.create_error(
                        trace_id=trace_id,
                        tool_name=tool_name,
                        inputs=tool_input,
                        error_message=error_msg,
                        error_type="ToolNotFoundError",
                    )
                    emit_event(error_event)
                except Exception:
                    pass  # Don't fail on observability errors
                
                raise ValueError(error_msg)
            
            # Start timing
            start_time = time.perf_counter()
            
            # Emit tool_call_start event
            try:
                start_event = ToolCallEvent.create_start(
                    trace_id=trace_id,
                    tool_name=tool_name,
                    inputs=tool_input,
                    attributes={"profile": profile, "step_index": idx},
                )
                emit_event(start_event)
            except Exception as e:
                print(f"Warning: Failed to emit tool_call_start event: {e}")
            
            # Budget guard check (if guardrails enabled)
            if self.guardrail_policy and GUARDRAILS_AVAILABLE:
                try:
                    # Estimate cost (could be tool-specific in real implementation)
                    estimated_cost = 0.01  # Default cost per call (lower to allow testing)
                    budget_guard(self.guardrail_policy, cost=estimated_cost, calls=1, tokens=0)
                except ValueError as budget_error:
                    # Budget exhausted - emit budget_exceeded event
                    try:
                        budget = self.guardrail_policy.budget
                        utilization_pct = max(
                            (budget.current_cost / budget.max_cost * 100) if budget.max_cost > 0 else 0,
                            (budget.current_calls / budget.max_calls * 100) if budget.max_calls > 0 else 0,
                            (budget.current_tokens / budget.max_tokens * 100) if budget.max_tokens > 0 else 0,
                        )
                        budget_exceeded_event = BudgetEvent.create_exceeded(
                            trace_id=trace_id,
                            profile=profile,
                            budget_type="cost",  # Default to cost budget type
                            current_value=budget.current_cost,
                            limit=budget.max_cost,
                            utilization_pct=utilization_pct,
                        )
                        emit_event(budget_exceeded_event)
                    except Exception as e:
                        print(f"Warning: Failed to emit budget_exceeded event: {e}")
                    
                    # Emit error event
                    try:
                        error_event = ToolCallEvent.create_error(
                            trace_id=trace_id,
                            tool_name=tool_name,
                            inputs=tool_input,
                            error_message=str(budget_error),
                            error_type="BudgetExceededError",
                        )
                        emit_event(error_event)
                    except Exception:
                        pass
                    
                    raise budget_error
            
            # Execute tool with retry logic
            context = {"profile": profile, "trace_id": trace_id}
            try:
                # Use retry-enabled execution
                result = self._execute_tool_with_retry(
                    tool=tool,
                    tool_name=tool_name,
                    tool_input=tool_input,
                    context=context,
                    trace_id=trace_id,
                )
                output = result
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Save step result to partial result tracker (v1.3.2+)
                step_timestamp = time.perf_counter()
                partial_result.add_completed_step(
                    step_name=f"step_{idx}_{tool_name}",
                    result=result,
                    timestamp=step_timestamp,
                )
                # Update partial_data with latest output
                partial_result.partial_data["last_output"] = output
                partial_result.partial_data[f"step_{idx}_output"] = result
                
                # Emit tool_call_complete event
                try:
                    complete_event = ToolCallEvent.create_complete(
                        trace_id=trace_id,
                        tool_name=tool_name,
                        inputs=tool_input,
                        result=result,
                        duration_ms=duration_ms,
                    )
                    emit_event(complete_event)
                except Exception as e:
                    print(f"Warning: Failed to emit tool_call_complete event: {e}")
                
                # Backward compatibility trace
                event = {"event": "execute:step", "tool": tool_name, "index": idx, "trace_id": trace_id}
                trace.append(event)
                
            except Exception as tool_error:
                duration_ms = (time.perf_counter() - start_time) * 1000
                
                # Record failed step in partial result (v1.3.2+)
                step_name = f"step_{idx}_{tool_name}"
                
                # Detect failure mode from exception
                failure_mode = self._detect_failure_mode(tool_error)
                partial_result.add_failed_step(step_name, failure_mode)
                partial_result.recovery_strategy = self._suggest_recovery(
                    failure_mode,
                    partial_result.completion_ratio,
                )
                
                # Emit tool_call_error event
                try:
                    error_event = ToolCallEvent.create_error(
                        trace_id=trace_id,
                        tool_name=tool_name,
                        inputs=tool_input,
                        error_message=str(tool_error),
                        error_type=type(tool_error).__name__,
                        duration_ms=duration_ms,
                    )
                    emit_event(error_event)
                except Exception as e:
                    print(f"Warning: Failed to emit tool_call_error event: {e}")
                
                # Attach partial result to exception for recovery
                if hasattr(tool_error, "__dict__"):
                    tool_error.partial_result = partial_result  # type: ignore
                
                # Re-raise the tool error with partial result attached
                raise tool_error
            
            # Legacy observability (deprecated in v1.1.0, will be removed in v1.3.0)
            # Note: This is redundant - events are already emitted above via emit_event()
            if self.observability:
                warnings.warn(
                    "BaseEmitter.emit() calls are deprecated and redundant. "
                    "Events are automatically emitted via cuga.observability.emit_event(). "
                    "This legacy path will be removed in v1.3.0.",
                    DeprecationWarning,
                    stacklevel=2
                )
                try:
                    self.observability.emit(
                        {"event": "tool", "name": tool_name, "profile": profile, "trace_id": trace_id}
                    )
                except Exception as e:
                    # Don't fail on legacy observability errors
                    print(f"Warning: Legacy observability emit failed: {e}")
        
        # Store output in memory
        self.memory.remember(str(output), metadata={"profile": profile, "trace_id": trace_id})
        return AgentResult(output=output, trace=trace)
    
    def execute_from_partial(
        self,
        steps: Iterable[dict],
        partial_result: PartialResult,
        metadata: Optional[dict] = None,
    ) -> AgentResult:
        """
        Resume execution from a partial result (recovery method).
        
        Skips already-completed steps and continues from the failure point.
        Enhanced in v1.3.2 for robust failure recovery.
        
        Args:
            steps: Original steps (will skip completed ones)
            partial_result: PartialResult from previous failed execution
            metadata: Execution metadata (profile, trace_id)
            
        Returns:
            AgentResult with output and trace
            
        Raises:
            ValueError: If partial_result is invalid or not recoverable
            Exception: On failure (with updated PartialResult attached)
        """
        # Validate partial result
        if not partial_result.is_recoverable:
            raise ValueError(
                f"PartialResult is not recoverable: {partial_result.failure_mode.value} "
                f"(completion: {partial_result.completion_ratio:.0%})"
            )
        
        # Verify trace_id continuity
        metadata = metadata or {}
        if partial_result.trace_id:
            # Reuse same trace_id for continuity
            metadata["trace_id"] = partial_result.trace_id
        
        print(f"Resuming execution from partial result: "
              f"{len(partial_result.completed_steps)}/{partial_result.total_steps} steps completed "
              f"({partial_result.completion_ratio:.0%})")
        print(f"Recovery strategy: {partial_result.recovery_strategy}")
        print(f"Recovery hint: {partial_result.get_recovery_hint()}")
        
        # Execute remaining steps (execute method will skip completed ones)
        return self.execute(steps=steps, metadata=metadata, partial_result=partial_result)
    
    def get_partial_result_from_exception(self, exc: Exception) -> Optional[PartialResult]:
        """
        Extract PartialResult from exception if available.
        
        Args:
            exc: Exception from failed execute() call
            
        Returns:
            PartialResult if attached to exception, None otherwise
        """
        return getattr(exc, "partial_result", None)
    
    # AgentProtocol I/O Contract (v1.2.0+)
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process agent request with standardized I/O contract.
        
        Provides clean routing interface while maintaining backward compatibility
        with existing execute() method.
        
        Args:
            request: Canonical agent request (steps in inputs field)
            
        Returns:
            Canonical agent response (status, result, trace, metadata)
        """
        # Validate request
        validation_errors = request.validate()
        if validation_errors:
            return error_response(
                error_type=ErrorType.VALIDATION,
                message=f"Request validation failed: {', '.join(validation_errors)}",
                details={"validation_errors": validation_errors},
                recoverable=False,
                trace=[{"event": "validation_failed", "errors": validation_errors}],
                metadata={"trace_id": request.metadata.trace_id},
            )
        
        start_time = time.perf_counter()
        
        try:
            # Extract steps from inputs (required for worker)
            if not request.inputs or "steps" not in request.inputs:
                return error_response(
                    error_type=ErrorType.VALIDATION,
                    message="WorkerAgent requires 'steps' in request.inputs",
                    details={"inputs": request.inputs},
                    recoverable=False,
                    trace=[{"event": "missing_steps"}],
                    metadata={"trace_id": request.metadata.trace_id},
                )
            
            steps = request.inputs["steps"]
            
            # Convert AgentRequest to execute() call
            metadata_dict = {
                "profile": request.metadata.profile,
                "trace_id": request.metadata.trace_id,
                "priority": request.metadata.priority,
                **(request.context or {}),
            }
            
            # Call existing execute() method
            exec_result = self.execute(steps=steps, metadata=metadata_dict)
            
            # Convert AgentResult to AgentResponse
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return success_response(
                result={
                    "output": exec_result.output,
                    "steps_executed": len(steps),
                },
                trace=exec_result.trace,
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                    "profile": request.metadata.profile,
                    "agent_type": "worker",
                },
            )
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return error_response(
                error_type=ErrorType.EXECUTION,
                message=f"Execution failed: {str(e)}",
                details={"exception": str(e), "exception_type": type(e).__name__},
                recoverable=True,
                trace=[{"event": "exec_error", "error": str(e)}],
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                },
            )
    
    # ========== AgentLifecycleProtocol Methods ==========
    
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """Initialize worker resources (idempotent, timeout-bounded)."""
        with self._state_lock:
            if self._state in (AgentState.READY, AgentState.BUSY):
                return  # Already initialized
            
            start_time = time.perf_counter()
            self._transition_state(AgentState.INITIALIZING)
            
            try:
                # Worker initialization: validate registry/memory
                if not self.registry or not self.memory:
                    raise ValueError("Worker requires registry and memory")
                
                self._transition_state(AgentState.READY)
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.startup_time_ms = duration_ms
            except Exception as e:
                self._transition_state(AgentState.TERMINATED)
                raise RuntimeError(f"WorkerAgent startup failed: {e}") from e
    
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Clean up worker resources (MUST NOT raise exceptions)."""
        try:
            with self._state_lock:
                if self._state == AgentState.TERMINATED:
                    return  # Already shut down
                
                start_time = time.perf_counter()
                self._transition_state(AgentState.SHUTTING_DOWN)
                
                # Worker cleanup: discard ephemeral state
                # Memory persistence handled by memory system
                
                self._transition_state(AgentState.TERMINATED)
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.shutdown_time_ms = duration_ms
        except Exception as e:
            # MUST NOT raise - log and ensure terminated state
            print(f"Warning: WorkerAgent shutdown error: {e}")
            self._state = AgentState.TERMINATED
    
    def get_state(self) -> AgentState:
        """Get current lifecycle state (thread-safe read)."""
        return self._state
    
    def get_metrics(self) -> LifecycleMetrics:
        """Get lifecycle metrics."""
        return self._metrics
    
    def owns_state(self, key: str) -> StateOwnership:
        """Determine who owns a specific state key."""
        # AGENT: Ephemeral state (request-scoped, discarded on shutdown)
        if key in ("_state", "_metrics", "_state_lock", "observability", "guardrail_policy"):
            return StateOwnership.AGENT
        
        # MEMORY: Persistent state (survives restarts)
        if key == "memory":
            return StateOwnership.MEMORY
        
        # ORCHESTRATOR: Coordination state (managed by orchestrator)
        if key in ("trace_id", "routing_context", "parent_context"):
            return StateOwnership.ORCHESTRATOR
        
        # SHARED: Config (shared between components)
        if key in ("registry",):
            return StateOwnership.SHARED
        
        # Default to AGENT with warning
        print(f"Warning: Unknown state key '{key}' defaulting to AGENT ownership")
        return StateOwnership.AGENT
    
    def _transition_state(self, new_state: AgentState) -> None:
        """Atomic state transition with metrics tracking."""
        old_state = self._state
        self._state = new_state
        self._metrics.state_transitions += 1


@dataclass
class CoordinatorAgent(OrchestratorProtocol):
    """
    Production orchestrator implementing canonical OrchestratorProtocol.
    
    Responsibilities:
    - Lifecycle management (Initialize → Plan → Route → Execute → Complete)
    - Routing decisions for multi-worker coordination
    - Error handling with structured OrchestrationError
    - Trace propagation and observability
    
    Non-Responsibilities (delegated):
    - Tool registration (ToolRegistry)
    - Policy enforcement (PolicyEnforcer)
    - Memory management (VectorMemory)
    - Budget enforcement (WorkerAgent)
    
    Version: 1.3.0+
    - Implements OrchestratorProtocol
    - Lifecycle stage emissions
    - Structured error handling
    - Pluggable RoutingAuthority (v1.3.1+)
    - Pluggable PlanningAuthority (v1.3.1+)
    """
    
    planner: PlannerAgent
    workers: List[WorkerAgent]
    memory: VectorMemory
    
    # Routing authority (v1.3.1+) - pluggable routing decisions
    routing_authority: Optional[RoutingAuthority] = None
    
    # Planning authority (v1.3.1+) - pluggable planning decisions
    planning_authority: Optional[PlanningAuthority] = None
    
    # Audit trail (v1.3.2+) - persistent decision logging
    audit_trail: Optional[AuditTrail] = None
    
    # Legacy round-robin state (deprecated, will be removed when all routing goes through authority)
    _next_worker_idx: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    # Orchestrator metrics (v1.3.0+)
    _orchestrator_metrics: OrchestratorMetrics = field(default_factory=OrchestratorMetrics, init=False)
    
    # Lifecycle state (v1.2.0+)
    _state: AgentState = field(default=AgentState.UNINITIALIZED, init=False)
    _metrics: LifecycleMetrics = field(default_factory=LifecycleMetrics, init=False)
    _state_lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    
    def __post_init__(self):
        """Initialize routing and planning authorities if not provided."""
        if self.routing_authority is None:
            # Default to round-robin policy for workers
            self.routing_authority = create_routing_authority(
                worker_strategy=RoutingStrategy.ROUND_ROBIN,
            )
        
        if self.planning_authority is None:
            # Default to tool ranking planner with reasonable limits
            self.planning_authority = create_planning_authority(
                max_steps=10,
                budget=ToolBudget(
                    cost_ceiling=100.0,
                    call_ceiling=50,
                    token_ceiling=100000,
                    policy="warn",
                ),
            )
        
        if self.audit_trail is None:
            # Default to SQLite backend for production-ready audit trail
            self.audit_trail = create_audit_trail(backend_type="sqlite")
    
    # Lifecycle Protocol Implementation (v1.2.0+)
    
    async def startup(self, config: Optional[LifecycleConfig] = None) -> None:
        """Initialize coordinator and managed agents."""
        with self._state_lock:
            if self._state in (AgentState.READY, AgentState.BUSY):
                return  # Already initialized
            
            start_time = time.perf_counter()
            self._transition_state(AgentState.INITIALIZING)
            
            try:
                # Initialize managed agents
                await self.planner.startup(config)
                for worker in self.workers:
                    await worker.startup(config)
                
                self._transition_state(AgentState.READY)
                
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.startup_time_ms = duration_ms
                
            except Exception as e:
                self._transition_state(AgentState.TERMINATED)
                raise RuntimeError(f"CoordinatorAgent startup failed: {e}") from e
    
    async def shutdown(self, timeout_seconds: Optional[float] = None) -> None:
        """Clean up coordinator and managed agents."""
        start_time = time.perf_counter()
        
        try:
            with self._state_lock:
                if self._state == AgentState.TERMINATED:
                    return
                
                self._transition_state(AgentState.SHUTTING_DOWN)
                
                # Shutdown managed agents
                await self.planner.shutdown(timeout_seconds)
                for worker in self.workers:
                    await worker.shutdown(timeout_seconds)
                
                duration_ms = (time.perf_counter() - start_time) * 1000
                self._metrics.shutdown_time_ms = duration_ms
                
                self._transition_state(AgentState.TERMINATED)
                
        except Exception as e:
            print(f"Warning: CoordinatorAgent shutdown error: {e}")
            self._state = AgentState.TERMINATED
    
    def get_state(self) -> AgentState:
        """Get current lifecycle state (thread-safe)."""
        return self._state
    
    def get_metrics(self) -> LifecycleMetrics:
        """Get lifecycle metrics."""
        return self._metrics
    
    def owns_state(self, key: str) -> StateOwnership:
        """Determine who owns a specific state key."""
        # AGENT state (ephemeral, coordination-specific)
        if key in ("_state", "_metrics", "_state_lock", "_next_worker_idx", "_lock", "planner", "workers", "_orchestrator_metrics"):
            return StateOwnership.AGENT
        
        # MEMORY state (persistent)
        if key in ("memory",):
            return StateOwnership.MEMORY
        
        # ORCHESTRATOR state
        if key in ("trace_id", "routing_context", "routing_policy"):
            return StateOwnership.ORCHESTRATOR
        
        print(f"Warning: Unknown state key '{key}' - assuming AGENT ownership")
        return StateOwnership.AGENT
    
    def _transition_state(self, new_state: AgentState) -> None:
        """Transition to new state (must hold _state_lock)."""
        old_state = self._state
        self._state = new_state
        self._metrics.record_transition(old_state, new_state)
    
    # OrchestratorProtocol Implementation (v1.3.0+)
    
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ):
        """
        Full orchestration with lifecycle stage emissions.
        
        Implements OrchestratorProtocol.orchestrate() with:
        - Lifecycle stage emissions (INITIALIZE → PLAN → ROUTE → EXECUTE → COMPLETE)
        - Structured error handling with OrchestrationError
        - Trace propagation through all stages
        - Observability event emission
        
        Args:
            goal: User goal/task description
            context: Execution context with trace_id and profile
            error_strategy: How to handle errors (FAIL_FAST, RETRY, CONTINUE, FALLBACK)
            
        Yields:
            Dict containing:
                - stage: LifecycleStage
                - data: Stage-specific output
                - context: Updated execution context
                
        Raises:
            OrchestrationError: On unrecoverable failures
        """
        trace_id = context.trace_id
        
        # INITIALIZE stage
        yield {
            "stage": LifecycleStage.INITIALIZE,
            "data": {
                "goal": goal,
                "workers_available": len(self.workers),
                "profile": context.profile,
            },
            "context": context,
        }
        
        try:
            # PLAN stage - use PlanningAuthority
            plan_start = time.perf_counter()
            
            # Get available tools from planner's legacy format for now
            # TODO: Eventually move tool registry to PlanningAuthority
            legacy_plan = self.planner.plan(
                goal,
                metadata={
                    "profile": context.profile,
                    "trace_id": trace_id,
                }
            )
            
            # Convert legacy plan to available_tools format for PlanningAuthority
            available_tools = [
                {
                    "name": step.get("tool", "unknown"),
                    "description": step.get("name", ""),
                    "cost": 0.1,  # Default cost
                    "tokens": 10,  # Default tokens
                }
                for step in legacy_plan.steps
            ]
            
            # Create plan using PlanningAuthority
            authority_plan: Plan = self.planning_authority.create_plan(
                goal=goal,
                trace_id=trace_id,
                profile=context.profile,
                constraints={"available_tools": available_tools} if available_tools else None,
            )
            
            # Validate plan
            self.planning_authority.validate_plan(authority_plan)
            
            # Transition to ROUTED stage (will be updated in ROUTE stage below)
            authority_plan = authority_plan.transition_to(PlanningStage.ROUTED)
            
            # Record plan to audit trail (v1.3.2+)
            if self.audit_trail:
                try:
                    self.audit_trail.record_plan(authority_plan, stage="plan")
                except Exception as e:
                    print(f"Warning: Failed to record plan to audit trail: {e}")
            
            plan_duration_ms = (time.perf_counter() - plan_start) * 1000
            
            # Emit plan_created event
            try:
                plan_event = PlanEvent.create(
                    trace_id=trace_id,
                    goal=goal,
                    steps_count=len(authority_plan.steps),
                    tools_selected=[step.tool for step in authority_plan.steps],
                    duration_ms=plan_duration_ms,
                    attributes={
                        "profile": context.profile,
                        "plan_id": authority_plan.plan_id,
                        "budget_cost": authority_plan.budget.cost_ceiling,
                        "estimated_cost": authority_plan.estimated_total_cost(),
                    },
                )
                emit_event(plan_event)
            except Exception as e:
                print(f"Warning: Failed to emit plan_created event: {e}")
            
            yield {
                "stage": LifecycleStage.PLAN,
                "data": {
                    "plan": authority_plan,
                    "steps_count": len(authority_plan.steps),
                    "duration_ms": plan_duration_ms,
                    "budget": authority_plan.budget,
                    "planning_stage": authority_plan.stage.value,
                },
                "context": context,
            }
            
            # Validate workers
            if not self.workers:
                raise OrchestrationError(
                    stage=LifecycleStage.ROUTE,
                    message="No workers configured",
                    context=context,
                    recoverable=False,
                )
            
            # ROUTE stage - Use RoutingAuthority
            routing_start = time.perf_counter()
            
            # Create routing context from execution context
            routing_context = RoutingContext(
                trace_id=context.trace_id,
                profile=context.profile,
                goal=goal,
                task=goal,
                metadata=context.metadata,
            )
            
            # Create worker candidates
            worker_candidates = [
                RoutingCandidate(
                    id=f"worker-{i}",
                    name=f"worker-{i}",
                    type="worker",
                    available=True,
                )
                for i in range(len(self.workers))
            ]
            
            # Use RoutingAuthority to make decision
            routing_decision_full = self.routing_authority.route_to_worker(
                context=routing_context,
                workers=worker_candidates,
            )
            
            # Extract selected worker index
            selected_id = routing_decision_full.selected.id
            worker_idx = int(selected_id.split("-")[1])  # Extract index from "worker-N"
            worker = self.workers[worker_idx]
            
            routing_duration_ms = (time.perf_counter() - routing_start) * 1000
            
            self._orchestrator_metrics.record_routing()
            
            # Record routing decision to audit trail (v1.3.2+)
            if self.audit_trail:
                try:
                    self.audit_trail.record_routing_decision(
                        routing_decision_full,
                        trace_id=trace_id,
                        stage="route",
                    )
                except Exception as e:
                    print(f"Warning: Failed to record routing decision to audit trail: {e}")
            
            # Emit route_decision event
            try:
                route_event = RouteEvent.create(
                    trace_id=trace_id,
                    agent_selected=selected_id,
                    alternatives_considered=[c.id for c in routing_decision_full.alternatives],
                    reason=routing_decision_full.reason,
                    duration_ms=routing_duration_ms,
                    attributes={
                        "worker_count": len(self.workers),
                        "selected_index": worker_idx,
                        "profile": context.profile,
                        "strategy": routing_decision_full.strategy.value,
                        "confidence": routing_decision_full.confidence,
                    },
                )
                emit_event(route_event)
            except Exception as e:
                print(f"Warning: Failed to emit route_decision event: {e}")
            
            yield {
                "stage": LifecycleStage.ROUTE,
                "data": {
                    "decision": routing_decision_full,
                    "worker_index": worker_idx,
                    "duration_ms": routing_duration_ms,
                },
                "context": context,
            }
            
            # EXECUTE stage
            # Transition plan to EXECUTING stage
            authority_plan = authority_plan.transition_to(PlanningStage.EXECUTING)
            
            execute_start = time.perf_counter()
            
            # Convert PlanningAuthority plan steps to legacy format for worker execution
            # TODO: Update WorkerAgent to accept Plan directly
            legacy_steps = [
                {
                    "tool": step.tool,
                    "input": step.input,
                    "name": step.name,
                    "reason": step.reason,
                }
                for step in authority_plan.steps
            ]
            
            result = worker.execute(
                legacy_steps,
                metadata={
                    "profile": context.profile,
                    "trace_id": trace_id,
                    "plan_id": authority_plan.plan_id,
                }
            )
            execute_duration_ms = (time.perf_counter() - execute_start) * 1000
            
            # Transition plan to COMPLETED stage
            authority_plan = authority_plan.transition_to(PlanningStage.COMPLETED)
            
            self._orchestrator_metrics.record_success()
            
            yield {
                "stage": LifecycleStage.EXECUTE,
                "data": {
                    "result": result,
                    "duration_ms": execute_duration_ms,
                    "plan_stage": authority_plan.stage.value,
                },
                "context": context,
            }
            
            # AGGREGATE stage (combine traces)
            # authority_plan doesn't have legacy trace attribute, use result trace
            all_traces = list(result.trace) if hasattr(result, 'trace') else []
            
            yield {
                "stage": LifecycleStage.AGGREGATE,
                "data": {
                    "trace_length": len(all_traces),
                    "output": result.output,
                },
                "context": context,
            }
            
            # COMPLETE stage
            yield {
                "stage": LifecycleStage.COMPLETE,
                "data": {
                    "output": result.output,
                    "trace": all_traces,
                    "metrics": {
                        "plan_duration_ms": plan_duration_ms,
                        "routing_duration_ms": routing_duration_ms,
                        "execute_duration_ms": execute_duration_ms,
                        "total_duration_ms": plan_duration_ms + routing_duration_ms + execute_duration_ms,
                    },
                },
                "context": context,
            }
            
        except OrchestrationError:
            # Re-raise orchestration errors
            raise
        except Exception as e:
            # Wrap other exceptions
            self._orchestrator_metrics.record_failure()
            
            error = OrchestrationError(
                stage=LifecycleStage.EXECUTE,
                message=f"Orchestration failed: {str(e)}",
                context=context,
                cause=e,
                recoverable=error_strategy != ErrorPropagation.FAIL_FAST,
            )
            
            # Handle error according to strategy
            recovery_result = await self.handle_error(error, error_strategy)
            
            if recovery_result is not None:
                yield recovery_result
            else:
                # FAILED stage
                yield {
                    "stage": LifecycleStage.FAILED,
                    "data": {
                        "error": str(error),
                        "recoverable": error.recoverable,
                    },
                    "context": context,
                }
                raise error
    
    def make_routing_decision(
        self,
        task: str,
        context: ExecutionContext,
        available_agents: List[str],
    ) -> ProtocolRoutingDecision:
        """
        Make explicit routing decision using RoutingAuthority.
        
        This method now delegates to RoutingAuthority for pluggable routing
        strategies. Converts full RoutingDecision to protocol format.
        
        Args:
            task: Task description to route
            context: Current execution context
            available_agents: List of available agent identifiers
            
        Returns:
            ProtocolRoutingDecision with target, reason, and metadata
        """
        if not available_agents:
            return ProtocolRoutingDecision(
                target="none",
                reason="no_workers_available",
                metadata={"alternatives": []},
            )
        
        # Create routing context
        routing_context = RoutingContext(
            trace_id=context.trace_id,
            profile=context.profile,
            goal=context.user_intent,
            task=task,
            metadata=context.metadata,
        )
        
        # Create candidates
        candidates = [
            RoutingCandidate(
                id=agent_id,
                name=agent_id,
                type="worker",
                available=True,
            )
            for agent_id in available_agents
        ]
        
        # Use RoutingAuthority to make decision
        full_decision = self.routing_authority.route_to_worker(
            context=routing_context,
            workers=candidates,
        )
        
        # Convert to protocol format (simple version)
        return ProtocolRoutingDecision(
            target=full_decision.selected.id,
            reason=full_decision.reason,
            metadata={
                "alternatives": [c.id for c in full_decision.alternatives],
                "strategy": full_decision.strategy.value,
                "confidence": full_decision.confidence,
                "decision_type": full_decision.decision_type.value,
            },
            fallback=full_decision.fallback.id if full_decision.fallback else None,
        )
    
    async def handle_error(
        self,
        error: OrchestrationError,
        strategy: ErrorPropagation,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle orchestration error with specified strategy.
        
        Args:
            error: Orchestration error to handle
            strategy: Error handling strategy
            
        Returns:
            Recovery result if strategy allows, None otherwise
            
        Raises:
            OrchestrationError: If strategy is FAIL_FAST or recovery not possible
        """
        if strategy == ErrorPropagation.FAIL_FAST:
            # Re-raise immediately
            raise error
        
        elif strategy == ErrorPropagation.CONTINUE:
            # Log and continue
            print(f"Warning: Orchestration error (continuing): {error}")
            return {
                "stage": LifecycleStage.FAILED,
                "data": {
                    "error": str(error),
                    "strategy": "continue",
                    "recoverable": error.recoverable,
                },
                "context": error.context,
            }
        
        elif strategy == ErrorPropagation.RETRY:
            # Retry not yet implemented (Task #4)
            print(f"Warning: RETRY strategy requested but not implemented: {error}")
            raise error
        
        elif strategy == ErrorPropagation.FALLBACK:
            # Fallback routing not yet implemented (Task #2)
            print(f"Warning: FALLBACK strategy requested but not implemented: {error}")
            raise error
        
        else:
            # Unknown strategy
            raise error
    
    def get_lifecycle(self) -> AgentLifecycle:
        """
        Get lifecycle manager for this orchestrator.
        
        Returns:
            Self (implements lifecycle via startup/shutdown methods)
        """
        # CoordinatorAgent implements lifecycle via startup/shutdown
        # Return a wrapper that conforms to AgentLifecycle protocol
        class CoordinatorLifecycle:
            def __init__(self, coordinator: CoordinatorAgent):
                self.coordinator = coordinator
            
            async def initialize(self, context: ExecutionContext) -> None:
                """Initialize coordinator."""
                await self.coordinator.startup()
            
            async def teardown(self, context: ExecutionContext) -> None:
                """Teardown coordinator."""
                await self.coordinator.shutdown()
            
            def get_stage(self) -> LifecycleStage:
                """Get current lifecycle stage."""
                state = self.coordinator.get_state()
                # Map AgentState to LifecycleStage
                if state == AgentState.UNINITIALIZED:
                    return LifecycleStage.INITIALIZE
                elif state == AgentState.READY:
                    return LifecycleStage.COMPLETE
                elif state == AgentState.BUSY:
                    return LifecycleStage.EXECUTE
                elif state == AgentState.SHUTTING_DOWN:
                    return LifecycleStage.COMPLETE
                elif state == AgentState.TERMINATED:
                    return LifecycleStage.COMPLETE
                else:
                    return LifecycleStage.INITIALIZE
        
        return CoordinatorLifecycle(self)  # type: ignore
    
    def get_orchestrator_metrics(self) -> OrchestratorMetrics:
        """Get orchestrator metrics."""
        return self._orchestrator_metrics
    
    # AgentProtocol I/O Contract (v1.2.0+)
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process agent request with standardized I/O contract.
        
        Uses new orchestrate() method (v1.3.0+) with full lifecycle stages.
        Maintains backward compatibility with AgentProtocol contract.
        
        Args:
            request: Canonical agent request (goal for coordination)
            
        Returns:
            Canonical agent response (status, result, trace, metadata)
        """
        # Validate request
        validation_errors = request.validate()
        if validation_errors:
            return error_response(
                error_type=ErrorType.VALIDATION,
                message=f"Request validation failed: {', '.join(validation_errors)}",
                details={"validation_errors": validation_errors},
                recoverable=False,
                trace=[{"event": "validation_failed", "errors": validation_errors}],
                metadata={"trace_id": request.metadata.trace_id},
            )
        
        start_time = time.perf_counter()
        
        try:
            # Create ExecutionContext from request metadata
            context = ExecutionContext(
                trace_id=request.metadata.trace_id,
                profile=request.metadata.profile,
                user_intent=request.goal,
            )
            
            # Call orchestrate() and collect all events
            all_events = []
            final_data = None
            
            async for event in self.orchestrate(goal=request.goal, context=context):
                all_events.append(event)
                
                # Keep final output from COMPLETE or last stage
                if event["stage"] in (LifecycleStage.COMPLETE, LifecycleStage.AGGREGATE):
                    final_data = event["data"]
            
            # Extract output and trace
            if final_data is None:
                final_data = all_events[-1]["data"] if all_events else {}
            
            output = final_data.get("output", "")
            trace = final_data.get("trace", [])
            
            # Convert lifecycle events to trace entries
            for event in all_events:
                trace.append({
                    "stage": event["stage"].value,
                    "data": event.get("data", {}),
                })
            
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return success_response(
                result={
                    "output": output,
                    "trace_length": len(trace),
                    "lifecycle_stages": [e["stage"].value for e in all_events],
                },
                trace=trace,
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                    "profile": request.metadata.profile,
                    "agent_type": "coordinator",
                    "workers_available": len(self.workers),
                    "orchestration_version": "1.3.0",
                },
            )
            
        except OrchestrationError as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return error_response(
                error_type=ErrorType.EXECUTION,
                message=f"Orchestration failed: {e.message}",
                details={
                    "stage": e.stage.value,
                    "recoverable": e.recoverable,
                    "cause": str(e.cause) if e.cause else None,
                },
                recoverable=e.recoverable,
                trace=[{"event": "orchestration_error", "stage": e.stage.value, "error": e.message}],
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                },
            )
            
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            return error_response(
                error_type=ErrorType.EXECUTION,
                message=f"Coordination failed: {str(e)}",
                details={"exception": str(e), "exception_type": type(e).__name__},
                recoverable=True,
                trace=[{"event": "coord_error", "error": str(e)}],
                metadata={
                    "duration_ms": duration_ms,
                    "trace_id": request.metadata.trace_id,
                },
            )

    def dispatch(self, goal: str, trace_id: Optional[str] = None) -> AgentResult:
        """Dispatch goal to planner and worker with observability."""
        if trace_id is None:
            trace_id = f"coord-{id(self)}-{time.time()}"
        
        # Start timing for routing decision
        routing_start = time.perf_counter()
        
        # Create plan
        plan = self.planner.plan(
            goal, metadata={"profile": self.planner.config.profile, "trace_id": trace_id}
        )
        traces = list(plan.trace)
        
        if not self.workers:
            raise ValueError("No workers configured")
        
        # Select worker (round-robin)
        worker = self._select_worker()
        worker_idx = (self._next_worker_idx - 1) % len(self.workers)  # Get the index that was just selected
        
        # Calculate routing duration
        routing_duration_ms = (time.perf_counter() - routing_start) * 1000
        
        # Emit route_decision event
        try:
            route_event = RouteEvent.create(
                trace_id=trace_id,
                agent_selected=f"worker-{worker_idx}",
                alternatives_considered=[f"worker-{i}" for i in range(len(self.workers))],
                reason="round_robin",
                duration_ms=routing_duration_ms,
                attributes={
                    "worker_count": len(self.workers),
                    "selected_index": worker_idx,
                    "profile": self.planner.config.profile,
                },
            )
            emit_event(route_event)
        except Exception as e:
            print(f"Warning: Failed to emit route_decision event: {e}")
        
        # Execute with selected worker
        result = worker.execute(
            plan.steps, metadata={"profile": self.planner.config.profile, "trace_id": trace_id}
        )
        traces.extend(result.trace)
        return AgentResult(output=result.output, trace=traces)

    def _select_worker(self) -> WorkerAgent:
        """Thread-safe round-robin worker selection."""
        with self._lock:
            if not self.workers:
                raise ValueError("No workers available to select from.")
            worker = self.workers[self._next_worker_idx]
            self._next_worker_idx = (self._next_worker_idx + 1) % len(self.workers)
        return worker


def create_coordinator(
    planner: PlannerAgent,
    workers: List[WorkerAgent],
    memory: VectorMemory,
    *,
    routing_strategy: RoutingStrategy = RoutingStrategy.ROUND_ROBIN,
    max_plan_steps: int = 10,
    default_budget: Optional[ToolBudget] = None,
) -> CoordinatorAgent:
    """
    Factory function for creating CoordinatorAgent with pluggable routing and planning.
    
    Args:
        planner: PlannerAgent for plan creation
        workers: List of WorkerAgents for execution
        memory: VectorMemory for context storage
        routing_strategy: Routing strategy for worker selection
            - ROUND_ROBIN: Distribute requests evenly (default)
            - CAPABILITY: Match based on worker capabilities
            - LOAD_BALANCED: Route based on current load
        max_plan_steps: Maximum steps per plan (default: 10)
        default_budget: Default tool budget (default: 100 cost, 50 calls, 100k tokens)
            
    Returns:
        Fully configured CoordinatorAgent with routing and planning authorities
        
    Example:
        >>> coordinator = create_coordinator(
        ...     planner=planner,
        ...     workers=[worker1, worker2],
        ...     memory=memory,
        ...     routing_strategy=RoutingStrategy.CAPABILITY,
        ...     max_plan_steps=15,
        ...     default_budget=ToolBudget(cost_ceiling=200.0),
        ... )
    """
    routing_authority = create_routing_authority(
        worker_strategy=routing_strategy,
    )
    
    planning_authority = create_planning_authority(
        max_steps=max_plan_steps,
        budget=default_budget,
    )
    
    return CoordinatorAgent(
        planner=planner,
        workers=workers,
        memory=memory,
        routing_authority=routing_authority,
        planning_authority=planning_authority,
    )


def build_default_registry() -> ToolRegistry:
    """Build default registry with echo tool for testing."""
    def echo_handler(inputs: Dict[str, Any], ctx: Dict[str, Any]) -> str:
        return inputs.get("text", "")
    
    echo_tool = ToolSpec(
        name="echo",
        description="Echo text",
        handler=echo_handler,
    )
    return ToolRegistry(tools=[echo_tool])
