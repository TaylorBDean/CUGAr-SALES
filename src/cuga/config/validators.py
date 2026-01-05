"""
Environment Mode Validation

Validates required/optional environment variables per execution mode
(local, service, mcp, test) based on specs in docs/configuration/ENVIRONMENT_MODES.md.

Usage:
    from cuga.config.validators import validate_environment_mode, EnvironmentMode
    
    result = validate_environment_mode(EnvironmentMode.SERVICE)
    if not result.is_valid:
        print(f"Missing required vars: {result.missing_required}")
        print(f"Suggestions: {result.suggestions}")
        raise RuntimeError("Invalid environment configuration")
"""

import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set

from loguru import logger


class EnvironmentMode(str, Enum):
    """Execution modes with different environment requirements."""

    LOCAL = "local"  # Local CLI development
    SERVICE = "service"  # FastAPI backend service
    MCP = "mcp"  # MCP orchestration mode
    TEST = "test"  # Test/CI mode (no env vars required)


@dataclass
class ValidationResult:
    """
    Result of environment validation.
    
    Attributes:
        is_valid: True if all required vars present
        mode: The execution mode validated
        missing_required: Required env vars that are missing
        missing_optional: Optional env vars that are missing (informational)
        present: Env vars that are present
        suggestions: Helpful suggestions for missing vars
    """

    is_valid: bool
    mode: EnvironmentMode
    missing_required: Set[str] = field(default_factory=set)
    missing_optional: Set[str] = field(default_factory=set)
    present: Set[str] = field(default_factory=set)
    suggestions: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        lines = [f"Environment validation for {self.mode.value} mode:"]
        if self.is_valid:
            lines.append(f"  ✅ Valid ({len(self.present)} vars present)")
        else:
            lines.append(f"  ❌ Invalid - missing {len(self.missing_required)} required vars")
            for var in sorted(self.missing_required):
                lines.append(f"    - {var}")

        if self.missing_optional:
            lines.append(f"  ℹ️  Optional vars not set ({len(self.missing_optional)}):")
            for var in sorted(self.missing_optional):
                lines.append(f"    - {var}")

        if self.suggestions:
            lines.append("  💡 Suggestions:")
            for suggestion in self.suggestions:
                lines.append(f"    {suggestion}")

        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Environment Variable Specifications (from ENVIRONMENT_MODES.md)
# ---------------------------------------------------------------------------


# Provider-specific env vars (one required per mode that needs model access)
PROVIDER_VARS = {
    "watsonx": ["WATSONX_API_KEY", "WATSONX_PROJECT_ID"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "azure": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "groq": ["GROQ_API_KEY"],
}


# Mode-specific requirements
ENV_REQUIREMENTS: Dict[EnvironmentMode, Dict[str, List[str]]] = {
    EnvironmentMode.LOCAL: {
        "required": [
            # At least one provider required (checked separately)
        ],
        "optional": [
            "MODEL_NAME",  # Model override (defaults to provider default)
            "PROFILE",  # Profile selection (defaults to "default")
            "CUGA_VECTOR_BACKEND",  # Vector backend (defaults to "chroma")
            "OTEL_EXPORTER_OTLP_ENDPOINT",  # Observability
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGSMITH_API_KEY",
        ],
        "conditional": [
            # If using Chroma vector backend
            ("CUGA_VECTOR_BACKEND=chroma", ["CHROMA_HOST", "CHROMA_PORT"]),
            # If using Qdrant vector backend
            ("CUGA_VECTOR_BACKEND=qdrant", ["QDRANT_URL", "QDRANT_API_KEY"]),
        ],
    },
    EnvironmentMode.SERVICE: {
        "required": [
            "AGENT_TOKEN",  # Authentication token
            "AGENT_BUDGET_CEILING",  # Budget enforcement
            # At least one provider required (checked separately)
        ],
        "optional": [
            "MODEL_NAME",
            "PROFILE",
            "CUGA_VECTOR_BACKEND",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGSMITH_API_KEY",
        ],
        "conditional": [],
    },
    EnvironmentMode.MCP: {
        "required": [
            "MCP_SERVERS_FILE",  # MCP server definitions
            "CUGA_PROFILE_SANDBOX",  # Sandbox isolation profile
            # At least one provider required (checked separately)
        ],
        "optional": [
            "MODEL_NAME",
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
        ],
        "conditional": [],
    },
    EnvironmentMode.TEST: {
        "required": [],  # No env vars required (uses defaults/mocks)
        "optional": [
            "PYTEST_TIMEOUT",
            "CUGA_TEST_PROFILE",
        ],
        "conditional": [],
    },
}


# Helpful suggestions per missing var
SUGGESTIONS: Dict[str, str] = {
    # Authentication
    "AGENT_TOKEN": "Set AGENT_TOKEN for API authentication (required for service mode). "
    "Generate with: openssl rand -hex 32",
    "AGENT_BUDGET_CEILING": "Set AGENT_BUDGET_CEILING to limit token usage (default: 100). "
    "Example: AGENT_BUDGET_CEILING=500",
    # Watsonx
    "WATSONX_API_KEY": "Set WATSONX_API_KEY with IBM Cloud API key. "
    "See: https://cloud.ibm.com/iam/apikeys",
    "WATSONX_PROJECT_ID": "Set WATSONX_PROJECT_ID with watsonx.ai project ID. "
    "See: https://dataplatform.cloud.ibm.com/projects",
    # OpenAI
    "OPENAI_API_KEY": "Set OPENAI_API_KEY from https://platform.openai.com/api-keys",
    # Anthropic
    "ANTHROPIC_API_KEY": "Set ANTHROPIC_API_KEY from https://console.anthropic.com/settings/keys",
    # Azure
    "AZURE_OPENAI_API_KEY": "Set AZURE_OPENAI_API_KEY from Azure portal",
    "AZURE_OPENAI_ENDPOINT": "Set AZURE_OPENAI_ENDPOINT (e.g., https://your-resource.openai.azure.com/)",
    # Groq
    "GROQ_API_KEY": "Set GROQ_API_KEY from https://console.groq.com/keys",
    # MCP
    "MCP_SERVERS_FILE": "Set MCP_SERVERS_FILE to path of MCP server definitions YAML. "
    "Example: MCP_SERVERS_FILE=./configurations/mcp_servers.yaml",
    "CUGA_PROFILE_SANDBOX": "Set CUGA_PROFILE_SANDBOX for sandbox isolation (e.g., 'docker', 'local'). "
    "See: docs/sandboxing.md",
    # Vector backends
    "CHROMA_HOST": "Set CHROMA_HOST for Chroma vector backend (default: localhost)",
    "CHROMA_PORT": "Set CHROMA_PORT for Chroma vector backend (default: 8000)",
    "QDRANT_URL": "Set QDRANT_URL for Qdrant vector backend (e.g., http://localhost:6333)",
    "QDRANT_API_KEY": "Set QDRANT_API_KEY if using Qdrant with authentication",
}


def validate_environment_mode(mode: EnvironmentMode) -> ValidationResult:
    """
    Validate environment variables for a specific execution mode.
    
    Args:
        mode: Execution mode to validate (local/service/mcp/test)
        
    Returns:
        ValidationResult with validation status and helpful suggestions
        
    Example:
        result = validate_environment_mode(EnvironmentMode.SERVICE)
        if not result.is_valid:
            print(result)  # Prints missing vars and suggestions
            raise RuntimeError("Invalid environment")
    """
    requirements = ENV_REQUIREMENTS[mode]
    required = set(requirements["required"])
    optional = set(requirements["optional"])

    # Check required vars
    missing_required = {var for var in required if not os.getenv(var)}

    # Check provider vars (at least one provider required for non-test modes)
    if mode != EnvironmentMode.TEST:
        has_provider = False
        missing_providers = {}

        for provider_name, provider_vars in PROVIDER_VARS.items():
            provider_complete = all(os.getenv(var) for var in provider_vars)
            if provider_complete:
                has_provider = True
                break
            else:
                missing_providers[provider_name] = [var for var in provider_vars if not os.getenv(var)]

        if not has_provider:
            # Add missing provider vars to required (choose first available)
            # Prefer watsonx (default provider)
            if "watsonx" in missing_providers:
                missing_required.update(missing_providers["watsonx"])
            else:
                # Fall back to first provider with fewest missing vars
                best_provider = min(missing_providers.items(), key=lambda x: len(x[1]))
                missing_required.update(best_provider[1])

    # Check optional vars
    missing_optional = {var for var in optional if not os.getenv(var)}

    # Track present vars
    present = set()
    for var in required | optional:
        if os.getenv(var):
            present.add(var)

    # Add provider vars to present set
    for provider_vars in PROVIDER_VARS.values():
        for var in provider_vars:
            if os.getenv(var):
                present.add(var)

    # Generate suggestions
    suggestions = []
    for var in sorted(missing_required):
        if var in SUGGESTIONS:
            suggestions.append(f"• {SUGGESTIONS[var]}")

    # Check conditional requirements
    for condition, cond_vars in requirements.get("conditional", []):
        if _check_condition(condition):
            for var in cond_vars:
                if not os.getenv(var):
                    missing_required.add(var)
                    if var in SUGGESTIONS:
                        suggestions.append(f"• {SUGGESTIONS[var]} (required when {condition})")

    is_valid = len(missing_required) == 0

    result = ValidationResult(
        is_valid=is_valid,
        mode=mode,
        missing_required=missing_required,
        missing_optional=missing_optional,
        present=present,
        suggestions=suggestions,
    )

    if is_valid:
        logger.debug(f"Environment validation passed for {mode.value} mode ({len(present)} vars present)")
    else:
        logger.warning(
            f"Environment validation failed for {mode.value} mode "
            f"(missing {len(missing_required)} required vars)"
        )

    return result


def _check_condition(condition: str) -> bool:
    """
    Check if a conditional requirement is met.
    
    Args:
        condition: Condition string (e.g., "CUGA_VECTOR_BACKEND=chroma")
        
    Returns:
        True if condition matches current environment
    """
    if "=" in condition:
        var, expected = condition.split("=", 1)
        actual = os.getenv(var, "")
        return actual == expected
    else:
        # Simple existence check
        return bool(os.getenv(condition))


def validate_startup(mode: EnvironmentMode, fail_fast: bool = True) -> ValidationResult:
    """
    Validate environment at application startup.
    
    Args:
        mode: Execution mode
        fail_fast: If True, raise RuntimeError on validation failure
        
    Returns:
        ValidationResult
        
    Raises:
        RuntimeError: If fail_fast=True and validation fails
    """
    result = validate_environment_mode(mode)

    if not result.is_valid and fail_fast:
        error_msg = [
            f"Environment validation failed for {mode.value} mode.",
            f"Missing {len(result.missing_required)} required variables:",
        ]
        for var in sorted(result.missing_required):
            error_msg.append(f"  - {var}")

        if result.suggestions:
            error_msg.append("\nSuggestions:")
            error_msg.extend(f"  {s}" for s in result.suggestions)

        error_msg.append("\nSee docs/configuration/ENVIRONMENT_MODES.md for complete requirements.")

        raise RuntimeError("\n".join(error_msg))

    return result


# ============================================================================
# Schema Validation (added in Phase 5: Config Single Source of Truth)
# ============================================================================

from typing import Any
from pydantic import ValidationError as PydanticValidationError


class ConfigValidator:
    """Validates resolved configuration against Pydantic schemas."""

    @staticmethod
    def validate_registry(config: Dict[str, Any]):
        """
        Validate tool registry against schema.

        Args:
            config: Registry configuration dict (must have 'tools' key)

        Returns:
            Validated ToolRegistry instance

        Raises:
            ValidationError: If registry invalid with detailed error message
        """
        from .schemas.registry_schema import ToolRegistry

        try:
            registry = ToolRegistry(**config)
            logger.info(f"✅ Registry validation passed: {len(registry.tools)} tools")
            return registry
        except PydanticValidationError as e:
            logger.error(f"❌ Registry validation failed: {e}")
            raise ValueError(f"Tool registry validation failed:\n{e}") from e

    @staticmethod
    def validate_guards(config: Dict[str, Any]):
        """
        Validate guards configuration against schema.

        Args:
            config: Guards configuration dict (must have 'guards' and 'default_action' keys)

        Returns:
            Validated GuardsConfig instance

        Raises:
            ValidationError: If guards invalid
        """
        from .schemas.guards_schema import GuardsConfig

        try:
            guards = GuardsConfig(**config)
            logger.info(f"✅ Guards validation passed: {len(guards.guards)} rules")
            return guards
        except PydanticValidationError as e:
            logger.error(f"❌ Guards validation failed: {e}")
            raise ValueError(f"Guards configuration validation failed:\n{e}") from e

    @staticmethod
    def validate_agent_config(config: Dict[str, Any]):
        """
        Validate agent configuration against schema.

        Args:
            config: Agent configuration dict

        Returns:
            Validated AgentConfig instance

        Raises:
            ValidationError: If config invalid
        """
        from .schemas.agent_schema import AgentConfig

        try:
            agent_config = AgentConfig(**config)
            logger.info(f"✅ Agent config validation passed: {agent_config.name}")
            return agent_config
        except PydanticValidationError as e:
            logger.error(f"❌ Agent config validation failed: {e}")
            raise ValueError(f"Agent configuration validation failed:\n{e}") from e

    @staticmethod
    def validate_memory_config(config: Dict[str, Any]):
        """
        Validate memory configuration against schema.

        Args:
            config: Memory configuration dict

        Returns:
            Validated MemoryConfig instance

        Raises:
            ValidationError: If config invalid
        """
        from .schemas.agent_schema import MemoryConfig

        try:
            memory_config = MemoryConfig(**config)
            logger.info(f"✅ Memory config validation passed: backend={memory_config.backend}")
            return memory_config
        except PydanticValidationError as e:
            logger.error(f"❌ Memory config validation failed: {e}")
            raise ValueError(f"Memory configuration validation failed:\n{e}") from e

    @staticmethod
    def validate_observability_config(config: Dict[str, Any]):
        """
        Validate observability configuration against schema.

        Args:
            config: Observability configuration dict

        Returns:
            Validated ObservabilityConfig instance

        Raises:
            ValidationError: If config invalid
        """
        from .schemas.agent_schema import ObservabilityConfig

        try:
            obs_config = ObservabilityConfig(**config)
            logger.info(f"✅ Observability config validation passed: emitter={obs_config.emitter}")
            return obs_config
        except PydanticValidationError as e:
            logger.error(f"❌ Observability config validation failed: {e}")
            raise ValueError(f"Observability configuration validation failed:\n{e}") from e
