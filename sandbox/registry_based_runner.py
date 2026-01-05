import yaml
from typing import Dict, Any, Optional

from sandbox.subprocess_runner import SubprocessSandboxRunner
from sandbox.base import SandboxRunner, SandboxExecutionResult

# The path to the central tool and policy registry.
REGISTRY_FILE_PATH = "registry.yaml"


class RegistryBasedRunner:
    """
    A runner that executes local tools based on policies defined in a central registry.

    This class acts as a dispatcher. It reads the `registry.yaml` file to
    understand which local tools are available and which sandbox policies they
    are associated with. When asked to run a tool, it instantiates the
    appropriate sandbox runner (e.g., SubprocessSandboxRunner) with the correct
    configuration and executes the command.
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

            # Index tools by their ID for quick lookup.
            if "local_tools" in registry:
                for tool in registry["local_tools"]:
                    self._tools[tool["id"]] = tool

            # Index policies by their ID for quick lookup.
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
        # In the future, other runner types (e.g., 'container', 'in_process') could be added here.

    def run_tool(self, tool_id: str, command: str) -> SandboxExecutionResult:
        """
        Executes a command using the specified local tool and its associated sandbox policy.

        Args:
            tool_id: The ID of the local tool to run (e.g., 'python_code_interpreter').
            command: The command or code to execute.

        Returns:
            A SandboxExecutionResult object with the outcome of the execution.
        """
        # 1. Find the tool in the registry.
        tool = self._tools.get(tool_id)
        if not tool:
            return SandboxExecutionResult(
                output=None, error=f"Tool with ID '{tool_id}' not found in registry."
            )

        # 2. Find the associated sandbox policy.
        policy_id = tool.get("sandbox")
        if not policy_id:
            return SandboxExecutionResult(
                output=None, error=f"Tool '{tool_id}' does not have a sandbox policy."
            )

        policy = self._policies.get(policy_id)
        if not policy:
            return SandboxExecutionResult(output=None, error=f"Sandbox policy '{policy_id}' not found.")

        # 3. Get the appropriate runner for the policy type.
        runner_type = policy.get("type")
        runner = self._runners.get(runner_type)
        if not runner:
            return SandboxExecutionResult(
                output=None, error=f"No runner registered for sandbox type '{runner_type}'."
            )

        # 4. Execute the command with the runner and the policy config.
        print(f"--- Executing tool '{tool_id}' with sandbox '{policy_id}' ({runner_type}) ---")
        return runner.run(command, config=policy)
