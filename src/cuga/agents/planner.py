"""Task planner for controller-led orchestration."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, List, Literal

from .registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """Single unit of work for the executor."""

    name: str
    tool: str
    input: dict[str, Any]


@dataclass
class PlanningPreferences:
    """Planner tuning options for optimization and topology."""

    optimization: Literal["balanced", "cost", "latency"] = "balanced"
    max_steps: int | None = None


@dataclass
class PlanningResult:
    """Plan output with trace information for observability."""

    steps: List[PlanStep]
    trace: List[str]
    profile: str
    optimization: str


class Planner:
    """Builds an optimized, traceable plan from a goal and available tools."""

    def __init__(self) -> None:
        self._last_trace: List[str] = []

    def _score_tool(self, cost: float, latency: float, mode: Literal["balanced", "cost", "latency"]) -> float:
        if mode == "cost":
            return cost + (0.1 * latency)
        if mode == "latency":
            return latency + (0.1 * cost)
        return (cost + latency) / 2

    def plan(
        self, goal: str, registry: ToolRegistry, *, preferences: PlanningPreferences | None = None
    ) -> PlanningResult:
        prefs = preferences or PlanningPreferences()
        trace: List[str] = []

        profiles = sorted(list(registry.profiles()))
        if not profiles:
            raise ValueError("No profiles available for planning")
        profile = profiles[0]
        trace.append(f"Selected profile '{profile}' from {len(profiles)} available profiles")

        profile_tools = registry.tools_for_profile(profile)
        if not profile_tools:
            raise ValueError(f"No tools registered for profile '{profile}'")

        scored_tools = []
        for name, entry in profile_tools.items():
            cost = float(entry.get("cost", 1.0))
            latency = float(entry.get("latency", 1.0))
            score = self._score_tool(cost, latency, prefs.optimization)
            scored_tools.append((score, name, cost, latency))
            trace.append(
                f"Scored tool '{name}' with cost={cost:.2f}, latency={latency:.2f}, score={score:.2f}"
            )

        scored_tools.sort(key=lambda item: (item[0], item[1]))
        max_steps = prefs.max_steps or min(2, len(scored_tools)) or 1
        chosen_tools = scored_tools[:max_steps]

        steps: List[PlanStep] = []
        for index, (_, name, _cost, _latency) in enumerate(chosen_tools, start=1):
            step_name = f"step-{index}:{goal}"
            steps.append(
                PlanStep(
                    name=step_name,
                    tool=name,
                    input={"goal": goal, "profile": profile, "sequence": index},
                )
            )
            trace.append(f"Added plan step '{step_name}' using tool '{name}'")

        logger.info("Constructed plan with %s steps for goal '%s'", len(steps), goal)
        for message in trace:
            logger.debug("[planner] %s", message)

        self._last_trace = trace
        return PlanningResult(steps=steps, trace=trace, profile=profile, optimization=prefs.optimization)

    @property
    def last_trace(self) -> List[str]:
        return list(self._last_trace)
