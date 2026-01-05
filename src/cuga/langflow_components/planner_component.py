"""Langflow planner component stub.

Provides compatibility with Langflow >=1.7 without performing remote calls in tests.
"""

from __future__ import annotations

from typing import Any, Dict

try:
    from langflow.custom import custom_component
    from langflow.custom.custom_component.component import Component
except Exception:  # pragma: no cover - soft dependency
    Component = object  # type: ignore
    custom_component = lambda *args, **kwargs: (lambda cls: cls)


@custom_component(component_type="planner", description="Planner bridge for cuga")
class PlannerComponent(Component):
    display_name = "CUGA Planner"
    description = "Deterministic planner wrapper"

    def build_config(self) -> Dict[str, Any]:  # pragma: no cover - UI metadata
        return {"goal": {"type": "str", "required": True}, "metadata": {"type": "dict", "required": False}}

    def __call__(self, goal: str, metadata: Dict[str, Any] | None = None) -> Dict[str, Any]:
        metadata = metadata or {}
        return {"plan": [goal], "metadata": metadata}
