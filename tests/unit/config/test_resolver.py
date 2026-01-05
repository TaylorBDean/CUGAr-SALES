"""
Unit tests for ConfigResolver

Tests:
- Precedence order (CLI > ENV > DOTENV > YAML > TOML > DEFAULT > HARDCODED)
- Deep merge algorithm for nested dicts
- Provenance tracking (which layer provided which value)
- Missing file handling (warnings, not errors)
- Environment variable parsing (prefixes, nested keys)
- ConfigResolver.validate_all() with fail_fast and collect_all modes
- Source loading and caching behavior
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from cuga.config.resolver import (
    ConfigLayer,
    ConfigResolver,
    ConfigValue,
    DefaultSource,
    DotEnvSource,
    EnvSource,
    TOMLSource,
    YAMLSource,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create temporary config directory with sample files."""
    config_dir = tmp_path / "config"
    config_dir.mkdir()

    # Create sample YAML config
    yaml_config = config_dir / "test.yaml"
    yaml_config.write_text(
        """
llm:
  model: granite-4-h-small
  temperature: 0.7
  provider: watsonx

agent:
  max_retries: 3
  timeout: 300
"""
    )

    # Create sample TOML config
    toml_config = config_dir / "settings.toml"
    toml_config.write_text(
        """
[llm]
model = "gpt-4o"
max_tokens = 4096

[agent]
timeout = 600
"""
    )

    # Create sample .env file
    env_file = config_dir / ".env"
    env_file.write_text(
        """
CUGA_PROFILE=production
AGENT__MAX_RETRIES=5
LLM__MODEL=claude-3-sonnet
"""
    )

    # Create defaults directory
    defaults_dir = config_dir / "defaults"
    defaults_dir.mkdir()
    default_config = defaults_dir / "defaults.yaml"
    default_config.write_text(
        """
llm:
  model: default-model
  temperature: 1.0
  max_tokens: 2048

agent:
  max_retries: 1
  timeout: 120
"""
    )

    return config_dir


@pytest.fixture
def clean_env():
    """Clean environment before each test."""
    original_env = dict(os.environ)
    yield
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


# ---------------------------------------------------------------------------
# Test ConfigLayer Precedence
# ---------------------------------------------------------------------------


def test_config_layer_precedence():
    """Test that ConfigLayer enum has correct precedence ordering."""
    assert ConfigLayer.CLI > ConfigLayer.ENV
    assert ConfigLayer.ENV > ConfigLayer.DOTENV
    assert ConfigLayer.DOTENV > ConfigLayer.YAML
    assert ConfigLayer.YAML > ConfigLayer.TOML
    assert ConfigLayer.TOML > ConfigLayer.DEFAULT
    assert ConfigLayer.DEFAULT > ConfigLayer.HARDCODED

    # Verify numeric values
    assert ConfigLayer.CLI == 7
    assert ConfigLayer.ENV == 6
    assert ConfigLayer.DOTENV == 5
    assert ConfigLayer.YAML == 4
    assert ConfigLayer.TOML == 3
    assert ConfigLayer.DEFAULT == 2
    assert ConfigLayer.HARDCODED == 1


def test_config_value_creation():
    """Test ConfigValue dataclass creation and string representation."""
    value = ConfigValue(
        value="granite-4-h-small",
        layer=ConfigLayer.ENV,
        source="WATSONX_MODEL",
        path="llm.model",
    )

    assert value.value == "granite-4-h-small"
    assert value.layer == ConfigLayer.ENV
    assert value.source == "WATSONX_MODEL"
    assert value.path == "llm.model"

    # Test string representation
    str_repr = str(value)
    assert "llm.model = granite-4-h-small" in str_repr
    assert "ENV" in str_repr
    assert "WATSONX_MODEL" in str_repr


# ---------------------------------------------------------------------------
# Test EnvSource
# ---------------------------------------------------------------------------


def test_env_source_basic(clean_env):
    """Test EnvSource loads environment variables."""
    os.environ["CUGA_MODEL"] = "granite"
    os.environ["AGENT__TIMEOUT"] = "300"

    source = EnvSource(prefixes=["CUGA_", "AGENT_"])
    data = source.load()

    assert data["cuga_model"] == "granite"
    assert data["agent"]["timeout"] == "300"
    assert source.layer == ConfigLayer.ENV


def test_env_source_nested_keys(clean_env):
    """Test EnvSource converts double underscore to nested dict."""
    os.environ["AGENT__LLM__MODEL"] = "gpt-4o"
    os.environ["AGENT__LLM__TEMPERATURE"] = "0.7"

    source = EnvSource(prefixes=["AGENT_"])
    data = source.load()

    assert data["agent"]["llm"]["model"] == "gpt-4o"
    assert data["agent"]["llm"]["temperature"] == "0.7"


def test_env_source_no_prefix_filter(clean_env):
    """Test EnvSource without prefix filter includes all env vars."""
    os.environ["CUSTOM_VAR"] = "value"
    os.environ["ANOTHER_VAR"] = "123"

    source = EnvSource()  # No prefixes
    data = source.load()

    # Should include both custom vars
    assert "custom_var" in data
    assert "another_var" in data


# ---------------------------------------------------------------------------
# Test DotEnvSource
# ---------------------------------------------------------------------------


def test_dotenv_source_basic(temp_config_dir):
    """Test DotEnvSource parses .env files."""
    source = DotEnvSource(temp_config_dir / ".env")
    data = source.load()

    assert data["cuga_profile"] == "production"
    assert data["agent"]["max_retries"] == "5"
    assert data["llm"]["model"] == "claude-3-sonnet"
    assert source.layer == ConfigLayer.DOTENV


def test_dotenv_source_missing_file(tmp_path):
    """Test DotEnvSource handles missing files gracefully."""
    source = DotEnvSource(tmp_path / "nonexistent.env")
    data = source.load()

    assert data == {}


def test_dotenv_source_comments_and_quotes(tmp_path):
    """Test DotEnvSource handles comments and quoted values."""
    env_file = tmp_path / ".env"
    env_file.write_text(
        """
# Comment line
KEY1=value1
KEY2="quoted value"
KEY3='single quoted'

# Another comment
KEY4=value4
"""
    )

    source = DotEnvSource(env_file)
    data = source.load()

    assert data["key1"] == "value1"
    assert data["key2"] == "quoted value"
    assert data["key3"] == "single quoted"
    assert data["key4"] == "value4"


# ---------------------------------------------------------------------------
# Test YAMLSource
# ---------------------------------------------------------------------------


def test_yaml_source_basic(temp_config_dir):
    """Test YAMLSource loads YAML files."""
    source = YAMLSource(temp_config_dir / "test.yaml")
    data = source.load()

    assert data["llm"]["model"] == "granite-4-h-small"
    assert data["llm"]["temperature"] == 0.7
    assert data["agent"]["max_retries"] == 3
    assert source.layer == ConfigLayer.YAML


def test_yaml_source_missing_file(tmp_path):
    """Test YAMLSource handles missing files gracefully."""
    source = YAMLSource(tmp_path / "nonexistent.yaml")
    data = source.load()

    assert data == {}


# ---------------------------------------------------------------------------
# Test TOMLSource
# ---------------------------------------------------------------------------


def test_toml_source_basic(temp_config_dir):
    """Test TOMLSource loads TOML files."""
    source = TOMLSource(temp_config_dir / "settings.toml")
    data = source.load()

    assert data["llm"]["model"] == "gpt-4o"
    assert data["llm"]["max_tokens"] == 4096
    assert data["agent"]["timeout"] == 600
    assert source.layer == ConfigLayer.TOML


def test_toml_source_missing_file(tmp_path):
    """Test TOMLSource handles missing files gracefully."""
    source = TOMLSource(tmp_path / "nonexistent.toml")
    data = source.load()

    assert data == {}


# ---------------------------------------------------------------------------
# Test DefaultSource
# ---------------------------------------------------------------------------


def test_default_source_basic(temp_config_dir):
    """Test DefaultSource loads and merges all YAML files in directory."""
    source = DefaultSource(temp_config_dir / "defaults")
    data = source.load()

    assert data["llm"]["model"] == "default-model"
    assert data["llm"]["temperature"] == 1.0
    assert data["agent"]["max_retries"] == 1
    assert source.layer == ConfigLayer.DEFAULT


def test_default_source_multiple_files(tmp_path):
    """Test DefaultSource merges multiple YAML files."""
    defaults_dir = tmp_path / "defaults"
    defaults_dir.mkdir()

    # Create multiple default files
    (defaults_dir / "defaults1.yaml").write_text("llm:\n  model: model1\n")
    (defaults_dir / "defaults2.yaml").write_text("agent:\n  timeout: 120\n")

    source = DefaultSource(defaults_dir)
    data = source.load()

    assert data["llm"]["model"] == "model1"
    assert data["agent"]["timeout"] == 120


# ---------------------------------------------------------------------------
# Test ConfigResolver Precedence
# ---------------------------------------------------------------------------


def test_resolver_precedence_yaml_over_toml(temp_config_dir):
    """Test YAML (layer 4) has higher precedence than TOML (layer 3)."""
    resolver = ConfigResolver()
    resolver.add_source(TOMLSource(temp_config_dir / "settings.toml"))  # Layer 3
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))  # Layer 4
    resolver.resolve()

    # YAML should win for overlapping keys
    model = resolver.get_value("llm.model")
    assert model == "granite-4-h-small"  # From YAML, not "gpt-4o" from TOML

    # TOML should provide non-overlapping keys
    max_tokens = resolver.get_value("llm.max_tokens")
    assert max_tokens == 4096  # From TOML


def test_resolver_precedence_env_over_yaml(temp_config_dir, clean_env):
    """Test ENV (layer 6) has higher precedence than YAML (layer 4)."""
    os.environ["LLM__MODEL"] = "env-model"

    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))  # Layer 4
    resolver.add_source(EnvSource(prefixes=["LLM_"]))  # Layer 6
    resolver.resolve()

    # ENV should win
    model = resolver.get_value("llm.model")
    assert model == "env-model"  # From ENV, not "granite-4-h-small" from YAML


def test_resolver_precedence_dotenv_over_yaml(temp_config_dir):
    """Test DOTENV (layer 5) has higher precedence than YAML (layer 4)."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))  # Layer 4
    resolver.add_source(DotEnvSource(temp_config_dir / ".env"))  # Layer 5
    resolver.resolve()

    # DOTENV should win for agent.max_retries
    max_retries = resolver.get_value("agent.max_retries")
    assert max_retries == "5"  # From .env, not 3 from YAML


def test_resolver_full_precedence_stack(temp_config_dir, clean_env):
    """Test complete precedence stack: CLI > ENV > DOTENV > YAML > TOML > DEFAULT."""
    os.environ["AGENT__TIMEOUT"] = "999"

    resolver = ConfigResolver()
    resolver.add_source(DefaultSource(temp_config_dir / "defaults"))  # Layer 2
    resolver.add_source(TOMLSource(temp_config_dir / "settings.toml"))  # Layer 3
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))  # Layer 4
    resolver.add_source(DotEnvSource(temp_config_dir / ".env"))  # Layer 5
    resolver.add_source(EnvSource(prefixes=["AGENT_"]))  # Layer 6
    resolver.resolve()

    # ENV should win for agent.timeout
    timeout = resolver.get_value("agent.timeout")
    assert timeout == "999"  # From ENV

    # DOTENV should win for agent.max_retries
    max_retries = resolver.get_value("agent.max_retries")
    assert max_retries == "5"  # From DOTENV

    # YAML should win for llm.temperature (not in ENV/DOTENV)
    temperature = resolver.get_value("llm.temperature")
    assert temperature == 0.7  # From YAML


# ---------------------------------------------------------------------------
# Test Provenance Tracking
# ---------------------------------------------------------------------------


def test_resolver_provenance_tracking(temp_config_dir):
    """Test resolver tracks which layer provided each value."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))
    resolver.resolve()

    # Get ConfigValue with provenance
    config_value = resolver.get("llm.model")
    assert config_value.value == "granite-4-h-small"
    assert config_value.layer == ConfigLayer.YAML
    assert "test.yaml" in config_value.source
    assert config_value.path == "llm.model"


def test_resolver_get_provenance(temp_config_dir):
    """Test get_provenance() returns human-readable string."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))
    resolver.resolve()

    provenance = resolver.get_provenance("llm.model")
    assert "llm.model = granite-4-h-small" in provenance
    assert "YAML" in provenance
    assert "test.yaml" in provenance


def test_resolver_dump_all_provenance(temp_config_dir):
    """Test dump() returns all config with provenance."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(temp_config_dir / "test.yaml"))
    resolver.resolve()

    dump = resolver.dump()
    assert isinstance(dump, dict)
    assert len(dump) > 0
    assert "llm.model" in dump
    assert "granite-4-h-small" in dump["llm.model"]


# ---------------------------------------------------------------------------
# Test Deep Merge
# ---------------------------------------------------------------------------


def test_resolver_deep_merge_dicts(tmp_path):
    """Test resolver deep merges nested dicts from multiple sources."""
    # Create two YAML files with partial overlaps
    yaml1 = tmp_path / "config1.yaml"
    yaml1.write_text("llm:\n  model: model1\n  temperature: 0.5\n")

    yaml2 = tmp_path / "config2.yaml"
    yaml2.write_text("llm:\n  temperature: 0.7\n  max_tokens: 4096\n")

    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(yaml1))  # Loaded first
    resolver.add_source(YAMLSource(yaml2))  # Loaded second (same layer, so order matters)
    resolver.resolve()

    # yaml2 should override temperature but preserve model from yaml1
    assert resolver.get_value("llm.model") == "model1"  # From yaml1
    assert resolver.get_value("llm.temperature") == 0.7  # From yaml2 (override)
    assert resolver.get_value("llm.max_tokens") == 4096  # From yaml2


# ---------------------------------------------------------------------------
# Test Missing Files and Error Handling
# ---------------------------------------------------------------------------


def test_resolver_handles_missing_files():
    """Test resolver handles missing config files gracefully."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource("/nonexistent/path/config.yaml"))
    resolver.add_source(TOMLSource("/nonexistent/path/settings.toml"))
    resolver.resolve()

    # Should resolve without errors (empty config)
    keys = resolver.keys()
    assert keys == []


def test_resolver_get_with_default():
    """Test resolver.get() returns default for missing keys."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource("/nonexistent.yaml"))
    resolver.resolve()

    value = resolver.get("missing.key", default="fallback")
    assert value.value == "fallback"
    assert value.layer == ConfigLayer.HARDCODED


# ---------------------------------------------------------------------------
# Test validate_all() Integration
# ---------------------------------------------------------------------------


def test_resolver_validate_all_pass(tmp_path):
    """Test validate_all() passes with valid registry config."""
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(
        """
tools:
  file_search:
    module: "cuga.modular.tools.file_search"
    handler: "search_files"
    description: "Search for files matching patterns"
    sandbox_profile: "py_slim"
    mounts:
      - "/workdir:/workdir:ro"
"""
    )

    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(registry_file))
    resolver.resolve()

    # Should not raise
    errors = resolver.validate_all(fail_fast=True)
    assert errors == {}


def test_resolver_validate_all_fail_fast(tmp_path):
    """Test validate_all() raises on first error with fail_fast=True."""
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(
        """
tools:
  bad_tool:
    module: "evil.tools.backdoor"
    handler: "run"
    description: "Bad tool"
    sandbox_profile: "py_slim"
"""
    )

    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(registry_file))
    resolver.resolve()

    # Should raise ValueError
    with pytest.raises(ValueError) as exc_info:
        resolver.validate_all(fail_fast=True)

    assert "allowlist" in str(exc_info.value).lower()


def test_resolver_validate_all_collect_errors(tmp_path):
    """Test validate_all() collects all errors with fail_fast=False."""
    registry_file = tmp_path / "registry.yaml"
    registry_file.write_text(
        """
tools:
  bad_tool:
    module: "evil.tools.backdoor"
    handler: "run"
    description: "Bad tool"
    sandbox_profile: "py_slim"
    mounts:
      - "/tmp:invalid"
"""
    )

    resolver = ConfigResolver()
    resolver.add_source(YAMLSource(registry_file))
    resolver.resolve()

    # Should collect all errors
    errors = resolver.validate_all(fail_fast=False)
    assert "registry" in errors
    assert len(errors["registry"]) > 0


def test_resolver_must_resolve_before_access():
    """Test resolver raises if accessing values before resolve()."""
    resolver = ConfigResolver()
    resolver.add_source(YAMLSource("/tmp/config.yaml"))

    # Should raise RuntimeError
    with pytest.raises(RuntimeError, match="resolve.*must be called"):
        resolver.get("some.key")

    with pytest.raises(RuntimeError, match="resolve.*must be called"):
        resolver.get_value("some.key")

    with pytest.raises(RuntimeError, match="resolve.*must be called"):
        resolver.keys()
