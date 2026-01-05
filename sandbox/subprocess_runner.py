import subprocess
import os
import sys
import resource
import time
from typing import Any, Dict, Optional

from sandbox.base import SandboxRunner, SandboxExecutionResult


# A helper function to parse memory strings like "128MB" or "1GB" into bytes.
def parse_memory_limit(mem_str: Optional[str]) -> Optional[int]:
    if not mem_str:
        return None
    mem_str = mem_str.upper()
    if mem_str.endswith("MB"):
        return int(mem_str[:-2]) * 1024 * 1024
    elif mem_str.endswith("GB"):
        return int(mem_str[:-2]) * 1024 * 1024 * 1024
    return int(mem_str)


# A helper function to parse time strings like "5s" into seconds.
def parse_time_limit(time_str: Optional[str]) -> Optional[int]:
    if not time_str:
        return None
    if time_str.endswith("s"):
        return int(time_str[:-1])
    return int(time_str)


class SubprocessSandboxRunner(SandboxRunner):
    """
    A sandbox runner that executes Python code in an isolated subprocess.

    This implementation provides a higher level of security and resource control
    than the in-process runner by leveraging OS-level process isolation.
    It uses the `resource` module to set hard limits on CPU time and memory
    usage for the child process, making it resistant to resource exhaustion attacks.
    """

    def _set_resource_limits(self, config: Dict[str, Any]):
        """
        Sets resource limits for the current process. This function is intended
        to be called in the child process right before exec.

        NOTE: Using `preexec_fn` is not safe in the presence of threads in the
        parent process, but it is a standard way to achieve this kind of
        sandboxing. For this application, we assume a controlled environment.
        """
        # Set CPU time limit
        cpu_time_limit = parse_time_limit(config.get("max_cpu_time"))
        if cpu_time_limit is not None:
            # RLIMIT_CPU is the total CPU time in seconds
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_time_limit, cpu_time_limit))

        # Set memory limit
        memory_limit = parse_memory_limit(config.get("max_memory"))
        if memory_limit is not None:
            # RLIMIT_AS is the total virtual memory
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))

    def run(self, command: str, config: Dict[str, Any]) -> SandboxExecutionResult:
        """
        Executes a string of Python code in an isolated subprocess with resource limits.

        Args:
            command: The string of Python code to execute.
            config: A dictionary of configuration options, including resource limits
                    like `max_cpu_time`, `max_memory`, and `max_wall_clock_time`.

        Returns:
            A SandboxExecutionResult object.
        """
        start_time = time.time()
        error_message = None

        try:
            # The `subprocess.Popen` call executes the command.
            # `preexec_fn` is used to run `_set_resource_limits` in the child
            # process after it's forked but before the new program is executed.
            proc = subprocess.Popen(
                [sys.executable, "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=lambda: self._set_resource_limits(config),
                text=True,
                encoding='utf-8',
            )

            # Enforce the wall-clock time limit.
            wall_clock_limit = parse_time_limit(config.get("max_wall_clock_time"))

            try:
                stdout, stderr = proc.communicate(timeout=wall_clock_limit)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                error_message = f"Execution timed out after {wall_clock_limit} seconds."

            # Check the return code and stderr for errors.
            if proc.returncode != 0:
                if stderr:
                    error_message = stderr.strip()
                # A non-zero exit code might be due to resource limits being exceeded.
                elif proc.returncode != 0 and not error_message:
                    error_message = f"Process exited with non-zero code: {proc.returncode}"

            output = stdout.strip() if stdout else None

        except Exception as e:
            # Catch any other unexpected errors during process creation.
            error_message = f"Failed to execute sandboxed code: {type(e).__name__}: {e}"
            output = None

        wall_clock_time = time.time() - start_time

        return SandboxExecutionResult(
            output=output,
            error=error_message,
            resource_usage={'wall_clock_time_s': round(wall_clock_time, 4)},
        )
