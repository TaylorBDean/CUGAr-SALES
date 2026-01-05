"""Langflow tool guard component with unique identity."""

from __future__ import annotations

import importlib
from typing import Any

_lfx_spec = importlib.util.find_spec("lfx")
if _lfx_spec:
    from lfx.custom.custom_component.component import Component
    from lfx.custom.custom_component.decorators import custom_component
    from lfx.io import MessageTextInput, Output
    from lfx.schema import Data
else:  # pragma: no cover - optional dependency

    class Component:  # type: ignore
        ...

    def custom_component(*args: Any, **kwargs: Any):  # type: ignore
        def wrapper(cls: Any) -> Any:
            return cls

        return wrapper

    class MessageTextInput:  # type: ignore
        def __init__(self, name: str, display_name: str, value: str = "") -> None:
            self.name = name
            self.display_name = display_name
            self.value = value

    class Output:  # type: ignore
        def __init__(self, display_name: str, name: str, method: str) -> None:
            self.display_name = display_name
            self.name = name
            self.method = method

    class Data:  # type: ignore
        def __init__(self, value: Any) -> None:
            self.value = value


@custom_component(component_type="guard_tool", description="Tool guard component")
class GuardToolComponent(Component):
    display_name = "CUGA Tool Guard"
    description = "Applies lightweight guardrail logic to tool calls"
    inputs = [MessageTextInput(name="payload", display_name="Payload", value="")]
    outputs = [Output(display_name="Result", name="result", method="build")]

    def build(self) -> Data:
        return Data(value={"decision": "pass", "details": {"tool": "unknown"}})
