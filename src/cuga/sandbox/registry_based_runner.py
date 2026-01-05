import yaml
from typing import Dict, Any, Optional

from .subprocess_runner import SubprocessSandboxRunner
from .base import SandboxRunner, SandboxExecutionResult

# The path to the central tool and policy registry.
REGISTRY_FILE_PATH = "registry.yaml"


class RegistryBasedRunner:
    """
    A runner that executes local tools based on policies defined in a central registry.
    """

    _instance = None
    _tools: Dict[str, Dict[str, Any]] = {}
    _policies: Dict[str, Dict[str, Any]] = {}
    _runners: Dict[str, SandboxRunner] = {}

    def __new__(cls):
        # Use a singleton pattern to ensure the registry is loaded only once.
        if cls._instance is None:
            cls._instance = super(RegistryBasedRunner, cls).__new__(cls)
            cls._instance._load_registry()
            cls._instance._register_runners()
        return cls._instance

    def _load_registry(self):
        """Loads and parses the local tools and sandbox policies from registry.yaml."""
        try:
            with open(REGISTRY_FILE_PATH, 'r') as f:
                registry = yaml.safe_load(f)

            if "local_tools" in registry:
                for tool in registry["local_tools"]:
                    self._tools[tool["id"]] = tool

            if "sandbox_policies" in registry:
                for policy in registry["sandbox_policies"]:
                    self._policies[policy["id"]] = policy

            print(
                f"--- Registry loaded: {len(self._tools)} local tools and {len(self._policies)} policies. ---"
            )

        except FileNotFoundError:
            print(f"Error: The registry file could not be found at '{REGISTRY_FILE_PATH}'.")
            raise
        except (yaml.YAMLError, KeyError) as e:
            print(f"Error: Failed to parse the registry file: {e}")
            raise

    def _register_runners(self):
        """Initializes and registers the available sandbox runner implementations."""
        self._runners["subprocess"] = SubprocessSandboxRunner()

    def run_tool(self, tool_id: str, command: str) -> SandboxExecutionResult:
        """
        Executes a command using the specified local tool and its associated sandbox policy.
        """
        tool = self._tools.get(tool_id)
        if not tool:
            return SandboxExecutionResult(
                output=None, error=f"Tool with ID '{tool_id}' not found in registry."
            )

        policy_id = tool.get("sandbox")
        if not policy_id:
            return SandboxExecutionResult(
                output=None, error=f"Tool '{tool_id}' does not have a sandbox policy."
            )

        policy = self._policies.get(policy_id)
        if not policy:
            return SandboxExecutionResult(output=None, error=f"Sandbox policy '{policy_id}' not found.")

        runner_type = policy.get("type")
        runner = self._runners.get(runner_type)
        if not runner:
            return SandboxExecutionResult(
                output=None, error=f"No runner registered for sandbox type '{runner_type}'."
            )

        print(f"--- Executing tool '{tool_id}' with sandbox '{policy_id}' ({runner_type}) ---")
        return runner.run(command, config=policy)
