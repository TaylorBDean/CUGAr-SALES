"""Unit tests for environment mode validation."""

import os

import pytest

from cuga.config.validators import (
    EnvironmentMode,
    ValidationResult,
    validate_environment_mode,
    validate_startup,
)


class TestEnvironmentMode:
    """Test EnvironmentMode enum."""

    def test_mode_values(self):
        """Test that mode values are correct strings."""
        assert EnvironmentMode.LOCAL.value == "local"
        assert EnvironmentMode.SERVICE.value == "service"
        assert EnvironmentMode.MCP.value == "mcp"
        assert EnvironmentMode.TEST.value == "test"


class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creation of valid result."""
        result = ValidationResult(
            is_valid=True,
            mode=EnvironmentMode.LOCAL,
            present={"WATSONX_API_KEY", "WATSONX_PROJECT_ID"},
        )

        assert result.is_valid is True
        assert result.mode == EnvironmentMode.LOCAL
        assert len(result.missing_required) == 0
        assert len(result.present) == 2

    def test_invalid_result(self):
        """Test creation of invalid result."""
        result = ValidationResult(
            is_valid=False,
            mode=EnvironmentMode.SERVICE,
            missing_required={"AGENT_TOKEN", "AGENT_BUDGET_CEILING"},
            suggestions=["Set AGENT_TOKEN for authentication"],
        )

        assert result.is_valid is False
        assert len(result.missing_required) == 2
        assert len(result.suggestions) == 1

    def test_string_representation(self):
        """Test human-readable string representation."""
        result = ValidationResult(
            is_valid=False,
            mode=EnvironmentMode.SERVICE,
            missing_required={"AGENT_TOKEN"},
            suggestions=["Set AGENT_TOKEN=<token>"],
        )

        string_repr = str(result)
        assert "service mode" in string_repr
        assert "Invalid" in string_repr
        assert "AGENT_TOKEN" in string_repr
        assert "Suggestions" in string_repr


class TestLocalModeValidation:
    """Test LOCAL execution mode validation."""

    def test_valid_local_watsonx(self, monkeypatch):
        """Test valid local mode with Watsonx credentials."""
        # Clear all env vars first
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_", "AGENT_", "MCP_"]
            ):
                monkeypatch.delenv(key, raising=False)

        # Set Watsonx credentials
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.LOCAL)

        assert result.is_valid is True
        assert "WATSONX_API_KEY" in result.present
        assert "WATSONX_PROJECT_ID" in result.present

    def test_valid_local_openai(self, monkeypatch):
        """Test valid local mode with OpenAI credentials."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_", "AGENT_", "MCP_"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")

        result = validate_environment_mode(EnvironmentMode.LOCAL)

        assert result.is_valid is True
        assert "OPENAI_API_KEY" in result.present

    def test_valid_local_anthropic(self, monkeypatch):
        """Test valid local mode with Anthropic credentials."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_", "AGENT_", "MCP_"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

        result = validate_environment_mode(EnvironmentMode.LOCAL)

        assert result.is_valid is True
        assert "ANTHROPIC_API_KEY" in result.present

    def test_invalid_local_no_provider(self, monkeypatch):
        """Test invalid local mode with no provider credentials."""
        # Clear all provider credentials
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_"]
            ):
                monkeypatch.delenv(key, raising=False)

        result = validate_environment_mode(EnvironmentMode.LOCAL)

        assert result.is_valid is False
        # Should suggest Watsonx (default provider) credentials
        assert "WATSONX_API_KEY" in result.missing_required or "OPENAI_API_KEY" in result.missing_required

    def test_local_partial_watsonx_credentials(self, monkeypatch):
        """Test invalid local mode with partial Watsonx credentials."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_"]
            ):
                monkeypatch.delenv(key, raising=False)

        # Only API key, missing project ID
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")

        result = validate_environment_mode(EnvironmentMode.LOCAL)

        assert result.is_valid is False
        assert "WATSONX_PROJECT_ID" in result.missing_required

    def test_local_with_optional_vars(self, monkeypatch):
        """Test local mode with optional variables present."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_", "MODEL_", "PROFILE"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")
        monkeypatch.setenv("MODEL_NAME", "granite-4-h-small")
        monkeypatch.setenv("PROFILE", "production")

        result = validate_environment_mode(EnvironmentMode.LOCAL)

        assert result.is_valid is True
        assert "MODEL_NAME" in result.present
        assert "PROFILE" in result.present


class TestServiceModeValidation:
    """Test SERVICE execution mode validation."""

    def test_valid_service_mode(self, monkeypatch):
        """Test valid service mode with all required vars."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AGENT_", "MCP_"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("AGENT_TOKEN", "secret-token")
        monkeypatch.setenv("AGENT_BUDGET_CEILING", "100")
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.SERVICE)

        assert result.is_valid is True
        assert "AGENT_TOKEN" in result.present
        assert "AGENT_BUDGET_CEILING" in result.present
        assert "WATSONX_API_KEY" in result.present

    def test_invalid_service_missing_auth(self, monkeypatch):
        """Test invalid service mode missing authentication."""
        for key in list(os.environ.keys()):
            if any(key.startswith(p) for p in ["AGENT_", "WATSONX_", "OPENAI_"]):
                monkeypatch.delenv(key, raising=False)

        # Have provider but missing AGENT_TOKEN
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.SERVICE)

        assert result.is_valid is False
        assert "AGENT_TOKEN" in result.missing_required

    def test_invalid_service_missing_budget(self, monkeypatch):
        """Test invalid service mode missing budget enforcement."""
        for key in list(os.environ.keys()):
            if any(key.startswith(p) for p in ["AGENT_", "WATSONX_", "OPENAI_"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("AGENT_TOKEN", "secret-token")
        # Missing AGENT_BUDGET_CEILING
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.SERVICE)

        assert result.is_valid is False
        assert "AGENT_BUDGET_CEILING" in result.missing_required

    def test_invalid_service_missing_provider(self, monkeypatch):
        """Test invalid service mode missing provider credentials."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("AGENT_TOKEN", "secret-token")
        monkeypatch.setenv("AGENT_BUDGET_CEILING", "100")

        result = validate_environment_mode(EnvironmentMode.SERVICE)

        assert result.is_valid is False
        # Should require at least one provider
        assert any(
            var in result.missing_required
            for var in ["WATSONX_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
        )

    def test_service_with_observability_optional(self, monkeypatch):
        """Test service mode with optional observability vars."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["AGENT_", "WATSONX_", "OTEL_", "LANGFUSE_"]
            ):
                monkeypatch.delenv(key, raising=False)

        # Required vars
        monkeypatch.setenv("AGENT_TOKEN", "secret-token")
        monkeypatch.setenv("AGENT_BUDGET_CEILING", "100")
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        # Optional observability
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-test")

        result = validate_environment_mode(EnvironmentMode.SERVICE)

        assert result.is_valid is True
        assert "OTEL_EXPORTER_OTLP_ENDPOINT" in result.present
        assert "LANGFUSE_PUBLIC_KEY" in result.present


class TestMCPModeValidation:
    """Test MCP execution mode validation."""

    def test_valid_mcp_mode(self, monkeypatch):
        """Test valid MCP mode with all required vars."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["MCP_", "CUGA_", "WATSONX_", "OPENAI_"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MCP_SERVERS_FILE", "./configs/mcp_servers.yaml")
        monkeypatch.setenv("CUGA_PROFILE_SANDBOX", "docker")
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.MCP)

        assert result.is_valid is True
        assert "MCP_SERVERS_FILE" in result.present
        assert "CUGA_PROFILE_SANDBOX" in result.present

    def test_invalid_mcp_missing_servers_file(self, monkeypatch):
        """Test invalid MCP mode missing MCP_SERVERS_FILE."""
        for key in list(os.environ.keys()):
            if any(key.startswith(p) for p in ["MCP_", "CUGA_", "WATSONX_"]):
                monkeypatch.delenv(key, raising=False)

        # Missing MCP_SERVERS_FILE
        monkeypatch.setenv("CUGA_PROFILE_SANDBOX", "docker")
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.MCP)

        assert result.is_valid is False
        assert "MCP_SERVERS_FILE" in result.missing_required

    def test_invalid_mcp_missing_sandbox_profile(self, monkeypatch):
        """Test invalid MCP mode missing CUGA_PROFILE_SANDBOX."""
        for key in list(os.environ.keys()):
            if any(key.startswith(p) for p in ["MCP_", "CUGA_", "WATSONX_"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MCP_SERVERS_FILE", "./configs/mcp_servers.yaml")
        # Missing CUGA_PROFILE_SANDBOX
        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        result = validate_environment_mode(EnvironmentMode.MCP)

        assert result.is_valid is False
        assert "CUGA_PROFILE_SANDBOX" in result.missing_required

    def test_invalid_mcp_missing_provider(self, monkeypatch):
        """Test invalid MCP mode missing provider credentials."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["MCP_", "CUGA_", "WATSONX_", "OPENAI_", "ANTHROPIC_"]
            ):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("MCP_SERVERS_FILE", "./configs/mcp_servers.yaml")
        monkeypatch.setenv("CUGA_PROFILE_SANDBOX", "docker")

        result = validate_environment_mode(EnvironmentMode.MCP)

        assert result.is_valid is False
        # Should require at least one provider
        assert any(
            var in result.missing_required
            for var in ["WATSONX_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"]
        )


class TestTestModeValidation:
    """Test TEST execution mode validation."""

    def test_valid_test_mode_no_vars(self, monkeypatch):
        """Test that test mode requires no environment variables."""
        # Clear all env vars
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "AGENT_", "MCP_", "CUGA_", "PYTEST_"]
            ):
                monkeypatch.delenv(key, raising=False)

        result = validate_environment_mode(EnvironmentMode.TEST)

        assert result.is_valid is True
        assert len(result.missing_required) == 0

    def test_valid_test_mode_with_vars(self, monkeypatch):
        """Test that test mode is valid even with env vars present."""
        monkeypatch.setenv("PYTEST_TIMEOUT", "300")
        monkeypatch.setenv("CUGA_TEST_PROFILE", "ci")

        result = validate_environment_mode(EnvironmentMode.TEST)

        assert result.is_valid is True
        # Optional vars tracked but not required
        assert "PYTEST_TIMEOUT" in result.present or "pytest_timeout" in result.present


class TestValidateStartup:
    """Test validate_startup with fail-fast behavior."""

    def test_validate_startup_success(self, monkeypatch):
        """Test that validate_startup passes for valid environment."""
        for key in list(os.environ.keys()):
            if any(key.startswith(p) for p in ["WATSONX_", "OPENAI_"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        # Should not raise
        result = validate_startup(EnvironmentMode.LOCAL, fail_fast=True)
        assert result.is_valid is True

    def test_validate_startup_fail_fast_raises(self, monkeypatch):
        """Test that validate_startup raises RuntimeError on invalid environment."""
        # Clear all provider credentials
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_", "AZURE_", "GROQ_"]
            ):
                monkeypatch.delenv(key, raising=False)

        with pytest.raises(RuntimeError, match="Environment validation failed"):
            validate_startup(EnvironmentMode.LOCAL, fail_fast=True)

    def test_validate_startup_no_fail_fast(self, monkeypatch):
        """Test that validate_startup returns result without raising."""
        for key in list(os.environ.keys()):
            if any(
                key.startswith(p)
                for p in ["WATSONX_", "OPENAI_", "ANTHROPIC_"]
            ):
                monkeypatch.delenv(key, raising=False)

        # Should not raise, just return invalid result
        result = validate_startup(EnvironmentMode.LOCAL, fail_fast=False)
        assert result.is_valid is False
        assert len(result.missing_required) > 0

    def test_validate_startup_error_message_quality(self, monkeypatch):
        """Test that validation error messages are helpful."""
        for key in list(os.environ.keys()):
            if any(key.startswith(p) for p in ["AGENT_", "WATSONX_"]):
                monkeypatch.delenv(key, raising=False)

        monkeypatch.setenv("WATSONX_API_KEY", "test-key")
        monkeypatch.setenv("WATSONX_PROJECT_ID", "test-project")

        try:
            validate_startup(EnvironmentMode.SERVICE, fail_fast=True)
            pytest.fail("Should have raised RuntimeError")
        except RuntimeError as e:
            error_msg = str(e)
            # Check for helpful error message components
            assert "service mode" in error_msg
            assert "AGENT_TOKEN" in error_msg or "AGENT_BUDGET_CEILING" in error_msg
            assert "Suggestions" in error_msg
            assert "ENVIRONMENT_MODES.md" in error_msg
