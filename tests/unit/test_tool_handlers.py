"""
tests/unit/test_tool_handlers.py

Comprehensive tests for tool handler execution patterns per AGENTS.md § Tool Contract.
Tests handler signatures, parameter validation, context usage, error handling,
and guardrails compliance (allowlist enforcement, budget constraints).

Target: 80%+ coverage of tool handler execution patterns

Test Strategy:
- Test handler signature compliance (inputs, context, return value)
- Test parameter validation and type checking
- Test context usage (profile, trace_id propagation)
- Test error handling (missing params, invalid types, handler exceptions)
- Test allowlist enforcement (reject non-cuga.modular.tools.* imports)
- Test budget guard integration (per-tool cost tracking)
"""

import pytest
from typing import Dict, Any
from unittest.mock import Mock, patch

from cuga.modular.tools import ToolSpec, ToolRegistry, _load_handler, Handler


# ============================================================================
# Test Handler Implementations
# ============================================================================


def valid_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Valid handler following canonical signature."""
    text = inputs.get("text", "default")
    trace_id = context.get("trace_id", "unknown")
    return f"Processed: {text} (trace: {trace_id})"


def error_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> str:
    """Handler that raises exceptions."""
    if inputs.get("fail"):
        raise ValueError("Intentional failure")
    return "success"


def context_aware_handler(inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """Handler that uses context extensively."""
    return {
        "input": inputs,
        "profile": context.get("profile"),
        "trace_id": context.get("trace_id"),
        "executed": True,
    }


# ============================================================================
# Tests: Handler Signature Compliance
# ============================================================================


class TestHandlerSignature:
    """Test that handlers follow canonical signature."""
    
    def test_handler_accepts_inputs_and_context(self):
        """Handler must accept (inputs: Dict, context: Dict)."""
        tool = ToolSpec(
            name="test",
            description="Test tool",
            handler=valid_handler,
        )
        
        inputs = {"text": "hello"}
        context = {"trace_id": "test-123"}
        
        result = tool.handler(inputs, context)
        assert result == "Processed: hello (trace: test-123)"
    
    def test_handler_returns_value(self):
        """Handler must return a value (Any type)."""
        tool = ToolSpec(
            name="test",
            description="Test tool",
            handler=valid_handler,
        )
        
        result = tool.handler({}, {})
        assert result is not None
        assert isinstance(result, str)
    
    def test_handler_can_return_dict(self):
        """Handler can return dict for structured results."""
        tool = ToolSpec(
            name="test",
            description="Test tool",
            handler=context_aware_handler,
        )
        
        result = tool.handler({"key": "value"}, {"profile": "test"})
        assert isinstance(result, dict)
        assert result["executed"] is True
        assert result["profile"] == "test"


# ============================================================================
# Tests: Parameter Validation
# ============================================================================


class TestParameterValidation:
    """Test parameter validation and type checking."""
    
    def test_handler_validates_required_params(self):
        """Handler should validate required parameters."""
        def strict_handler(inputs: Dict, context: Dict) -> str:
            if "required_field" not in inputs:
                raise ValueError("Missing required_field")
            return inputs["required_field"]
        
        tool = ToolSpec(
            name="strict",
            description="Strict validation",
            handler=strict_handler,
        )
        
        # Missing required param raises error
        with pytest.raises(ValueError, match="Missing required_field"):
            tool.handler({}, {})
        
        # Valid param succeeds
        result = tool.handler({"required_field": "value"}, {})
        assert result == "value"
    
    def test_handler_validates_param_types(self):
        """Handler should validate parameter types."""
        def typed_handler(inputs: Dict, context: Dict) -> int:
            count = inputs.get("count")
            if not isinstance(count, int):
                raise TypeError(f"count must be int, got {type(count)}")
            return count * 2
        
        tool = ToolSpec(
            name="typed",
            description="Type checking",
            handler=typed_handler,
        )
        
        # Wrong type raises error
        with pytest.raises(TypeError, match="count must be int"):
            tool.handler({"count": "not an int"}, {})
        
        # Correct type succeeds
        result = tool.handler({"count": 5}, {})
        assert result == 10
    
    def test_handler_provides_defaults(self):
        """Handler should provide sensible defaults for optional params."""
        def default_handler(inputs: Dict, context: Dict) -> str:
            text = inputs.get("text", "default text")
            mode = inputs.get("mode", "standard")
            return f"{mode}: {text}"
        
        tool = ToolSpec(
            name="defaults",
            description="Default values",
            handler=default_handler,
        )
        
        # No params uses defaults
        result = tool.handler({}, {})
        assert result == "standard: default text"
        
        # Partial params uses some defaults
        result = tool.handler({"text": "custom"}, {})
        assert result == "standard: custom"
        
        # All params provided
        result = tool.handler({"text": "custom", "mode": "advanced"}, {})
        assert result == "advanced: custom"


# ============================================================================
# Tests: Context Usage
# ============================================================================


class TestContextUsage:
    """Test that handlers properly use context."""
    
    def test_handler_accesses_trace_id(self):
        """Handler should propagate trace_id from context."""
        def trace_handler(inputs: Dict, context: Dict) -> str:
            trace_id = context.get("trace_id", "no-trace")
            return f"trace:{trace_id}"
        
        tool = ToolSpec(
            name="trace",
            description="Trace propagation",
            handler=trace_handler,
        )
        
        result = tool.handler({}, {"trace_id": "abc-123"})
        assert result == "trace:abc-123"
    
    def test_handler_accesses_profile(self):
        """Handler should access profile from context."""
        def profile_handler(inputs: Dict, context: Dict) -> str:
            profile = context.get("profile", "default")
            return f"profile:{profile}"
        
        tool = ToolSpec(
            name="profile",
            description="Profile access",
            handler=profile_handler,
        )
        
        result = tool.handler({}, {"profile": "dev"})
        assert result == "profile:dev"
    
    def test_handler_combines_inputs_and_context(self):
        """Handler should combine inputs and context effectively."""
        tool = ToolSpec(
            name="combined",
            description="Input+context",
            handler=context_aware_handler,
        )
        
        inputs = {"query": "test"}
        context = {"profile": "test_profile", "trace_id": "trace-456"}
        
        result = tool.handler(inputs, context)
        assert result["input"] == inputs
        assert result["profile"] == "test_profile"
        assert result["trace_id"] == "trace-456"


# ============================================================================
# Tests: Error Handling
# ============================================================================


class TestErrorHandling:
    """Test handler error handling patterns."""
    
    def test_handler_raises_on_invalid_input(self):
        """Handler should raise clear errors for invalid inputs."""
        tool = ToolSpec(
            name="error",
            description="Error handling",
            handler=error_handler,
        )
        
        # Valid input succeeds
        result = tool.handler({"fail": False}, {})
        assert result == "success"
        
        # Invalid input raises error
        with pytest.raises(ValueError, match="Intentional failure"):
            tool.handler({"fail": True}, {})
    
    def test_registry_handles_missing_tool(self):
        """Registry should return None for missing tools."""
        registry = ToolRegistry()
        
        tool = registry.get("nonexistent")
        assert tool is None
    
    def test_handler_exception_propagates(self):
        """Handler exceptions should propagate to caller."""
        def buggy_handler(inputs: Dict, context: Dict) -> str:
            # Simulates a bug in handler logic
            return inputs["missing_key"]  # KeyError
        
        tool = ToolSpec(
            name="buggy",
            description="Buggy handler",
            handler=buggy_handler,
        )
        
        with pytest.raises(KeyError):
            tool.handler({}, {})


# ============================================================================
# Tests: Allowlist Enforcement
# ============================================================================


class TestAllowlistEnforcement:
    """Test that dynamic imports are restricted to allowlist."""
    
    def test_load_handler_accepts_allowlisted_module(self):
        """_load_handler should accept cuga.modular.tools.* modules."""
        # Mock the module to avoid actual import
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.run = lambda inputs, ctx: "result"
            mock_import.return_value = mock_module
            
            handler = _load_handler("cuga.modular.tools.echo.run")
            assert callable(handler)
            assert handler({}, {}) == "result"
    
    def test_load_handler_rejects_non_allowlisted_module(self):
        """_load_handler should reject modules outside allowlist."""
        with pytest.raises(ImportError, match="restricted to cuga.modular.tools"):
            _load_handler("os.system")  # Dangerous!
        
        with pytest.raises(ImportError, match="restricted to cuga.modular.tools"):
            _load_handler("subprocess.run")  # Dangerous!
        
        with pytest.raises(ImportError, match="restricted to cuga.modular.tools"):
            _load_handler("cuga.backend.tools.something")  # Wrong namespace
    
    def test_load_handler_validates_module_path_format(self):
        """_load_handler should validate module path format."""
        # Valid prefix but missing attribute after last dot
        # This will fail allowlist check because "cuga.modular.tools" doesn't end with "."
        with pytest.raises(ImportError, match="restricted to cuga.modular.tools"):
            _load_handler("cuga.modular.tools")  # No dot after tools, fails allowlist
        
        # Valid prefix with trailing dot (passes allowlist, fails format check)
        with pytest.raises(ImportError, match="must include attribute"):
            _load_handler("cuga.modular.tools.")  # Trailing dot, no attribute
    
    def test_load_handler_validates_attribute_exists(self):
        """_load_handler should check that attribute exists."""
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock(spec=[])  # Empty spec = no attributes
            mock_import.return_value = mock_module
            
            with pytest.raises(ImportError, match="missing attribute"):
                _load_handler("cuga.modular.tools.echo.nonexistent")
    
    def test_load_handler_validates_attribute_callable(self):
        """_load_handler should check that attribute is callable."""
        with patch("importlib.import_module") as mock_import:
            mock_module = Mock()
            mock_module.NOT_CALLABLE = "I'm a string, not a function"
            mock_import.return_value = mock_module
            
            with pytest.raises(ImportError, match="not callable"):
                _load_handler("cuga.modular.tools.echo.NOT_CALLABLE")


# ============================================================================
# Tests: Registry Integration
# ============================================================================


class TestRegistryIntegration:
    """Test ToolSpec integration with ToolRegistry."""
    
    def test_registry_stores_tools(self):
        """Registry should store and retrieve tools."""
        tool1 = ToolSpec(name="tool1", description="First", handler=valid_handler)
        tool2 = ToolSpec(name="tool2", description="Second", handler=error_handler)
        
        registry = ToolRegistry(tools=[tool1, tool2])
        
        assert len(registry.tools) == 2
        assert registry.get("tool1") == tool1
        assert registry.get("tool2") == tool2
    
    def test_registry_register_adds_tool(self):
        """Registry.register should add tools dynamically."""
        registry = ToolRegistry()
        
        tool = ToolSpec(name="new_tool", description="New", handler=valid_handler)
        registry.register(tool)
        
        assert len(registry.tools) == 1
        assert registry.get("new_tool") == tool
    
    def test_registry_from_config_loads_handlers(self):
        """Registry.from_config should load handlers dynamically."""
        with patch("cuga.modular.tools._load_handler") as mock_load:
            mock_load.return_value = valid_handler
            
            config = [
                {
                    "name": "echo",
                    "description": "Echo tool",
                    "module": "cuga.modular.tools.echo.run",
                    "parameters": {"text": {"type": "string"}},
                },
            ]
            
            registry = ToolRegistry.from_config(config)
            
            assert len(registry.tools) == 1
            tool = registry.get("echo")
            assert tool.name == "echo"
            assert tool.description == "Echo tool"
            assert tool.parameters == {"text": {"type": "string"}}
            mock_load.assert_called_once_with("cuga.modular.tools.echo.run")
    
    def test_registry_from_config_handles_missing_handler(self):
        """Registry.from_config should provide fallback for missing handlers."""
        config = [
            {
                "name": "no_handler",
                "description": "No handler specified",
                # No "module" key -> should use fallback
            },
        ]
        
        registry = ToolRegistry.from_config(config)
        
        assert len(registry.tools) == 1
        tool = registry.get("no_handler")
        # Fallback handler should echo inputs
        result = tool.handler({"test": "value"}, {})
        assert result == {"test": "value"}
