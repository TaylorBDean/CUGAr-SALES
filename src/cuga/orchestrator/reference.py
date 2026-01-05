"""
Reference Orchestrator Implementation

This module provides a reference implementation of OrchestratorProtocol
demonstrating best practices for lifecycle management, routing, and error handling.

Use this as a starting point for custom orchestrators.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from cuga.orchestrator import (
    AgentLifecycle,
    ErrorPropagation,
    ExecutionContext,
    LifecycleStage,
    OrchestrationError,
    OrchestratorProtocol,
    RoutingDecision,
)

logger = logging.getLogger(__name__)


class ReferenceLifecycle(AgentLifecycle):
    """Reference implementation of AgentLifecycle."""
    
    def __init__(self) -> None:
        self._stage = LifecycleStage.INITIALIZE
    
    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize agent resources."""
        logger.info(f"Initializing agent for trace_id={context.trace_id}")
        self._stage = LifecycleStage.INITIALIZE
        # Initialize resources here (connections, registries, etc.)
        await asyncio.sleep(0)  # Simulate async initialization
    
    async def teardown(self, context: ExecutionContext) -> None:
        """Clean up agent resources."""
        logger.info(f"Tearing down agent for trace_id={context.trace_id}")
        try:
            # Clean up resources here
            await asyncio.sleep(0)  # Simulate async teardown
        except Exception as e:
            # MUST NOT raise - log errors internally
            logger.error(f"Teardown error: {e}", exc_info=True)
    
    def get_stage(self) -> LifecycleStage:
        """Return current lifecycle stage."""
        return self._stage


class ReferenceOrchestrator(OrchestratorProtocol):
    """
    Reference orchestrator implementation.
    
    Demonstrates:
    - Proper lifecycle stage emission
    - Deterministic routing decisions
    - Error handling strategies
    - Context propagation
    
    Usage:
        orchestrator = ReferenceOrchestrator(
            workers=["worker1", "worker2"],
            planner=planner_agent,
        )
        
        context = ExecutionContext(trace_id="abc123", profile="demo")
        
        async for event in orchestrator.orchestrate("search docs", context):
            print(f"Stage: {event['stage']}, Data: {event['data']}")
    """
    
    def __init__(
        self,
        workers: List[str],
        planner: Any = None,
        *,
        default_worker: Optional[str] = None,
    ) -> None:
        """
        Initialize reference orchestrator.
        
        Args:
            workers: List of available worker identifiers
            planner: Optional planner agent for task decomposition
            default_worker: Default worker if routing decision fails
        """
        self.workers = workers
        self.planner = planner
        self.default_worker = default_worker or (workers[0] if workers else None)
        self._lifecycle = ReferenceLifecycle()
        self._worker_index = 0  # For round-robin routing
    
    async def orchestrate(
        self,
        goal: str,
        context: ExecutionContext,
        *,
        error_strategy: ErrorPropagation = ErrorPropagation.FAIL_FAST,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        Orchestrate task execution with lifecycle stages.
        
        Yields events at each lifecycle stage with data and updated context.
        """
        # Stage 1: Initialize
        try:
            await self._lifecycle.initialize(context)
            yield {
                "stage": LifecycleStage.INITIALIZE,
                "data": {"workers": self.workers},
                "context": context,
            }
        except Exception as e:
            error = OrchestrationError(
                stage=LifecycleStage.INITIALIZE,
                message="Failed to initialize orchestrator",
                context=context,
                cause=e,
                recoverable=False,
            )
            yield {"stage": LifecycleStage.FAILED, "data": {"error": str(error)}, "context": context}
            await self._lifecycle.teardown(context)
            return
        
        # Stage 2: Plan
        try:
            plan = await self._plan(goal, context)
            yield {
                "stage": LifecycleStage.PLAN,
                "data": {"plan": plan, "num_steps": len(plan)},
                "context": context,
            }
        except Exception as e:
            await self._handle_stage_error(
                stage=LifecycleStage.PLAN,
                context=context,
                error=e,
                error_strategy=error_strategy,
            )
            yield {"stage": LifecycleStage.FAILED, "data": {"error": str(e)}, "context": context}
            await self._lifecycle.teardown(context)
            return
        
        # Stage 3-5: Route → Execute → Aggregate
        results = []
        for step in plan:
            # Route
            routing_decision = self.make_routing_decision(
                task=step.get("task", goal),
                context=context,
                available_agents=self.workers,
            )
            yield {
                "stage": LifecycleStage.ROUTE,
                "data": {
                    "decision": routing_decision,
                    "step": step,
                },
                "context": context,
            }
            
            # Execute
            try:
                result = await self._execute_step(step, routing_decision, context)
                yield {
                    "stage": LifecycleStage.EXECUTE,
                    "data": {
                        "step": step,
                        "worker": routing_decision.target,
                        "result": result,
                    },
                    "context": context,
                }
                results.append(result)
            except Exception as e:
                error = OrchestrationError(
                    stage=LifecycleStage.EXECUTE,
                    message=f"Step execution failed: {step}",
                    context=context,
                    cause=e,
                    recoverable=routing_decision.fallback is not None,
                )
                
                recovery = await self.handle_error(error, error_strategy)
                if recovery:
                    yield {
                        "stage": LifecycleStage.EXECUTE,
                        "data": {"recovery": recovery},
                        "context": context,
                    }
                    results.append(recovery)
                elif error_strategy == ErrorPropagation.FAIL_FAST:
                    yield {
                        "stage": LifecycleStage.FAILED,
                        "data": {"error": str(error)},
                        "context": context,
                    }
                    await self._lifecycle.teardown(context)
                    return
        
        # Aggregate results
        aggregated = await self._aggregate_results(results, context)
        yield {
            "stage": LifecycleStage.AGGREGATE,
            "data": {"results": aggregated, "count": len(results)},
            "context": context,
        }
        
        # Stage 6: Complete
        yield {
            "stage": LifecycleStage.COMPLETE,
            "data": {
                "success": True,
                "output": aggregated,
            },
            "context": context,
        }
        
        # Always teardown
        await self._lifecycle.teardown(context)
    
    def make_routing_decision(
        self,
        task: str,
        context: ExecutionContext,
        available_agents: List[str],
    ) -> RoutingDecision:
        """
        Make deterministic routing decision using round-robin.
        
        Override this method to implement custom routing logic
        (e.g., capability-based, cost-based, load-based).
        """
        if not available_agents:
            return RoutingDecision(
                target=self.default_worker or "unknown",
                reason="No available agents, using default",
                metadata={"available_count": 0},
            )
        
        # Simple round-robin for demonstration
        target = available_agents[self._worker_index % len(available_agents)]
        self._worker_index += 1
        
        # Check for fallback
        fallback = None
        if len(available_agents) > 1:
            fallback_idx = (self._worker_index) % len(available_agents)
            fallback = available_agents[fallback_idx]
        
        return RoutingDecision(
            target=target,
            reason=f"Round-robin selection (index={self._worker_index - 1})",
            metadata={
                "available_count": len(available_agents),
                "task_prefix": task[:20],
            },
            fallback=fallback,
        )
    
    async def handle_error(
        self,
        error: OrchestrationError,
        strategy: ErrorPropagation,
    ) -> Optional[Dict[str, Any]]:
        """
        Handle orchestration error per strategy.
        
        Implements:
        - FAIL_FAST: Re-raise immediately
        - CONTINUE: Log and return None
        - RETRY: Attempt retry (not implemented in reference)
        - FALLBACK: Use fallback routing decision
        """
        logger.error(
            f"Orchestration error at {error.stage}: {error.message}",
            extra={"trace_id": error.context.trace_id},
        )
        
        if strategy == ErrorPropagation.FAIL_FAST:
            raise error
        
        elif strategy == ErrorPropagation.CONTINUE:
            logger.warning(f"Continuing despite error: {error.message}")
            return None
        
        elif strategy == ErrorPropagation.RETRY:
            # In a real implementation, implement exponential backoff
            logger.info("Retry not implemented in reference orchestrator")
            return None
        
        elif strategy == ErrorPropagation.FALLBACK:
            if error.recoverable:
                logger.info("Attempting fallback recovery")
                return {"fallback": True, "original_error": str(error)}
            else:
                raise error
        
        return None
    
    def get_lifecycle(self) -> AgentLifecycle:
        """Return lifecycle manager."""
        return self._lifecycle
    
    # Private helper methods
    
    async def _plan(self, goal: str, context: ExecutionContext) -> List[Dict[str, Any]]:
        """Decompose goal into plan steps."""
        if self.planner:
            # Delegate to planner agent
            plan_result = self.planner.plan(goal, metadata=context.metadata)
            return [{"task": step["tool"], "input": step["input"]} for step in plan_result.steps]
        else:
            # Simple single-step plan
            return [{"task": goal, "input": {}}]
    
    async def _execute_step(
        self,
        step: Dict[str, Any],
        routing_decision: RoutingDecision,
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Execute a single step with selected worker."""
        # In a real implementation, this would call worker.execute()
        await asyncio.sleep(0.01)  # Simulate work
        return {
            "worker": routing_decision.target,
            "step": step,
            "output": f"Executed {step['task']} via {routing_decision.target}",
        }
    
    async def _aggregate_results(
        self,
        results: List[Dict[str, Any]],
        context: ExecutionContext,
    ) -> Dict[str, Any]:
        """Aggregate step results into final output."""
        return {
            "results": results,
            "count": len(results),
            "trace_id": context.trace_id,
        }
    
    async def _handle_stage_error(
        self,
        stage: LifecycleStage,
        context: ExecutionContext,
        error: Exception,
        error_strategy: ErrorPropagation,
    ) -> None:
        """Handle error at a specific stage."""
        orchestration_error = OrchestrationError(
            stage=stage,
            message=f"Error in {stage.value}",
            context=context,
            cause=error,
            recoverable=False,
        )
        
        await self.handle_error(orchestration_error, error_strategy)
