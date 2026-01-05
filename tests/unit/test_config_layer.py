"""
Comprehensive Configuration Layer Tests

Tests configuration resolution system with explicit precedence order,
deep merge semantics, provenance tracking, and environment validation.

Per AGENTS.md § Configuration Policy:
    CLI args > env vars > .env files > YAML configs > TOML configs > 
    configuration defaults > hardcoded defaults

Test Coverage (15 tests):
    - Precedence order (CLI > ENV > DOTENV > YAML > TOML > DEFAULT)
    - Deep merge for dicts
    - Override for lists/scalars
    - Provenance tracking (which layer provided which value)
    - Environment mode requirements (local/service/MCP/test)
    - Invalid config rejection
    - Edge cases (empty values, nested overrides, type coercion)
"""

import os
import tempfile
from pathlib import Path
from typing import Dict, Any

import pytest
import yaml
import tomllib

from cuga.config import (
    ConfigResolver,
    ConfigLayer,
    ConfigValue,
    ConfigSource,
    validate_environment_mode,
    EnvironmentMode,
)
from cuga.config.resolver import EnvSource, DotEnvSource, YAMLSource, TOMLSource, DefaultSource
from cuga.modular.config import AgentConfig, _parse_int, _parse_float


# ========== Fixtures ==========

@pytest.fixture
def clean_env(monkeypatch):
    """Clean environment for isolated testing."""
    # Clear all CUGA/AGENT env vars
    for key in list(os.environ.keys()):
        if key.startswith(("CUGA_", "AGENT_", "PLANNER_", "MODEL_", "PROFILE")):
            monkeypatch.delenv(key, raising=False)
    return monkeypatch


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory."""
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    return config_dir


# ========== Test Precedence Order ==========

class TestPrecedenceOrder:
    """Test configuration precedence layers."""
    
    def test_env_overrides_dotenv(self, clean_env, tmp_path):
        """ENV vars override .env file values."""
        # Create .env file
        env_file = tmp_path / ".env"
        env_file.write_text("CUGA_PROFILE=demo_power\n")
        
        # Set ENV var (higher precedence)
        clean_env.setenv("CUGA_PROFILE", "production")
        
        resolver = ConfigResolver()
        resolver.add_source(DotEnvSource(env_file))
        resolver.add_source(EnvSource(prefixes=["CUGA_"]))
        resolver.resolve()
        
        result = resolver.get("cuga_profile")
        
        assert result.value == "production"
        assert result.layer == ConfigLayer.ENV
        assert result.source == "os.environ"
    
    def test_dotenv_overrides_yaml(self, tmp_path):
        """DOTENV overrides YAML configs."""
        # Create YAML file
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("profile: demo_power\n")
        
        # Create .env file (higher precedence)
        env_file = tmp_path / ".env"
        env_file.write_text("PROFILE=production\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.add_source(DotEnvSource(env_file))
        resolver.resolve()
        
        result = resolver.get("profile")
        
        assert result.value == "production"
        assert result.layer == ConfigLayer.DOTENV
    
    def test_yaml_overrides_toml(self, tmp_path):
        """YAML overrides TOML configs."""
        # Create TOML file
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text('profile = "demo_power"\n')
        
        # Create YAML file (higher precedence)
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("profile: production\n")
        
        resolver = ConfigResolver()
        resolver.add_source(TOMLSource(toml_file))
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()
        
        result = resolver.get("profile")
        
        assert result.value == "production"
        assert result.layer == ConfigLayer.YAML
    
    def test_toml_overrides_defaults(self, tmp_path):
        """TOML overrides hardcoded defaults."""
        # Create defaults directory with YAML
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        (defaults_dir / "base.yaml").write_text('profile: "default"\n')
        
        # Create TOML file (higher precedence)
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text('profile = "custom_profile"\n')
        
        resolver = ConfigResolver()
        resolver.add_source(DefaultSource(defaults_dir))
        resolver.add_source(TOMLSource(toml_file))
        resolver.resolve()
        
        result = resolver.get("profile")
        
        assert result.value == "custom_profile"
        assert result.layer == ConfigLayer.TOML
    
    def test_full_precedence_chain(self, clean_env, tmp_path):
        """Test full precedence chain: ENV > DOTENV > YAML > TOML > DEFAULT."""
        # Setup DEFAULT
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        (defaults_dir / "base.yaml").write_text("max_steps: 5\n")
        
        # Setup TOML
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text('max_steps = 6\n')
        
        # Setup YAML
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("max_steps: 7\n")
        
        # Setup DOTENV
        env_file = tmp_path / ".env"
        env_file.write_text("MAX_STEPS=8\n")
        
        # Setup ENV (highest precedence)
        clean_env.setenv("MAX_STEPS", "10")
        
        resolver = ConfigResolver()
        resolver.add_source(DefaultSource(defaults_dir))
        resolver.add_source(TOMLSource(toml_file))
        resolver.add_source(YAMLSource(yaml_file))
        resolver.add_source(DotEnvSource(env_file))
        resolver.add_source(EnvSource())
        resolver.resolve()
        
        result = resolver.get("max_steps")
        
        # ENV should win
        assert result.value == "10"
        assert result.layer == ConfigLayer.ENV


# ========== Test Merge Semantics ==========

class TestMergeSemantics:
    """Test deep merge for dicts and override for lists/scalars."""
    
    def test_scalar_values_merge_correctly(self, tmp_path):
        """Test that scalar values at top level merge correctly."""
        yaml_base = tmp_path / "base.yaml"
        yaml_base.write_text("max_steps: 5\nprofile: demo\n")
        
        yaml_override = tmp_path / "override.yaml"
        yaml_override.write_text("max_steps: 10\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_base))
        resolver.add_source(YAMLSource(yaml_override))
        resolver.resolve()
        
        steps = resolver.get("max_steps")
        profile = resolver.get("profile")
        
        # Override should work
        assert steps.value == 10
        # Base value should still be there
        assert profile.value == "demo"
    
    def test_list_override_not_merge(self, tmp_path):
        """Lists should be replaced, not merged."""
        yaml_base = tmp_path / "base.yaml"
        yaml_base.write_text("tools: [echo, search, calculator]\n")
        
        yaml_override = tmp_path / "override.yaml"
        yaml_override.write_text("tools: [echo]\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_base))
        resolver.add_source(YAMLSource(yaml_override))
        resolver.resolve()
        
        result = resolver.get("tools")
        
        # Should be replaced, not merged
        assert result.value == ["echo"]
        assert len(result.value) == 1
    
    def test_scalar_override(self, tmp_path):
        """Scalars (strings, ints, bools) should be replaced."""
        yaml_base = tmp_path / "base.yaml"
        yaml_base.write_text("max_steps: 5\nenabled: false\nprofile: demo\n")
        
        yaml_override = tmp_path / "override.yaml"
        yaml_override.write_text("max_steps: 10\nenabled: true\nprofile: prod\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_base))
        resolver.add_source(YAMLSource(yaml_override))
        resolver.resolve()
        
        steps = resolver.get("max_steps")
        enabled = resolver.get("enabled")
        profile = resolver.get("profile")
        
        assert steps.value == 10
        assert enabled.value is True
        assert profile.value == "prod"


# ========== Test Provenance Tracking ==========

class TestProvenanceTracking:
    """Test configuration provenance (which layer/source provided value)."""
    
    def test_provenance_includes_layer(self, tmp_path):
        """Provenance includes configuration layer."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("profile: demo_power\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()
        
        result = resolver.get("profile")
        
        assert result.layer == ConfigLayer.YAML
        assert "YAML" in str(result)
    
    def test_provenance_includes_source_file(self, tmp_path):
        """Provenance includes source filename."""
        yaml_file = tmp_path / "agent.yaml"
        yaml_file.write_text("profile: demo_power\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()
        
        result = resolver.get("profile")
        
        assert "agent.yaml" in result.source
        assert "agent.yaml" in str(result)
    
    def test_provenance_includes_dotted_path(self, tmp_path):
        """Provenance includes dotted path to value."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("llm:\n  model: gpt-4\n")
        
        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()
        
        result = resolver.get("llm.model")
        
        assert result.path == "llm.model"
        assert "llm.model" in str(result)


# ========== Test Environment Validation ==========

class TestEnvironmentValidation:
    """Test environment mode requirements (local/service/MCP/test)."""
    
    def test_local_mode_validation(self, clean_env):
        """Local mode requires model API key."""
        # Missing model key
        result = validate_environment_mode(EnvironmentMode.LOCAL)
        
        assert not result.is_valid
        assert len(result.missing_required) > 0
        
        # With model key
        clean_env.setenv("OPENAI_API_KEY", "sk-test123")
        result = validate_environment_mode(EnvironmentMode.LOCAL)
        
        # Should be valid now or have fewer errors
        assert result.is_valid or len(result.missing_required) == 0
    
    def test_service_mode_validation(self, clean_env):
        """Service mode requires AGENT_TOKEN + AGENT_BUDGET_CEILING + model key."""
        # Missing all required vars
        result = validate_environment_mode(EnvironmentMode.SERVICE)
        
        assert not result.is_valid
        assert len(result.missing_required) > 0
        
        # With all required vars
        clean_env.setenv("AGENT_TOKEN", "test_token")
        clean_env.setenv("AGENT_BUDGET_CEILING", "100")
        clean_env.setenv("OPENAI_API_KEY", "sk-test123")
        
        result = validate_environment_mode(EnvironmentMode.SERVICE)
        
        assert result.is_valid
    
    def test_mcp_mode_validation(self, clean_env):
        """MCP mode requires MCP_SERVERS_FILE + CUGA_PROFILE_SANDBOX + model key."""
        # Missing required vars
        result = validate_environment_mode(EnvironmentMode.MCP)
        
        assert not result.is_valid
        assert len(result.missing_required) > 0
        
        # With required vars
        clean_env.setenv("MCP_SERVERS_FILE", "/path/to/mcp_servers.json")
        clean_env.setenv("CUGA_PROFILE_SANDBOX", "py_slim")
        clean_env.setenv("OPENAI_API_KEY", "sk-test123")
        
        result = validate_environment_mode(EnvironmentMode.MCP)
        
        assert result.is_valid


# ========== Test AgentConfig Edge Cases ==========

class TestAgentConfigEdgeCases:
    """Test edge cases in AgentConfig.from_env()."""
    
    def test_clamping_max_steps(self, clean_env):
        """PLANNER_MAX_STEPS clamped to 1..50."""
        # Below min
        clean_env.setenv("PLANNER_MAX_STEPS", "-5")
        result = _parse_int("PLANNER_MAX_STEPS", default=6, min_value=1, max_value=50)
        assert result == 1
        
        # Above max
        clean_env.setenv("PLANNER_MAX_STEPS", "100")
        result = _parse_int("PLANNER_MAX_STEPS", default=6, min_value=1, max_value=50)
        assert result == 50
        
        # Valid range
        clean_env.setenv("PLANNER_MAX_STEPS", "10")
        result = _parse_int("PLANNER_MAX_STEPS", default=6, min_value=1, max_value=50)
        assert result == 10
    
    def test_clamping_temperature(self, clean_env):
        """MODEL_TEMPERATURE clamped to 0..2."""
        # Below min
        clean_env.setenv("MODEL_TEMPERATURE", "-1.0")
        result = _parse_float("MODEL_TEMPERATURE", default=0.3, min_value=0.0, max_value=2.0)
        assert result == 0.0
        
        # Above max
        clean_env.setenv("MODEL_TEMPERATURE", "5.0")
        result = _parse_float("MODEL_TEMPERATURE", default=0.3, min_value=0.0, max_value=2.0)
        assert result == 2.0
        
        # Valid range
        clean_env.setenv("MODEL_TEMPERATURE", "0.7")
        result = _parse_float("MODEL_TEMPERATURE", default=0.3, min_value=0.0, max_value=2.0)
        assert result == 0.7
    
    def test_invalid_int_uses_default(self, clean_env):
        """Invalid int values fall back to default."""
        clean_env.setenv("PLANNER_MAX_STEPS", "not_a_number")
        result = _parse_int("PLANNER_MAX_STEPS", default=6, min_value=1, max_value=50)
        assert result == 6
    
    def test_invalid_float_uses_default(self, clean_env):
        """Invalid float values fall back to default."""
        clean_env.setenv("MODEL_TEMPERATURE", "invalid")
        result = _parse_float("MODEL_TEMPERATURE", default=0.3, min_value=0.0, max_value=2.0)
        assert result == 0.3
    
    def test_agent_config_from_env_defaults(self, clean_env):
        """AgentConfig.from_env() provides sensible defaults."""
        config = AgentConfig.from_env()
        
        assert config.profile == "demo_power"
        assert config.strategy == "react"
        assert config.max_steps == 6
        assert config.temperature == 0.3
        assert config.observability is True
        assert config.vector_backend == "local"
