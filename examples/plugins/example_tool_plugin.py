"""Example ToolPlugin demonstrating the expected API."""

from __future__ import annotations

from cuga.agents.registry import ToolRegistry
from cuga.plugins import ToolPlugin


def echo_tool(payload: dict, *, config: dict, context) -> dict:
    return {
        "echo": payload.get("goal"),
        "profile": payload.get("profile"),
        "config": config,
        "metadata": context.metadata,
    }


class Plugin(ToolPlugin):
    name = "example-echo"
    description = "Minimal echo tool for demonstrating plugin scaffolding"

    def register_tools(self, registry: ToolRegistry) -> None:
        registry.register(
            "example",
            "echo",
            echo_tool,
            config={"message": "hello"},
            cost=0.1,
            latency=0.1,
            description="Echo the requested goal for testing",
        )


plugin = Plugin()
