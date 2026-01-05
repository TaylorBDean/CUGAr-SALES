"""Controller orchestrating planner and executor layers."""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, Dict

from .executor import ExecutionContext, ExecutionResult, Executor
from .policy import PolicyEnforcer
from .planner import Planner, PlanningPreferences
from .registry import ToolRegistry


@dataclass
class Controller:
    planner: Planner
    executor: Executor
    registry: ToolRegistry
    policy_enforcer: PolicyEnforcer = field(default_factory=PolicyEnforcer)

    def __post_init__(self) -> None:
        if getattr(self.executor, "policy_enforcer", None) is None:
            self.executor.policy_enforcer = self.policy_enforcer

    def run(
        self,
        goal: str,
        profile: str,
        *,
        metadata: Dict[str, Any] | None = None,
        preferences: PlanningPreferences | None = None,
    ) -> ExecutionResult:
        trace_entries: list[Any] = []
        sandboxed_registry = self.registry.sandbox(profile)
        self.policy_enforcer.validate_metadata(profile, metadata or {})
        audit_logger = logging.getLogger("cuga.agents.audit")
        controller_audit = {
            "event": "controller_run",
            "profile": profile,
            "tool": "planner",
            "input": {"goal": goal, "metadata": metadata or {}},
            "policy_decision": "metadata_validated",
        }
        audit_logger.info("audit", extra={"audit": controller_audit})
        trace_entries.append(controller_audit)

        plan_result = self.planner.plan(goal, sandboxed_registry, preferences=preferences)
        trace_entries.extend(plan_result.trace or [])
        context = ExecutionContext(profile=profile, metadata=metadata)
        return self.executor.execute_plan(plan_result.steps, sandboxed_registry, context, trace=trace_entries)
