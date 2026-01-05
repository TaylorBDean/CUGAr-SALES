from __future__ import annotations

from typing import Any, Dict

from .orchestrator import BaseGuard, GuardResult


class ToolGuard(BaseGuard):
    def evaluate(self, payload: Dict[str, Any]) -> GuardResult:
        decision = "pass" if payload.get("readonly", True) else "review"
        return GuardResult(decision=decision, details={"tool": payload.get("tool")})
