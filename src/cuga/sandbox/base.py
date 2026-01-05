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
    """

    @abstractmethod
    def run(self, command: Any, config: Dict[str, Any]) -> SandboxExecutionResult:
        """
        Executes a command in the sandbox.
        """
        ...
