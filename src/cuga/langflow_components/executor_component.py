"""Langflow executor component stub with registry integration placeholder."""

from __future__ import annotations

from typing import Any, Dict, List

try:
    from langflow.custom import custom_component
    from langflow.custom.custom_component.component import Component
except Exception:  # pragma: no cover
    Component = object  # type: ignore
    custom_component = lambda *args, **kwargs: (lambda cls: cls)


@custom_component(component_type="executor", description="Executes a planned list of steps")
class ExecutorComponent(Component):
    display_name = "CUGA Executor"
    description = "Executes plan steps via registry"

    def build_config(self) -> Dict[str, Any]:  # pragma: no cover - UI metadata
        return {"plan": {"type": "list", "required": True}, "sandbox": {"type": "str", "required": False}}

    def __call__(self, plan: List[str], sandbox: str | None = None) -> Dict[str, Any]:
        sandbox = sandbox or "local"
        return {"results": plan, "sandbox": sandbox}
