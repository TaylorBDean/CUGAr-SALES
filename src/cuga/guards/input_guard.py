from __future__ import annotations

from typing import Any, Dict

from .orchestrator import BaseGuard, GuardResult


class InputGuard(BaseGuard):
    def evaluate(self, payload: Dict[str, Any]) -> GuardResult:
        return GuardResult(decision="pass", details={"checked": True, "payload": payload})
