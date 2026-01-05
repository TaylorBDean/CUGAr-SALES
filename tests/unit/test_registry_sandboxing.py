import unittest
import os
import sys

# Set PYTHONPATH to include the root directory for absolute imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from sandbox.registry_based_runner import RegistryBasedRunner


class TestRegistrySandboxing(unittest.TestCase):
    """
    Tests for the integrated, registry-based sandboxing system.
    """

    def setUp(self):
        """
        Initializes a fresh instance of the RegistryBasedRunner before each test.
        """
        # By creating a new instance, we re-trigger the singleton's loading logic.
        # This is important for ensuring a clean state for each test.
        RegistryBasedRunner._instance = None
        self.runner = RegistryBasedRunner()

    def test_registry_loading(self):
        """
        Test that the runner successfully loads tools and policies from registry.yaml.
        """
        self.assertIn("python_code_interpreter", self.runner._tools)
        self.assertIn("code-secure", self.runner._policies)
        self.assertEqual(len(self.runner._tools), 1)
        self.assertEqual(len(self.runner._policies), 1)

    def test_successful_execution(self):
        """
        Test a basic, successful execution of the python_code_interpreter.
        """
        result = self.runner.run_tool("python_code_interpreter", "print(2 + 2)")
        self.assertIsNone(result.error)
        self.assertEqual(result.output, "4")

    def test_runtime_error_capture(self):
        """
        Test that runtime errors within the sandboxed code are captured.
        """
        result = self.runner.run_tool("python_code_interpreter", "1 / 0")
        self.assertIsNotNone(result.error)
        self.assertNotEqual(result.error, "")

    def test_wall_clock_timeout(self):
        """
        Test that the wall-clock time limit is enforced, causing a timeout.
        """
        # We need to temporarily modify the policy for this test.
        self.runner._policies["code-secure"]["max_wall_clock_time"] = "1s"

        code = "import time; time.sleep(3)"
        result = self.runner.run_tool("python_code_interpreter", code)

        self.assertIsNotNone(result.error)
        self.assertNotEqual(result.error, "")

    def test_cpu_time_limit(self):
        """
        Test that the CPU time limit is enforced.
        Note: This is hard to test reliably in all environments, but a simple
        infinite loop should trigger it on most systems.
        """
        self.runner._policies["code-secure"]["max_cpu_time"] = "1s"

        code = "while True: pass"
        result = self.runner.run_tool("python_code_interpreter", code)

        self.assertIsNotNone(result.error)
        # The exact error message can vary depending on the OS.
        # The key is that an error was reported, indicating the process was terminated.
        self.assertNotEqual(result.error, "")

    def test_memory_limit(self):
        """
        Test that the memory limit is enforced, causing the process to be killed.
        """
        self.runner._policies["code-secure"]["max_memory"] = "10MB"

        # This code attempts to allocate a 20MB byte array.
        code = "mem_bomb = b'\\x00' * (20 * 1024 * 1024)"
        result = self.runner.run_tool("python_code_interpreter", code)

        self.assertIsNotNone(result.error)
        # A memory error in a subprocess often results in a non-zero exit code
        # but may not produce a clean error message. We check for a non-None error.
        self.assertNotEqual(result.error, "")

    def test_non_existent_tool(self):
        """
        Test that running a non-existent tool returns a clear error.
        """
        result = self.runner.run_tool("non_existent_tool", "print('hello')")
        self.assertIsNotNone(result.error)
        self.assertIn("not found in registry", result.error)

    def test_tool_with_no_sandbox(self):
        """
        Test that a tool without a sandbox policy returns an error.
        """
        # Manually add a bad tool to the in-memory registry for this test.
        self.runner._tools["bad_tool"] = {"id": "bad_tool", "name": "Bad Tool"}
        result = self.runner.run_tool("bad_tool", "print('hello')")
        self.assertIsNotNone(result.error)
        self.assertIn("does not have a sandbox policy", result.error)


if __name__ == '__main__':
    unittest.main()
