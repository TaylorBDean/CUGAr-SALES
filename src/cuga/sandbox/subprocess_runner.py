import subprocess
import os
import sys
import resource
import time
import signal
from typing import Any, Dict, Optional

from .base import SandboxRunner, SandboxExecutionResult


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
    """

    def _set_resource_limits(self, config: Dict[str, Any]):
        """
        Sets resource limits for the current process.
        """
        # Set CPU time limit
        cpu_time_limit = parse_time_limit(config.get("max_cpu_time"))
        if cpu_time_limit is not None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_time_limit, cpu_time_limit))

        # Set memory limit
        memory_limit = parse_memory_limit(config.get("max_memory"))
        if memory_limit is not None:
            resource.setrlimit(resource.RLIMIT_AS, (memory_limit, memory_limit))

    def run(self, command: str, config: Dict[str, Any]) -> SandboxExecutionResult:
        """
        Executes a string of Python code in an isolated subprocess with resource limits.
        """
        start_time = time.time()
        error_message = None

        try:
            proc = subprocess.Popen(
                [sys.executable, "-c", command],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=lambda: self._set_resource_limits(config),
                text=True,
                encoding='utf-8',
            )

            wall_clock_limit = parse_time_limit(config.get("max_wall_clock_time"))

            try:
                stdout, stderr = proc.communicate(timeout=wall_clock_limit)
            except subprocess.TimeoutExpired:
                proc.kill()
                stdout, stderr = proc.communicate()
                error_message = f"Execution timed out after {wall_clock_limit} seconds."

            if proc.returncode != 0:
                if stderr:
                    error_message = stderr.strip()
                elif proc.returncode != 0 and not error_message:
                    error_message = f"Process exited with non-zero code: {proc.returncode}"

            output = stdout.strip() if stdout else None

        except Exception as e:
            error_message = f"Failed to execute sandboxed code: {type(e).__name__}: {e}"
            output = None

        wall_clock_time = time.time() - start_time

        return SandboxExecutionResult(
            output=output,
            error=error_message,
            resource_usage={'wall_clock_time_s': round(wall_clock_time, 4)},
        )
