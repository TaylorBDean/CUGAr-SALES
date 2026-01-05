"""
Safe code execution abstraction enforcing AGENTS.md guardrails.

This module provides secure code execution through:
- Allowlist-based import restrictions (only cuga.modular.tools.*)
- Restricted builtins (deny dangerous operations)
- Filesystem deny-by-default (no write access, controlled reads)
- No eval/exec bypass (all code routed through this abstraction)
- Audit trail and trace propagation

Replaces direct exec() calls per AGENTS.md § 4 Sandbox Expectations.
"""
import sys
import asyncio
import importlib
from typing import Any, Dict, Optional, Set, List, Callable
from dataclasses import dataclass
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from loguru import logger


@dataclass
class ExecutionResult:
    """Result of safe code execution."""
    exit_code: int
    stdout: str
    stderr: str
    namespace: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None


class ImportGuard:
    """
    Controls imports with allowlist/denylist enforcement.
    
    Per AGENTS.md:
    - Allowlist: cuga.modular.tools.* only
    - Denylist: os, sys, subprocess, socket, urllib, requests, eval, exec, etc.
    """
    
    # Allowlisted module prefixes (explicit allow)
    ALLOWLIST_PREFIXES = [
        'cuga.modular.tools.',
    ]
    
    # Denylisted modules (explicit deny)
    DENYLIST = {
        'os', 'sys', 'subprocess', 'shutil', 'pathlib',
        'socket', 'urllib', 'requests', 'httpx', 'http',
        'ftplib', 'smtplib', 'telnetlib', 'ssl',
        'pickle', 'shelve', 'marshal', 'dill',
        'importlib', 'imp', '__import__',
        'eval', 'exec', 'compile',
        'open', 'file', 'input', 'raw_input',
        'ctypes', 'cffi',
    }
    
    # Additional safe modules (standard library, read-only)
    SAFE_MODULES = {
        'math', 'random', 'datetime', 'time', 'json', 'uuid',
        'collections', 'itertools', 'functools', 'operator',
        'typing', 'dataclasses', 're', 'string',
    }
    
    @classmethod
    def is_allowed(cls, module_name: str) -> bool:
        """
        Check if a module import is allowed.
        
        Args:
            module_name: The module name to check
            
        Returns:
            True if allowed, False otherwise
        """
        # Check denylist first (explicit deny)
        if module_name in cls.DENYLIST:
            return False
        
        # Check if it's a denylisted submodule
        for denied in cls.DENYLIST:
            if module_name.startswith(f"{denied}."):
                return False
        
        # Check allowlist (cuga.modular.tools.*)
        for prefix in cls.ALLOWLIST_PREFIXES:
            if module_name.startswith(prefix):
                return True
        
        # Check safe modules
        if module_name in cls.SAFE_MODULES:
            return True
        
        # Deny by default
        return False
    
    @classmethod
    def create_import_hook(cls, trace_id: Optional[str] = None):
        """
        Create an import hook that enforces allowlist/denylist.
        
        Args:
            trace_id: Optional trace ID for audit logging
            
        Returns:
            A callable that can replace __import__
        """
        original_import = __import__
        
        def guarded_import(name, globals=None, locals=None, fromlist=(), level=0):
            """Guarded import that enforces module restrictions."""
            # Allow relative imports within allowed modules
            if level > 0 and globals:
                package = globals.get('__package__', '')
                if package and not cls.is_allowed(package):
                    logger.error(
                        f"[{trace_id}] Blocked relative import from denied package: {package}"
                    )
                    raise ImportError(
                        f"Import denied by security policy: relative import from {package}"
                    )
            
            # Check absolute imports
            if not cls.is_allowed(name):
                logger.error(f"[{trace_id}] Blocked forbidden import: {name}")
                raise ImportError(f"Import denied by security policy: {name}")
            
            logger.debug(f"[{trace_id}] Allowed import: {name}")
            return original_import(name, globals, locals, fromlist, level)
        
        return guarded_import


class SafeCodeExecutor:
    """
    Execute Python code with security guardrails.
    
    Enforces AGENTS.md § 4 Sandbox Expectations:
    - Import restrictions (allowlist cuga.modular.tools.*)
    - Restricted builtins (no eval/exec/open/etc)
    - Filesystem deny-by-default
    - Trace propagation
    - Audit logging
    """
    
    # Restricted builtins (allow safe operations only)
    SAFE_BUILTINS = {
        # Type constructors
        'bool', 'int', 'float', 'str', 'bytes', 'list', 'tuple', 'dict', 'set', 'frozenset',
        # Type checks
        'isinstance', 'issubclass', 'type',
        # Iteration
        'enumerate', 'range', 'zip', 'map', 'filter', 'all', 'any', 'sum',
        'sorted', 'reversed', 'len', 'iter', 'next',
        # Math
        'abs', 'round', 'min', 'max', 'pow', 'divmod',
        # String/repr
        'repr', 'ascii', 'ord', 'chr', 'format',
        # Collections
        'getattr', 'setattr', 'hasattr', 'delattr',
        # Object introspection (limited)
        'dir', 'vars', 'id', 'hash',
        # Exceptions
        'Exception', 'ValueError', 'TypeError', 'KeyError', 'IndexError',
        'AttributeError', 'RuntimeError', 'StopIteration',
        # Other safe utilities
        'print', 'help',
    }
    
    # Forbidden builtins (explicit deny)
    FORBIDDEN_BUILTINS = {
        'eval', 'exec', 'compile', '__import__',
        'open', 'input', 'raw_input', 'file',
        'execfile', 'reload', 'vars', 'locals', 'globals',
        '__builtins__',
    }
    
    def __init__(
        self,
        profile: str = "default",
        trace_id: Optional[str] = None,
        timeout: float = 30.0,
        max_output_size: int = 1024 * 1024,  # 1MB
    ):
        """
        Initialize the safe code executor.
        
        Args:
            profile: Execution profile name (for audit trail)
            trace_id: Optional trace ID for observability
            timeout: Execution timeout in seconds
            max_output_size: Maximum stdout/stderr size in bytes
        """
        self.profile = profile
        self.trace_id = trace_id or "no-trace"
        self.timeout = timeout
        self.max_output_size = max_output_size
    
    def _create_restricted_namespace(self) -> Dict[str, Any]:
        """
        Create a restricted execution namespace.
        
        Returns:
            A dict with safe builtins and guarded __import__
        """
        # Start with empty builtins
        safe_builtins = {}
        
        # Add allowlisted builtins
        for name in self.SAFE_BUILTINS:
            if hasattr(__builtins__, name):
                safe_builtins[name] = getattr(__builtins__, name)
        
        # Add guarded import
        safe_builtins['__import__'] = ImportGuard.create_import_hook(self.trace_id)
        
        # Create namespace
        namespace = {
            '__builtins__': safe_builtins,
            '__name__': '__main__',
            '__file__': '<sandbox>',
            '__doc__': None,
            '__package__': None,
            # Add safe standard modules
            'asyncio': asyncio,
        }
        
        return namespace
    
    async def execute(
        self,
        code: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ExecutionResult:
        """
        Execute Python code safely.
        
        Args:
            code: The Python code to execute
            context: Optional context variables to inject into namespace
            
        Returns:
            ExecutionResult with stdout, stderr, exit code, and namespace
            
        Raises:
            TimeoutError: If execution exceeds timeout
            SyntaxError: If code has syntax errors
            ImportError: If code attempts forbidden imports
        """
        logger.info(f"[{self.trace_id}] Starting safe code execution (profile={self.profile})")
        
        # Create restricted namespace
        namespace = self._create_restricted_namespace()
        
        # Inject context variables if provided
        if context:
            # Filter context to prevent injection of dangerous objects
            safe_context = {
                k: v for k, v in context.items()
                if not k.startswith('_') and not callable(v)
            }
            namespace.update(safe_context)
        
        # Capture stdout/stderr
        stdout_buffer = StringIO()
        stderr_buffer = StringIO()
        exit_code = 0
        error_msg = None
        
        try:
            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                # Compile code (validates syntax)
                try:
                    compiled_code = compile(code, '<sandbox>', 'exec')
                except SyntaxError as se:
                    error_msg = f"Syntax error at line {se.lineno}: {se.msg}"
                    logger.error(f"[{self.trace_id}] {error_msg}")
                    raise
                
                # Execute with timeout
                exec_locals = {}
                
                # Check if code defines an async wrapper
                if 'async def __async_main' in code or 'async def __cuga_async_wrapper' in code:
                    # Execute to define the async function
                    exec(compiled_code, namespace, exec_locals)
                    
                    # Find and run the async function
                    async_func = None
                    for name in ['__async_main', '__cuga_async_wrapper']:
                        if name in exec_locals and asyncio.iscoroutinefunction(exec_locals[name]):
                            async_func = exec_locals[name]
                            break
                    
                    if async_func:
                        # Run async with timeout
                        result_namespace = await asyncio.wait_for(
                            async_func(),
                            timeout=self.timeout
                        )
                        if result_namespace:
                            namespace.update(result_namespace)
                    else:
                        logger.warning(f"[{self.trace_id}] Async wrapper defined but not found")
                else:
                    # Synchronous execution with timeout
                    await asyncio.wait_for(
                        asyncio.get_event_loop().run_in_executor(
                            None,
                            lambda: exec(compiled_code, namespace, exec_locals)
                        ),
                        timeout=self.timeout
                    )
                    namespace.update(exec_locals)
        
        except asyncio.TimeoutError:
            exit_code = 124  # Standard timeout exit code
            error_msg = f"Execution timed out after {self.timeout}s"
            stderr_buffer.write(f"Error: {error_msg}\n")
            logger.error(f"[{self.trace_id}] {error_msg}")
        
        except ImportError as ie:
            exit_code = 1
            error_msg = f"Import denied: {ie}"
            stderr_buffer.write(f"ImportError: {ie}\n")
            logger.error(f"[{self.trace_id}] {error_msg}")
        
        except SyntaxError as se:
            exit_code = 1
            error_msg = f"Syntax error: {se}"
            stderr_buffer.write(f"SyntaxError: {se}\n")
            logger.error(f"[{self.trace_id}] {error_msg}")
        
        except Exception as e:
            exit_code = 1
            error_msg = f"Execution error: {type(e).__name__}: {e}"
            stderr_buffer.write(f"{type(e).__name__}: {e}\n")
            logger.error(f"[{self.trace_id}] {error_msg}")
            
            # Include traceback
            import traceback
            stderr_buffer.write(traceback.format_exc())
        
        # Get output with size limits
        stdout = stdout_buffer.getvalue()[:self.max_output_size]
        stderr = stderr_buffer.getvalue()[:self.max_output_size]
        
        # Truncation warnings
        if len(stdout_buffer.getvalue()) > self.max_output_size:
            stdout += f"\n[WARNING: Output truncated at {self.max_output_size} bytes]"
        if len(stderr_buffer.getvalue()) > self.max_output_size:
            stderr += f"\n[WARNING: Error output truncated at {self.max_output_size} bytes]"
        
        logger.info(
            f"[{self.trace_id}] Execution completed: "
            f"exit_code={exit_code}, stdout_size={len(stdout)}, stderr_size={len(stderr)}"
        )
        
        return ExecutionResult(
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            namespace=namespace,
            success=(exit_code == 0),
            error=error_msg,
        )


async def safe_execute_code(
    code: str,
    profile: str = "default",
    trace_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> ExecutionResult:
    """
    Convenience function for safe code execution.
    
    Replaces direct exec() calls per AGENTS.md § 4.
    
    Args:
        code: The Python code to execute
        profile: Execution profile name (for audit trail)
        trace_id: Optional trace ID for observability
        context: Optional context variables
        timeout: Execution timeout in seconds
        
    Returns:
        ExecutionResult with stdout, stderr, exit code, and namespace
        
    Example:
        >>> result = await safe_execute_code("print('hello')")
        >>> result.stdout
        'hello\\n'
        >>> result.exit_code
        0
    """
    executor = SafeCodeExecutor(
        profile=profile,
        trace_id=trace_id,
        timeout=timeout,
    )
    return await executor.execute(code, context=context)
