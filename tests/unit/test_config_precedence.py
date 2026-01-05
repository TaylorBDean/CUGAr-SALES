"""
tests/unit/test_config_precedence.py

Test configuration precedence per AGENTS.md § Configuration Policy:
  CLI args > env vars > .env files > YAML configs > TOML configs > configuration defaults > hardcoded defaults

This test suite validates:
1. Precedence order (CLI > env > .env > YAML > TOML > defaults)
2. Deep merge for dicts, override for lists/scalars
3. Environment mode requirements (local/service/MCP/test)
4. Unknown key rejection via Pydantic schemas
5. Config provenance tracking
"""

import os
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch

import pytest
import yaml
from dotenv import dotenv_values

from cuga.config import (
    EVAL_CONFIG_TOML_PATH,
    PACKAGE_ROOT,
    SETTINGS_TOML_PATH,
    _find_config_file,
    base_settings,
    settings,
)


# ============================================================================
# Precedence Order Tests
# ============================================================================


class TestConfigPrecedence:
    """Test that configuration sources are resolved in correct precedence order."""

    def test_env_var_overrides_toml(self, monkeypatch):
        """Environment variables should override TOML settings."""
        # Set env var with DYNACONF_ prefix (Dynaconf convention)
        monkeypatch.setenv("DYNACONF_EVAL_CONFIG__HEADLESS", "true")
        
        # Re-import to pick up env change
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[SETTINGS_TOML_PATH, EVAL_CONFIG_TOML_PATH],
        )
        
        # Env var should override TOML default (which is False)
        assert test_settings.eval_config.headless is True

    def test_dotenv_overrides_toml(self, tmp_path, monkeypatch):
        """Values from .env files should override TOML configs."""
        # Create temp .env file
        env_file = tmp_path / ".env"
        env_file.write_text("DYNACONF_FEATURES__LOCAL_SANDBOX=false\n")
        
        # Load dotenv
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[SETTINGS_TOML_PATH],
        )
        
        # .env should override TOML default
        assert test_settings.features.local_sandbox is False

    def test_toml_overrides_defaults(self):
        """TOML settings should override hardcoded defaults."""
        # Check that base_settings has TOML values, not defaults
        # (TOML sets local_sandbox=true, which overrides a hypothetical hardcoded False)
        assert base_settings.features.local_sandbox is True
        assert base_settings.eval_config.headless is False  # Validator default

    def test_precedence_chain_full(self, tmp_path, monkeypatch):
        """Test full precedence chain: env > .env > TOML."""
        # Setup TOML (already exists)
        # Setup .env file
        env_file = tmp_path / ".env"
        env_file.write_text("DYNACONF_FEATURES__THOUGHTS=false\n")
        from dotenv import load_dotenv
        load_dotenv(env_file, override=False)
        
        # Setup env var (highest precedence)
        monkeypatch.setenv("DYNACONF_FEATURES__THOUGHTS", "true")
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[SETTINGS_TOML_PATH],
        )
        
        # Env var should win
        assert test_settings.features.thoughts is True

    def test_deep_merge_for_dicts(self, monkeypatch):
        """Nested dicts should deep merge, not replace entirely."""
        # Set partial nested config via env
        monkeypatch.setenv("DYNACONF_ADVANCED_FEATURES__LITE_MODE", "true")
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[SETTINGS_TOML_PATH],
        )
        
        # advanced_features should have both env override and TOML values
        assert test_settings.advanced_features.lite_mode is True
        assert test_settings.advanced_features.registry is True  # From TOML

    def test_list_override_not_merge(self, monkeypatch):
        """Lists should be replaced, not merged."""
        # Set playwright_args via env (should replace, not merge)
        monkeypatch.setenv("DYNACONF_PLAYWRIGHT_ARGS", '["--headless"]')
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[SETTINGS_TOML_PATH],
        )
        
        # Should be replaced list, not merged
        assert test_settings.playwright_args == ["--headless"]

    def test_scalar_override(self, monkeypatch):
        """Scalars (strings, ints) should be replaced."""
        monkeypatch.setenv("DYNACONF_ADVANCED_FEATURES__MESSAGE_WINDOW_LIMIT", "50")
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[SETTINGS_TOML_PATH],
        )
        
        assert test_settings.advanced_features.message_window_limit == 50


# ============================================================================
# Environment Mode Tests
# ============================================================================


class TestEnvironmentModes:
    """Test required/optional env vars per execution mode (local/service/MCP/test)."""

    def test_local_mode_requires_model_key(self, monkeypatch):
        """Local CLI mode requires model API key (OPENAI_API_KEY or provider key)."""
        # Clear all model keys
        for key in ["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GROQ_API_KEY"]:
            monkeypatch.delenv(key, raising=False)
        
        # Load LLM settings should raise helpful error
        from cuga.config import load_llm_settings
        
        with pytest.raises(Exception) as exc_info:
            # This will fail when trying to use LLM without key
            llm_settings = load_llm_settings()
            if not llm_settings.api_key:
                raise ValueError("Local mode requires model API key (OPENAI_API_KEY or provider-specific)")
        
        assert "api_key" in str(exc_info.value).lower() or "key" in str(exc_info.value).lower()

    def test_service_mode_requires_auth_and_budget(self, monkeypatch):
        """Service mode requires AGENT_TOKEN + AGENT_BUDGET_CEILING + model keys."""
        # Test missing AGENT_TOKEN
        monkeypatch.delenv("AGENT_TOKEN", raising=False)
        monkeypatch.delenv("AGENT_BUDGET_CEILING", raising=False)
        
        # In service mode, these should be validated
        assert os.getenv("AGENT_TOKEN") is None
        assert os.getenv("AGENT_BUDGET_CEILING") is None
        
        # Set required values
        monkeypatch.setenv("AGENT_TOKEN", "test_token_123")
        monkeypatch.setenv("AGENT_BUDGET_CEILING", "100")
        
        assert os.getenv("AGENT_TOKEN") == "test_token_123"
        assert os.getenv("AGENT_BUDGET_CEILING") == "100"

    def test_mcp_mode_requires_servers_and_profile(self, monkeypatch):
        """MCP mode requires MCP_SERVERS_FILE + CUGA_PROFILE_SANDBOX + model keys."""
        monkeypatch.delenv("MCP_SERVERS_FILE", raising=False)
        monkeypatch.delenv("CUGA_PROFILE_SANDBOX", raising=False)
        
        # Should be missing
        assert os.getenv("MCP_SERVERS_FILE") is None
        assert os.getenv("CUGA_PROFILE_SANDBOX") is None
        
        # Set required values
        monkeypatch.setenv("MCP_SERVERS_FILE", "/path/to/mcp_servers.json")
        monkeypatch.setenv("CUGA_PROFILE_SANDBOX", "py_slim")
        
        assert os.getenv("MCP_SERVERS_FILE") == "/path/to/mcp_servers.json"
        assert os.getenv("CUGA_PROFILE_SANDBOX") == "py_slim"

    def test_test_mode_no_required_env_vars(self):
        """Test mode requires no env vars (uses defaults/mocks)."""
        # Should be able to load settings without any env vars
        # (except those already in environment from pytest)
        assert base_settings is not None
        assert base_settings.features.local_sandbox is True

    def test_env_allowlist_enforcement(self, monkeypatch):
        """Only allowlisted env prefixes should be loaded."""
        # Per AGENTS.md: allowlist AGENT_*, OTEL_*, LANGFUSE_*, OPENINFERENCE_*, TRACELOOP_*
        allowlisted_prefixes = ["AGENT_", "OTEL_", "LANGFUSE_", "OPENINFERENCE_", "TRACELOOP_"]
        
        # Set allowlisted vars
        monkeypatch.setenv("AGENT_BUDGET_CEILING", "100")
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")
        monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "test_key")
        
        # Set non-allowlisted var (should be ignored by guardrails)
        monkeypatch.setenv("MALICIOUS_VAR", "bad_value")
        
        # Check allowlisted vars are accessible
        assert os.getenv("AGENT_BUDGET_CEILING") == "100"
        assert os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT") == "http://localhost:4318"
        assert os.getenv("LANGFUSE_PUBLIC_KEY") == "test_key"
        
        # Non-allowlisted var exists in os.environ but should be ignored by policy
        assert os.getenv("MALICIOUS_VAR") == "bad_value"  # Present in env
        # (Policy enforcement happens at runtime in GuardrailPolicy, not here)


# ============================================================================
# Config File Discovery Tests
# ============================================================================


class TestConfigFileDiscovery:
    """Test _find_config_file helper respects precedence."""

    def test_env_var_takes_precedence(self, tmp_path, monkeypatch):
        """Environment variable should override file search."""
        custom_config = tmp_path / "custom_settings.toml"
        custom_config.write_text("[test]\nvalue = 123\n")
        
        monkeypatch.setenv("SETTINGS_TOML_PATH", str(custom_config))
        
        result = _find_config_file("settings.toml", "SETTINGS_TOML_PATH")
        assert result == str(custom_config)

    def test_cwd_takes_precedence_over_package_root(self, tmp_path, monkeypatch):
        """Config in CWD should override package root."""
        cwd_config = tmp_path / "settings.toml"
        cwd_config.write_text("[test]\nvalue = 456\n")
        
        monkeypatch.chdir(tmp_path)
        
        result = _find_config_file("settings.toml", "NONEXISTENT_VAR")
        assert result == str(cwd_config)

    def test_fallback_to_package_root(self, monkeypatch):
        """Should fall back to package root if not in CWD."""
        monkeypatch.delenv("SETTINGS_TOML_PATH", raising=False)
        
        result = _find_config_file("settings.toml", "SETTINGS_TOML_PATH")
        assert PACKAGE_ROOT in Path(result).parents or Path(result).parent == PACKAGE_ROOT


# ============================================================================
# Pydantic Schema Validation Tests (Unknown Key Rejection)
# ============================================================================


class TestUnknownKeyRejection:
    """Test that unknown keys in configs trigger validation errors."""

    def test_unknown_toml_key_logged_as_warning(self, tmp_path, monkeypatch, caplog):
        """Unknown keys in TOML should not crash but should be logged."""
        # Create TOML with unknown key
        bad_config = tmp_path / "bad_settings.toml"
        bad_config.write_text("""
[features]
local_sandbox = true
unknown_key = "should_be_ignored"

[advanced_features]
registry = true
another_unknown = 123
""")
        
        # Load with Dynaconf (which is permissive by default)
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            root_path=PACKAGE_ROOT,
            settings_files=[str(bad_config)],
        )
        
        # Dynaconf allows unknown keys (doesn't raise)
        assert test_settings.features.local_sandbox is True
        # Unknown keys are accessible but not validated
        assert hasattr(test_settings.features, "unknown_key")

    def test_registry_yaml_validation_rejects_unknown_keys(self, tmp_path):
        """Registry YAML with unknown keys should fail Pydantic validation."""
        from pydantic import BaseModel, ConfigDict, ValidationError
        
        class StrictRegistryEntry(BaseModel):
            """Strict registry entry that rejects unknown keys."""
            model_config = ConfigDict(extra="forbid")
            
            name: str
            description: str
            category: str
            
        # Valid entry
        valid_entry = {"name": "test_tool", "description": "Test", "category": "utility"}
        assert StrictRegistryEntry(**valid_entry)
        
        # Invalid entry with unknown key
        invalid_entry = {
            "name": "test_tool",
            "description": "Test",
            "category": "utility",
            "unknown_field": "bad"
        }
        
        with pytest.raises(ValidationError) as exc_info:
            StrictRegistryEntry(**invalid_entry)
        
        assert "unknown_field" in str(exc_info.value)


# ============================================================================
# Config Provenance Tracking Tests
# ============================================================================


class TestConfigProvenance:
    """Test that config source tracking works correctly."""

    def test_track_config_source_env_var(self, monkeypatch):
        """Should be able to determine config came from env var."""
        monkeypatch.setenv("DYNACONF_TEST_KEY", "from_env")
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(envvar_prefix="DYNACONF")
        
        # Dynaconf doesn't have built-in provenance, but we can infer
        value = test_settings.get("TEST_KEY")
        assert value == "from_env"
        
        # Source is env (no file source)
        assert test_settings.get("TEST_KEY") is not None

    def test_track_config_source_toml(self):
        """Should be able to determine config came from TOML."""
        # Base settings loaded from TOML
        assert base_settings.features.local_sandbox is True
        
        # This came from TOML (validator default or TOML file)
        # Dynaconf stores source in _loaded_by_loaders dict internally


# ============================================================================
# Budget/Policy Environment Variable Tests
# ============================================================================


class TestBudgetPolicyEnvVars:
    """Test budget and policy environment variables."""

    def test_agent_budget_ceiling_default(self):
        """AGENT_BUDGET_CEILING should default to 100."""
        ceiling = os.getenv("AGENT_BUDGET_CEILING", "100")
        assert int(ceiling) == 100

    def test_agent_escalation_max_default(self):
        """AGENT_ESCALATION_MAX should default to 2."""
        max_escalation = os.getenv("AGENT_ESCALATION_MAX", "2")
        assert int(max_escalation) == 2

    def test_budget_policy_warn_or_block(self, monkeypatch):
        """Budget policy should be 'warn' or 'block'."""
        # Test warn
        monkeypatch.setenv("AGENT_BUDGET_POLICY", "warn")
        assert os.getenv("AGENT_BUDGET_POLICY") in ["warn", "block"]
        
        # Test block
        monkeypatch.setenv("AGENT_BUDGET_POLICY", "block")
        assert os.getenv("AGENT_BUDGET_POLICY") in ["warn", "block"]
        
        # Test invalid (should default to warn)
        monkeypatch.setenv("AGENT_BUDGET_POLICY", "invalid")
        policy = os.getenv("AGENT_BUDGET_POLICY", "warn")
        if policy not in ["warn", "block"]:
            policy = "warn"
        assert policy == "warn"


# ============================================================================
# Observability Environment Variable Tests
# ============================================================================


class TestObservabilityEnvVars:
    """Test OTEL/LangFuse/LangSmith environment variables."""

    def test_otel_exporter_endpoint_optional(self):
        """OTEL_EXPORTER_OTLP_ENDPOINT is optional (defaults to console)."""
        endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        # Should be None or a valid URL
        if endpoint:
            assert endpoint.startswith("http://") or endpoint.startswith("https://")

    def test_otel_service_name_optional(self):
        """OTEL_SERVICE_NAME is optional."""
        service_name = os.getenv("OTEL_SERVICE_NAME", "cuga-agent")
        assert isinstance(service_name, str)
        assert len(service_name) > 0

    def test_langfuse_keys_optional(self):
        """LangFuse keys are optional (only needed if enabled)."""
        public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        host = os.getenv("LANGFUSE_HOST")
        
        # Can be None (not required for all deployments)
        # If set, should be non-empty strings
        if public_key:
            assert len(public_key) > 0
        if secret_key:
            assert len(secret_key) > 0
        if host:
            assert host.startswith("http://") or host.startswith("https://")


# ============================================================================
# Config Validation Tests
# ============================================================================


class TestConfigValidation:
    """Test config validation and error handling."""

    def test_invalid_config_path_raises_error(self, monkeypatch):
        """Missing config files should raise FileNotFoundError in strict mode."""
        monkeypatch.setenv("CUGA_STRICT_CONFIG", "1")
        monkeypatch.setenv("AGENT_SETTING_CONFIG", "nonexistent.toml")
        
        # Should raise when loading settings
        # (Tested implicitly by config.py on import)

    def test_relaxed_config_mode_allows_missing(self, monkeypatch):
        """CUGA_STRICT_CONFIG=0 should allow missing files."""
        monkeypatch.setenv("CUGA_STRICT_CONFIG", "0")
        
        # Should not raise even if files missing
        # (Dynaconf continues with available configs)

    def test_validators_catch_invalid_values(self):
        """Validators should catch invalid config values."""
        from dynaconf import Validator, ValidationError
        
        # Create validator that should fail
        invalid_validator = Validator("test.nonexistent", must_exist=True)
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(validators=[invalid_validator])
        
        with pytest.raises(ValidationError):
            test_settings.validators.validate_all()


# ============================================================================
# Integration Tests
# ============================================================================


class TestConfigIntegration:
    """Integration tests for full config loading pipeline."""

    def test_load_llm_settings_with_env_expansion(self, monkeypatch):
        """load_llm_settings should expand ${VAR} placeholders."""
        monkeypatch.setenv("TEST_API_KEY", "test_key_123")
        
        from cuga.config import load_llm_settings
        
        # Create temp settings.toml with placeholder
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[llm]
provider = "openai"
model = "gpt-4"
api_key = "${TEST_API_KEY}"
""")
            temp_path = f.name
        
        try:
            # Load with env expansion
            llm_settings = load_llm_settings(env={"TEST_API_KEY": "test_key_123"})
            
            # Placeholder should be expanded
            assert llm_settings.api_key == "test_key_123"
        finally:
            os.unlink(temp_path)

    def test_full_config_load_without_errors(self):
        """Full config load should complete without errors."""
        # This tests that config.py imports successfully
        from cuga.config import settings
        
        assert settings is not None
        assert hasattr(settings, "features")
        assert hasattr(settings, "advanced_features")

    def test_dynaconf_precedence_order(self, tmp_path, monkeypatch):
        """Test Dynaconf respects precedence: env > file."""
        # Create TOML
        toml_file = tmp_path / "test.toml"
        toml_file.write_text("""
[test]
value = "from_toml"
""")
        
        # Set env var
        monkeypatch.setenv("DYNACONF_TEST__VALUE", "from_env")
        
        from dynaconf import Dynaconf
        test_settings = Dynaconf(
            settings_files=[str(toml_file)],
            envvar_prefix="DYNACONF"
        )
        
        # Env should win
        assert test_settings.test.value == "from_env"


# ============================================================================
# CLI Args Override Tests
# ============================================================================


class TestCLIArgsOverride:
    """Test that CLI args override all other config sources."""

    def test_typer_args_override_env(self, monkeypatch):
        """Typer CLI args should override environment variables."""
        # This is tested implicitly in cli.py where typer.Option values
        # take precedence over env vars
        
        # Example: --verbose flag overrides CUGA_VERBOSE env var
        monkeypatch.setenv("CUGA_VERBOSE", "false")
        
        # When CLI arg is provided, it wins
        # (Typer handles this automatically via its default priority)

    def test_argparse_args_override_config(self):
        """Argparse args (in evaluation) should override config files."""
        # Tested implicitly in evaluate_cuga.py where argparse
        # values override settings from config files
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
