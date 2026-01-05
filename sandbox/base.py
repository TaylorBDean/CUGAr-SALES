from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class SandboxExecutionResult:
    """
    A data class to hold the results of a sandboxed execution.
    """

    def __init__(
        self, output: Any, error: Optional[str] = None, resource_usage: Optional[Dict[str, Any]] = None
    ):
        self.output = output
        self.error = error
        self.resource_usage = resource_usage or {}

    def __repr__(self) -> str:
        return f"SandboxExecutionResult(output={self.output}, error={self.error})"


class SandboxRunner(ABC):
    """
    Abstract base class for a sandbox runner.

    This interface defines the contract for executing code or commands in a
    sandboxed environment with resource and policy constraints.
    """

    @abstractmethod
    def run(self, command: Any, config: Dict[str, Any]) -> SandboxExecutionResult:
        """
        Executes a command in the sandbox.

        Args:
            command: The code or command to execute. The type will vary
                     depending on the sandbox implementation (e.g., a string
                     of Python code, a dictionary for an HTTP request).
            config: A dictionary of configuration options for this execution,
                    often derived from the sandbox policy in tools.yaml
                    (e.g., resource limits, allowed imports).

        Returns:
            A SandboxExecutionResult object containing the output, any errors,
            and resource usage information.
        """
        ...
