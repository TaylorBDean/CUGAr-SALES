from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import uuid

from cuga.memory.in_memory_store import InMemoryMemoryStore
from cuga.sandbox.registry_based_runner import RegistryBasedRunner


@dataclass
class AgentConfig:
    """
    A placeholder for agent configuration.
    """

    llm: str = "gpt-4"


@dataclass
class AgentResult:
    """
    A structured result object for the `run_agent` function.
    """

    output: str
    session_id: str
    intermediate_steps: list = field(default_factory=list)
    error: Optional[str] = None


def run_agent(
    input_text: str,
    session_id: str,
    user_id: Optional[str] = None,
    config: Optional[AgentConfig] = None,
    memory_store: Optional[InMemoryMemoryStore] = None,
    tool_runner: Optional[RegistryBasedRunner] = None,
) -> AgentResult:
    """
    The primary, stateful entrypoint for the agent system.
    """
    # Use default instances if none are provided.
    config = config or AgentConfig()
    memory_store = memory_store or InMemoryMemoryStore()
    tool_runner = tool_runner or RegistryBasedRunner()

    # 1. Load state from MemoryStore
    session_state = memory_store.load_session_state(session_id) or {"history": []}

    final_output = ""
    intermediate_steps = []
    error = None

    try:
        # Simple "Planner" logic
        if "print(" in input_text or "+" in input_text or "import" in input_text:
            tool_id = "python_code_interpreter"
            command = input_text

            # "Tool Executor" logic
            execution_result = tool_runner.run_tool(tool_id, command)

            step = {"tool": tool_id, "command": command, "result": execution_result}
            intermediate_steps.append(step)

            if execution_result.error:
                final_output = f"An error occurred: {execution_result.error}"
                error = execution_result.error
            else:
                final_output = f"Execution result: {execution_result.output}"
        else:
            final_output = f"Echo: {input_text}"

    except Exception as e:
        error = f"An unexpected error occurred in the agent: {e}"
        final_output = error

    # 3. Update memory
    session_state["history"].append({"input": input_text, "output": final_output})
    memory_store.save_session_state(session_id, session_state)

    # 4. Return structured result
    return AgentResult(
        output=final_output,
        intermediate_steps=intermediate_steps,
        session_id=session_id,
        error=error,
    )
