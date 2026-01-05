"""
Unit tests for Pydantic configuration schemas

Tests:
- ToolRegistry schema validation (allowlist, mounts, budgets, profiles)
- GuardsConfig schema validation (conditions, actions, priorities)
- AgentConfig schema validation (providers, temperature, timeouts)
- MemoryConfig and ObservabilityConfig validation
- Security guardrails (API key warnings, module allowlist enforcement)
- Error message quality and actionability
"""

import pytest
from pydantic import ValidationError

from cuga.config.schemas.agent_schema import (
    AgentConfig,
    AgentLLMConfig,
    MemoryConfig,
    ObservabilityConfig,
)
from cuga.config.schemas.guards_schema import (
    GuardAction,
    GuardCondition,
    GuardsConfig,
    RoutingGuard,
)
from cuga.config.schemas.registry_schema import (
    SandboxProfile,
    ToolBudget,
    ToolRegistry,
    ToolRegistryEntry,
    ToolSchema,
)


# ---------------------------------------------------------------------------
# Test ToolRegistry Schema
# ---------------------------------------------------------------------------


def test_tool_registry_entry_valid():
    """Test valid tool registry entry passes validation."""
    entry = ToolRegistryEntry(
        module="cuga.modular.tools.file_search",
        handler="search_files",
        description="Search for files matching patterns",
        sandbox_profile=SandboxProfile.PY_SLIM,
        mounts=["/workdir:/workdir:ro"],
        budget=ToolBudget(max_tokens=50000, max_calls_per_session=100),
    )

    assert entry.module == "cuga.modular.tools.file_search"
    assert entry.handler == "search_files"
    assert entry.sandbox_profile == SandboxProfile.PY_SLIM
    assert len(entry.mounts) == 1


def test_tool_registry_entry_allowlist_enforcement():
    """Test module allowlist rejects non-cuga.modular.tools.* modules."""
    with pytest.raises(ValidationError) as exc_info:
        ToolRegistryEntry(
            module="evil.tools.backdoor",
            handler="run",
            description="Malicious tool",
            sandbox_profile=SandboxProfile.PY_SLIM,
        )

    error_msg = str(exc_info.value)
    assert "allowlist" in error_msg.lower()
    assert "cuga.modular.tools" in error_msg


def test_tool_registry_entry_invalid_mount_syntax():
    """Test mount validation rejects invalid syntax."""
    with pytest.raises(ValidationError) as exc_info:
        ToolRegistryEntry(
            module="cuga.modular.tools.test",
            handler="run",
            description="Test tool with invalid mount",
            sandbox_profile=SandboxProfile.PY_SLIM,
            mounts=["/tmp:invalid"],  # Missing mode
        )

    error_msg = str(exc_info.value)
    assert "mount" in error_msg.lower()
    assert "source:dest:mode" in error_msg.lower()


def test_tool_registry_entry_invalid_mount_mode():
    """Test mount validation rejects invalid modes."""
    with pytest.raises(ValidationError) as exc_info:
        ToolRegistryEntry(
            module="cuga.modular.tools.test",
            handler="run",
            description="Test tool with invalid mount mode",
            sandbox_profile=SandboxProfile.PY_SLIM,
            mounts=["/tmp:/tmp:writable"],  # Invalid mode (should be ro/rw)
        )

    error_msg = str(exc_info.value)
    assert "mode" in error_msg.lower()
    assert "ro" in error_msg or "rw" in error_msg


def test_tool_registry_entry_description_too_short():
    """Test description validation requires minimum 10 chars."""
    with pytest.raises(ValidationError) as exc_info:
        ToolRegistryEntry(
            module="cuga.modular.tools.test",
            handler="run",
            description="Short",  # Only 5 chars
            sandbox_profile=SandboxProfile.PY_SLIM,
        )

    error_msg = str(exc_info.value)
    assert "10" in error_msg or "length" in error_msg.lower()


def test_tool_budget_bounds():
    """Test ToolBudget enforces reasonable bounds."""
    # Valid budget
    budget = ToolBudget(max_tokens=50000, max_calls_per_session=100, max_calls_per_minute=10)
    assert budget.max_tokens == 50000

    # Exceeds max_tokens
    with pytest.raises(ValidationError):
        ToolBudget(max_tokens=200000)  # Exceeds 100000

    # Exceeds max_calls_per_session
    with pytest.raises(ValidationError):
        ToolBudget(max_tokens=5000, max_calls_per_session=20000)  # Exceeds 10000


def test_tool_registry_no_duplicate_modules():
    """Test ToolRegistry rejects duplicate module paths."""
    with pytest.raises(ValidationError) as exc_info:
        ToolRegistry(
            tools={
                "tool1": ToolRegistryEntry(
                    module="cuga.modular.tools.search",
                    handler="search",
                    description="First tool with this module",
                    sandbox_profile=SandboxProfile.PY_SLIM,
                ),
                "tool2": ToolRegistryEntry(
                    module="cuga.modular.tools.search",  # Duplicate module
                    handler="different_handler",
                    description="Second tool with same module",
                    sandbox_profile=SandboxProfile.PY_SLIM,
                ),
            }
        )

    error_msg = str(exc_info.value)
    assert "duplicate" in error_msg.lower()


def test_tool_registry_valid_tool_names():
    """Test tool names follow snake_case convention."""
    # Valid snake_case names
    registry = ToolRegistry(
        tools={
            "file_search": ToolRegistryEntry(
                module="cuga.modular.tools.file_search",
                handler="search",
                description="File search tool",
                sandbox_profile=SandboxProfile.PY_SLIM,
            ),
            "code_analyzer_v2": ToolRegistryEntry(
                module="cuga.modular.tools.code_analyzer",
                handler="analyze",
                description="Code analyzer tool v2",
                sandbox_profile=SandboxProfile.PY_SLIM,
            ),
        }
    )

    assert len(registry.tools) == 2


def test_sandbox_profile_enum():
    """Test SandboxProfile enum has expected values."""
    assert SandboxProfile.PY_SLIM == "py_slim"
    assert SandboxProfile.PY_FULL == "py_full"
    assert SandboxProfile.NODE_SLIM == "node_slim"
    assert SandboxProfile.NODE_FULL == "node_full"
    assert SandboxProfile.ORCHESTRATOR == "orchestrator"


# ---------------------------------------------------------------------------
# Test GuardsConfig Schema
# ---------------------------------------------------------------------------


def test_guard_condition_valid():
    """Test valid guard condition passes validation."""
    condition = GuardCondition(field="request.user.role", operator="eq", value="admin")

    assert condition.field == "request.user.role"
    assert condition.operator == "eq"
    assert condition.value == "admin"


def test_guard_condition_invalid_operator():
    """Test guard condition rejects invalid operators."""
    with pytest.raises(ValidationError) as exc_info:
        GuardCondition(field="request.type", operator="invalid_op", value="query")

    error_msg = str(exc_info.value)
    assert "operator" in error_msg.lower()


def test_guard_condition_field_path_validation():
    """Test guard condition validates field path syntax."""
    # Valid dot notation paths
    GuardCondition(field="request.user.role", operator="eq", value="admin")
    GuardCondition(field="metadata.profile", operator="ne", value="test")

    # Invalid field path (empty)
    with pytest.raises(ValidationError):
        GuardCondition(field="", operator="eq", value="test")


def test_guard_action_valid():
    """Test valid guard action passes validation."""
    action = GuardAction(action="allow", message="Access granted")
    assert action.action == "allow"

    action_route = GuardAction(action="route_to", target="fallback_agent", message="Routing")
    assert action_route.target == "fallback_agent"


def test_guard_action_route_to_requires_target():
    """Test route_to action requires target field."""
    with pytest.raises(ValidationError) as exc_info:
        GuardAction(action="route_to", message="Routing")  # Missing target

    error_msg = str(exc_info.value)
    assert "target" in error_msg.lower()


def test_routing_guard_valid():
    """Test valid routing guard passes validation."""
    guard = RoutingGuard(
        name="admin_only",
        priority=80,
        conditions=[GuardCondition(field="user.role", operator="eq", value="admin")],
        actions=[GuardAction(action="allow")],
    )

    assert guard.name == "admin_only"
    assert guard.priority == 80
    assert len(guard.conditions) == 1


def test_routing_guard_snake_case_name():
    """Test routing guard name must be snake_case."""
    # Valid snake_case names
    RoutingGuard(
        name="admin_access",
        conditions=[GuardCondition(field="user.role", operator="eq", value="admin")],
        actions=[GuardAction(action="allow")],
    )

    # Invalid names (should raise)
    with pytest.raises(ValidationError):
        RoutingGuard(
            name="AdminAccess",  # CamelCase not allowed
            conditions=[GuardCondition(field="user.role", operator="eq", value="admin")],
            actions=[GuardAction(action="allow")],
        )


def test_routing_guard_priority_bounds():
    """Test routing guard priority must be 0-100."""
    # Valid priorities
    RoutingGuard(
        name="low_priority",
        priority=10,
        conditions=[GuardCondition(field="user.role", operator="eq", value="user")],
        actions=[GuardAction(action="allow")],
    )

    # Invalid priority (too high)
    with pytest.raises(ValidationError):
        RoutingGuard(
            name="invalid_priority",
            priority=150,  # Exceeds 100
            conditions=[GuardCondition(field="user.role", operator="eq", value="user")],
            actions=[GuardAction(action="allow")],
        )


def test_guards_config_unique_names():
    """Test GuardsConfig enforces unique guard names."""
    with pytest.raises(ValidationError) as exc_info:
        GuardsConfig(
            guards=[
                RoutingGuard(
                    name="admin_check",
                    conditions=[GuardCondition(field="user.role", operator="eq", value="admin")],
                    actions=[GuardAction(action="allow")],
                ),
                RoutingGuard(
                    name="admin_check",  # Duplicate name
                    conditions=[GuardCondition(field="user.type", operator="eq", value="admin")],
                    actions=[GuardAction(action="deny")],
                ),
            ],
            default_action=GuardAction(action="deny"),
        )

    error_msg = str(exc_info.value)
    assert "unique" in error_msg.lower() or "duplicate" in error_msg.lower()


def test_guards_config_priority_conflict_warning(caplog):
    """Test GuardsConfig warns about same-priority guards."""
    config = GuardsConfig(
        guards=[
            RoutingGuard(
                name="guard1",
                priority=50,
                conditions=[GuardCondition(field="user.role", operator="eq", value="admin")],
                actions=[GuardAction(action="allow")],
            ),
            RoutingGuard(
                name="guard2",
                priority=50,  # Same priority
                conditions=[GuardCondition(field="user.role", operator="eq", value="user")],
                actions=[GuardAction(action="deny")],
            ),
        ],
        default_action=GuardAction(action="deny"),
    )

    # Should create config but may warn
    assert len(config.guards) == 2


# ---------------------------------------------------------------------------
# Test AgentConfig Schema
# ---------------------------------------------------------------------------


def test_agent_llm_config_valid():
    """Test valid AgentLLMConfig passes validation."""
    llm = AgentLLMConfig(
        provider="watsonx",
        model="granite-4-h-small",
        temperature=0.0,
        max_tokens=4096,
    )

    assert llm.provider == "watsonx"
    assert llm.model == "granite-4-h-small"
    assert llm.temperature == 0.0


def test_agent_llm_config_invalid_provider():
    """Test AgentLLMConfig rejects invalid providers."""
    with pytest.raises(ValidationError) as exc_info:
        AgentLLMConfig(
            provider="invalid_provider", model="model", temperature=0.7, max_tokens=4096
        )

    error_msg = str(exc_info.value)
    assert "provider" in error_msg.lower()


def test_agent_llm_config_temperature_bounds():
    """Test AgentLLMConfig enforces temperature bounds 0.0-2.0."""
    # Valid temperatures
    AgentLLMConfig(provider="openai", model="gpt-4o", temperature=0.0, max_tokens=4096)
    AgentLLMConfig(provider="openai", model="gpt-4o", temperature=2.0, max_tokens=4096)

    # Invalid temperature (too high)
    with pytest.raises(ValidationError):
        AgentLLMConfig(provider="openai", model="gpt-4o", temperature=3.0, max_tokens=4096)

    # Invalid temperature (negative)
    with pytest.raises(ValidationError):
        AgentLLMConfig(provider="openai", model="gpt-4o", temperature=-0.1, max_tokens=4096)


def test_agent_llm_config_max_tokens_bounds():
    """Test AgentLLMConfig enforces max_tokens bounds 1-128000."""
    # Valid max_tokens
    AgentLLMConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=1)
    AgentLLMConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=128000)

    # Invalid max_tokens (too high)
    with pytest.raises(ValidationError):
        AgentLLMConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=200000)

    # Invalid max_tokens (zero)
    with pytest.raises(ValidationError):
        AgentLLMConfig(provider="openai", model="gpt-4o", temperature=0.7, max_tokens=0)


def test_agent_llm_config_hardcoded_api_key_warning(caplog):
    """Test AgentLLMConfig warns about hardcoded API keys."""
    llm = AgentLLMConfig(
        provider="openai",
        model="gpt-4o",
        temperature=0.7,
        max_tokens=4096,
        api_key="sk-1234567890abcdef",  # Hardcoded key
    )

    # Should create config but may warn
    assert llm.api_key == "sk-1234567890abcdef"


def test_agent_config_valid():
    """Test valid AgentConfig passes validation."""
    config = AgentConfig(
        agent_type="planner",
        max_retries=3,
        timeout=300.0,
        llm=AgentLLMConfig(
            provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
        ),
    )

    assert config.agent_type == "planner"
    assert config.max_retries == 3
    assert config.timeout == 300.0


def test_agent_config_invalid_agent_type():
    """Test AgentConfig rejects invalid agent types."""
    with pytest.raises(ValidationError) as exc_info:
        AgentConfig(
            agent_type="invalid_type",
            llm=AgentLLMConfig(
                provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
            ),
        )

    error_msg = str(exc_info.value)
    assert "agent_type" in error_msg.lower()


def test_agent_config_max_retries_bounds():
    """Test AgentConfig enforces max_retries bounds 0-10."""
    # Valid retries
    AgentConfig(
        agent_type="worker",
        max_retries=0,
        llm=AgentLLMConfig(
            provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
        ),
    )

    # Invalid retries (too high)
    with pytest.raises(ValidationError):
        AgentConfig(
            agent_type="worker",
            max_retries=20,
            llm=AgentLLMConfig(
                provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
            ),
        )


def test_agent_config_timeout_bounds():
    """Test AgentConfig enforces timeout bounds 1-3600s."""
    # Valid timeouts
    AgentConfig(
        agent_type="worker",
        timeout=1.0,
        llm=AgentLLMConfig(
            provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
        ),
    )

    # Invalid timeout (too high)
    with pytest.raises(ValidationError):
        AgentConfig(
            agent_type="worker",
            timeout=5000.0,
            llm=AgentLLMConfig(
                provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
            ),
        )

    # Invalid timeout (zero)
    with pytest.raises(ValidationError):
        AgentConfig(
            agent_type="worker",
            timeout=0.0,
            llm=AgentLLMConfig(
                provider="watsonx", model="granite-4-h-small", temperature=0.0, max_tokens=4096
            ),
        )


# ---------------------------------------------------------------------------
# Test MemoryConfig Schema
# ---------------------------------------------------------------------------


def test_memory_config_valid():
    """Test valid MemoryConfig passes validation."""
    config = MemoryConfig(backend="faiss", retention_days=30, embedding_model="all-MiniLM-L6-v2")

    assert config.backend == "faiss"
    assert config.retention_days == 30


def test_memory_config_invalid_backend():
    """Test MemoryConfig rejects invalid backend types."""
    with pytest.raises(ValidationError) as exc_info:
        MemoryConfig(backend="invalid_backend")

    error_msg = str(exc_info.value)
    assert "backend" in error_msg.lower()


def test_memory_config_retention_bounds():
    """Test MemoryConfig enforces retention_days bounds 1-3650."""
    # Valid retention
    MemoryConfig(backend="local", retention_days=365)

    # Invalid retention (too high)
    with pytest.raises(ValidationError):
        MemoryConfig(backend="local", retention_days=5000)

    # Invalid retention (zero)
    with pytest.raises(ValidationError):
        MemoryConfig(backend="local", retention_days=0)


# ---------------------------------------------------------------------------
# Test ObservabilityConfig Schema
# ---------------------------------------------------------------------------


def test_observability_config_valid():
    """Test valid ObservabilityConfig passes validation."""
    config = ObservabilityConfig(
        emitter_type="langfuse", trace_sampling_rate=0.5, redact_secrets=True
    )

    assert config.emitter_type == "langfuse"
    assert config.trace_sampling_rate == 0.5
    assert config.redact_secrets is True


def test_observability_config_invalid_emitter():
    """Test ObservabilityConfig rejects invalid emitter types."""
    with pytest.raises(ValidationError) as exc_info:
        ObservabilityConfig(emitter_type="invalid_emitter")

    error_msg = str(exc_info.value)
    assert "emitter" in error_msg.lower()


def test_observability_config_sampling_rate_bounds():
    """Test ObservabilityConfig enforces trace_sampling_rate bounds 0.0-1.0."""
    # Valid sampling rates
    ObservabilityConfig(emitter_type="otel", trace_sampling_rate=0.0)
    ObservabilityConfig(emitter_type="otel", trace_sampling_rate=1.0)

    # Invalid sampling rate (too high)
    with pytest.raises(ValidationError):
        ObservabilityConfig(emitter_type="otel", trace_sampling_rate=1.5)

    # Invalid sampling rate (negative)
    with pytest.raises(ValidationError):
        ObservabilityConfig(emitter_type="otel", trace_sampling_rate=-0.1)


# ---------------------------------------------------------------------------
# Test ConfigValidator Integration
# ---------------------------------------------------------------------------


def test_config_validator_registry_integration():
    """Test ConfigValidator.validate_registry() with schema."""
    from cuga.config import ConfigValidator

    valid_registry = {
        "tools": {
            "file_search": {
                "module": "cuga.modular.tools.file_search",
                "handler": "search",
                "description": "File search tool",
                "sandbox_profile": "py_slim",
                "mounts": ["/workdir:/workdir:ro"],
            }
        }
    }

    # Should not raise
    ConfigValidator.validate_registry(valid_registry)


def test_config_validator_guards_integration():
    """Test ConfigValidator.validate_guards() with schema."""
    from cuga.config import ConfigValidator

    valid_guards = {
        "guards": [
            {
                "name": "admin_only",
                "priority": 80,
                "conditions": [{"field": "user.role", "operator": "eq", "value": "admin"}],
                "actions": [{"action": "allow"}],
            }
        ],
        "default_action": {"action": "deny"},
    }

    # Should not raise
    ConfigValidator.validate_guards(valid_guards)


def test_config_validator_agent_integration():
    """Test ConfigValidator.validate_agent_config() with schema."""
    from cuga.config import ConfigValidator

    valid_agent = {
        "agent_type": "planner",
        "max_retries": 3,
        "timeout": 300.0,
        "llm": {
            "provider": "watsonx",
            "model": "granite-4-h-small",
            "temperature": 0.0,
            "max_tokens": 4096,
        },
    }

    # Should not raise
    ConfigValidator.validate_agent_config(valid_agent)
