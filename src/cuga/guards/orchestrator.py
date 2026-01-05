from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class GuardResult:
    decision: str  # "pass" | "review" | "fail"
    details: Dict[str, Any]


class BaseGuard:
    def evaluate(self, payload: Dict[str, Any]) -> GuardResult:  # pragma: no cover
        raise NotImplementedError


class GuardrailOrchestrator:
    def __init__(self, input_guard: BaseGuard, tool_guard: BaseGuard, output_guard: BaseGuard) -> None:
        self.input_guard = input_guard
        self.tool_guard = tool_guard
        self.output_guard = output_guard

    def route(self, stage: str, payload: Dict[str, Any]) -> GuardResult:
        if stage == "input":
            return self.input_guard.evaluate(payload)
        if stage == "tool":
            return self.tool_guard.evaluate(payload)
        return self.output_guard.evaluate(payload)
