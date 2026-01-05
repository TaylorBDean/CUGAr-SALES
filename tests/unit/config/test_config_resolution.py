"""Unit tests for ConfigResolver."""

import os
import tempfile
from pathlib import Path

import pytest

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


class TestConfigLayer:
    """Test ConfigLayer precedence ordering."""

    def test_precedence_ordering(self):
        """Verify precedence order: CLI > ENV > DOTENV > YAML > TOML > DEFAULT > HARDCODED."""
        assert ConfigLayer.CLI > ConfigLayer.ENV
        assert ConfigLayer.ENV > ConfigLayer.DOTENV
        assert ConfigLayer.DOTENV > ConfigLayer.YAML
        assert ConfigLayer.YAML > ConfigLayer.TOML
        assert ConfigLayer.TOML > ConfigLayer.DEFAULT
        assert ConfigLayer.DEFAULT > ConfigLayer.HARDCODED

    def test_layer_values(self):
        """Verify layer numeric values for correct sorting."""
        layers = [
            ConfigLayer.HARDCODED,
            ConfigLayer.DEFAULT,
            ConfigLayer.TOML,
            ConfigLayer.YAML,
            ConfigLayer.DOTENV,
            ConfigLayer.ENV,
            ConfigLayer.CLI,
        ]
        # Should already be sorted from lowest to highest
        assert layers == sorted(layers)


class TestConfigValue:
    """Test ConfigValue provenance tracking."""

    def test_config_value_creation(self):
        """Test basic ConfigValue creation."""
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
        assert value.timestamp is not None

    def test_config_value_string_repr(self):
        """Test human-readable string representation."""
        value = ConfigValue(
            value="granite-4-h-small",
            layer=ConfigLayer.ENV,
            source="WATSONX_MODEL",
            path="llm.model",
        )

        string_repr = str(value)
        assert "llm.model" in string_repr
        assert "granite-4-h-small" in string_repr
        assert "ENV" in string_repr
        assert "WATSONX_MODEL" in string_repr

    def test_config_value_immutable(self):
        """Test that ConfigValue is immutable (frozen dataclass)."""
        value = ConfigValue(
            value="test",
            layer=ConfigLayer.ENV,
            source="TEST_VAR",
            path="test.path",
        )

        with pytest.raises(AttributeError):
            value.value = "modified"


class TestEnvSource:
    """Test EnvSource loading."""

    def test_load_all_env_vars(self, monkeypatch):
        """Test loading all environment variables."""
        monkeypatch.setenv("TEST_VAR", "value1")
        monkeypatch.setenv("ANOTHER_VAR", "value2")

        source = EnvSource()
        config = source.load()

        assert "test_var" in config
        assert config["test_var"] == "value1"
        assert "another_var" in config
        assert config["another_var"] == "value2"

    def test_load_with_prefix_filter(self, monkeypatch):
        """Test loading only prefixed environment variables."""
        monkeypatch.setenv("CUGA_MODEL", "granite")
        monkeypatch.setenv("AGENT_TOKEN", "secret")
        monkeypatch.setenv("UNRELATED", "ignore")

        source = EnvSource(prefixes=["CUGA_", "AGENT_"])
        config = source.load()

        assert "cuga_model" in config
        assert "agent_token" in config
        assert "unrelated" not in config

    def test_nested_key_mapping(self, monkeypatch):
        """Test conversion of AGENT__LLM__MODEL to agent.llm.model."""
        monkeypatch.setenv("AGENT__LLM__MODEL", "granite-4-h-small")
        monkeypatch.setenv("AGENT__LLM__TEMPERATURE", "0.0")

        source = EnvSource(prefixes=["AGENT_"])
        config = source.load()

        assert "agent" in config
        assert "llm" in config["agent"]
        assert config["agent"]["llm"]["model"] == "granite-4-h-small"
        assert config["agent"]["llm"]["temperature"] == "0.0"

    def test_layer_and_source_name(self):
        """Test source metadata."""
        source = EnvSource()
        assert source.layer == ConfigLayer.ENV
        assert source.source_name == "os.environ"


class TestDotEnvSource:
    """Test DotEnvSource loading."""

    def test_load_dotenv_file(self, tmp_path):
        """Test loading .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text(
            """
# Comment line
WATSONX_API_KEY=test-key-123
WATSONX_PROJECT_ID=project-456

# Quoted values
MODEL_NAME="granite-4-h-small"
TEMPERATURE='0.0'
"""
        )

        source = DotEnvSource(env_file)
        config = source.load()

        assert config["watsonx_api_key"] == "test-key-123"
        assert config["watsonx_project_id"] == "project-456"
        assert config["model_name"] == "granite-4-h-small"  # Quotes removed
        assert config["temperature"] == "0.0"  # Quotes removed

    def test_nested_keys_from_dotenv(self, tmp_path):
        """Test nested key conversion from .env file."""
        env_file = tmp_path / ".env"
        env_file.write_text("AGENT__LLM__MODEL=granite-4-h-small\nAGENT__LLM__TEMPERATURE=0.0")

        source = DotEnvSource(env_file)
        config = source.load()

        assert config["agent"]["llm"]["model"] == "granite-4-h-small"
        assert config["agent"]["llm"]["temperature"] == "0.0"

    def test_missing_file_warning(self, tmp_path):
        """Test graceful handling of missing .env file."""
        non_existent = tmp_path / "nonexistent.env"
        source = DotEnvSource(non_existent)
        config = source.load()

        assert config == {}  # Empty dict, no crash

    def test_layer_and_source_name(self, tmp_path):
        """Test source metadata."""
        env_file = tmp_path / ".env"
        env_file.write_text("TEST=value")

        source = DotEnvSource(env_file)
        assert source.layer == ConfigLayer.DOTENV
        assert str(env_file) in source.source_name


class TestYAMLSource:
    """Test YAMLSource loading."""

    def test_load_yaml_file(self, tmp_path):
        """Test loading YAML configuration."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            """
llm:
  model: granite-4-h-small
  temperature: 0.0
  providers:
    - watsonx
    - openai
"""
        )

        source = YAMLSource(yaml_file)
        config = source.load()

        assert config["llm"]["model"] == "granite-4-h-small"
        assert config["llm"]["temperature"] == 0.0
        assert config["llm"]["providers"] == ["watsonx", "openai"]

    def test_missing_file_warning(self, tmp_path):
        """Test graceful handling of missing YAML file."""
        non_existent = tmp_path / "nonexistent.yaml"
        source = YAMLSource(non_existent)
        config = source.load()

        assert config == {}

    def test_layer_and_source_name(self, tmp_path):
        """Test source metadata."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("test: value")

        source = YAMLSource(yaml_file)
        assert source.layer == ConfigLayer.YAML
        assert str(yaml_file) in source.source_name


class TestTOMLSource:
    """Test TOMLSource loading."""

    def test_load_toml_file(self, tmp_path):
        """Test loading TOML configuration."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """
[llm]
model = "granite-4-h-small"
temperature = 0.0

[llm.providers]
watsonx = true
openai = false
"""
        )

        source = TOMLSource(toml_file)
        config = source.load()

        assert config["llm"]["model"] == "granite-4-h-small"
        assert config["llm"]["temperature"] == 0.0
        assert config["llm"]["providers"]["watsonx"] is True

    def test_missing_file_warning(self, tmp_path):
        """Test graceful handling of missing TOML file."""
        non_existent = tmp_path / "nonexistent.toml"
        source = TOMLSource(non_existent)
        config = source.load()

        assert config == {}

    def test_layer_and_source_name(self, tmp_path):
        """Test source metadata."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text("[test]\nvalue = 1")

        source = TOMLSource(toml_file)
        assert source.layer == ConfigLayer.TOML
        assert str(toml_file) in source.source_name


class TestDefaultSource:
    """Test DefaultSource loading from configurations/_shared/."""

    def test_load_single_default_file(self, tmp_path):
        """Test loading single default YAML file."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()

        (defaults_dir / "base.yaml").write_text(
            """
llm:
  model: default-model
  temperature: 0.5
"""
        )

        source = DefaultSource(defaults_dir)
        config = source.load()

        assert config["llm"]["model"] == "default-model"
        assert config["llm"]["temperature"] == 0.5

    def test_load_multiple_defaults_with_merge(self, tmp_path):
        """Test loading and merging multiple default files."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()

        (defaults_dir / "00_base.yaml").write_text(
            """
llm:
  model: base-model
  temperature: 0.5
"""
        )

        (defaults_dir / "01_override.yaml").write_text(
            """
llm:
  model: override-model
  max_tokens: 8192
"""
        )

        source = DefaultSource(defaults_dir)
        config = source.load()

        # Later file should override model
        assert config["llm"]["model"] == "override-model"
        # Temperature from first file preserved
        assert config["llm"]["temperature"] == 0.5
        # max_tokens from second file added
        assert config["llm"]["max_tokens"] == 8192

    def test_missing_directory_warning(self, tmp_path):
        """Test graceful handling of missing defaults directory."""
        non_existent = tmp_path / "nonexistent_defaults"
        source = DefaultSource(non_existent)
        config = source.load()

        assert config == {}

    def test_layer_and_source_name(self, tmp_path):
        """Test source metadata."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()

        source = DefaultSource(defaults_dir)
        assert source.layer == ConfigLayer.DEFAULT
        assert str(defaults_dir) in source.source_name


class TestConfigResolver:
    """Test ConfigResolver precedence and provenance."""

    def test_basic_resolution(self, tmp_path):
        """Test basic config resolution from single source."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("model: granite-4-h-small\ntemperature: 0.0")

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()

        assert resolver.get_value("model") == "granite-4-h-small"
        assert resolver.get_value("temperature") == 0.0

    def test_precedence_env_over_yaml(self, tmp_path, monkeypatch):
        """Test that ENV layer overrides YAML layer."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("model: yaml-model\ntemperature: 0.5")

        monkeypatch.setenv("MODEL", "env-model")

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.add_source(EnvSource())
        resolver.resolve()

        # ENV should win
        assert resolver.get_value("model") == "env-model"
        # Temperature from YAML preserved
        assert resolver.get_value("temperature") == 0.5

    def test_precedence_dotenv_over_toml(self, tmp_path):
        """Test that DOTENV layer overrides TOML layer."""
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text('model = "toml-model"\ntemperature = 0.5')

        env_file = tmp_path / ".env"
        env_file.write_text("MODEL=dotenv-model")

        resolver = ConfigResolver()
        resolver.add_source(TOMLSource(toml_file))
        resolver.add_source(DotEnvSource(env_file))
        resolver.resolve()

        # DOTENV should win
        assert resolver.get_value("model") == "dotenv-model"
        # Temperature from TOML preserved
        assert resolver.get_value("temperature") == 0.5

    def test_full_precedence_chain(self, tmp_path, monkeypatch):
        """Test complete precedence chain: ENV > DOTENV > YAML > TOML > DEFAULT."""
        # DEFAULT layer
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()
        (defaults_dir / "base.yaml").write_text("model: default-model\ntemperature: 0.5\ntimeout: 60")

        # TOML layer
        toml_file = tmp_path / "settings.toml"
        toml_file.write_text('model = "toml-model"\ntemperature = 0.4')

        # YAML layer
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("model: yaml-model")

        # DOTENV layer
        env_file = tmp_path / ".env"
        env_file.write_text("TEMPERATURE=0.0")

        # ENV layer
        monkeypatch.setenv("MODEL", "env-model")

        resolver = ConfigResolver()
        resolver.add_source(DefaultSource(defaults_dir))
        resolver.add_source(TOMLSource(toml_file))
        resolver.add_source(YAMLSource(yaml_file))
        resolver.add_source(DotEnvSource(env_file))
        resolver.add_source(EnvSource())
        resolver.resolve()

        # Highest precedence wins
        assert resolver.get_value("model") == "env-model"  # From ENV
        assert resolver.get_value("temperature") == "0.0"  # From DOTENV
        assert resolver.get_value("timeout") == 60  # From DEFAULT (only source)

    def test_provenance_tracking(self, tmp_path, monkeypatch):
        """Test that provenance correctly tracks value sources."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("model: yaml-model\ntemperature: 0.5")

        monkeypatch.setenv("MODEL", "env-model")

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.add_source(EnvSource())
        resolver.resolve()

        # Check provenance for model (from ENV)
        model_value = resolver.get("model")
        assert model_value.value == "env-model"
        assert model_value.layer == ConfigLayer.ENV
        assert model_value.source == "os.environ"

        # Check provenance for temperature (from YAML)
        temp_value = resolver.get("temperature")
        assert temp_value.value == 0.5
        assert temp_value.layer == ConfigLayer.YAML
        assert str(yaml_file) in temp_value.source

    def test_nested_config_deep_merge(self, tmp_path):
        """Test deep merge of nested configuration."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            """
llm:
  model: yaml-model
  temperature: 0.5
  providers:
    watsonx:
      enabled: true
"""
        )

        toml_file = tmp_path / "settings.toml"
        toml_file.write_text(
            """
[llm]
model = "toml-model"

[llm.providers.openai]
enabled = false
"""
        )

        resolver = ConfigResolver()
        resolver.add_source(TOMLSource(toml_file))
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()

        # YAML wins for model
        assert resolver.get_value("llm.model") == "yaml-model"
        # Temperature from YAML
        assert resolver.get_value("llm.temperature") == 0.5
        # Both providers present (deep merge)
        assert resolver.get_value("llm.providers.watsonx.enabled") is True
        assert resolver.get_value("llm.providers.openai.enabled") is False

    def test_get_with_default(self, tmp_path):
        """Test get() with default value for missing keys."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("model: granite-4-h-small")

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()

        # Existing key
        model = resolver.get("model")
        assert model.value == "granite-4-h-small"

        # Missing key with default
        timeout = resolver.get("timeout", default=60)
        assert timeout.value == 60
        assert timeout.layer == ConfigLayer.HARDCODED

    def test_keys_listing(self, tmp_path):
        """Test listing all resolved config keys."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text(
            """
llm:
  model: granite
  temperature: 0.0
"""
        )

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()

        keys = resolver.keys()
        assert "llm.model" in keys
        assert "llm.temperature" in keys
        assert len(keys) == 2

    def test_get_provenance_string(self, tmp_path, monkeypatch):
        """Test human-readable provenance strings."""
        monkeypatch.setenv("MODEL", "env-model")

        resolver = ConfigResolver()
        resolver.add_source(EnvSource())
        resolver.resolve()

        provenance = resolver.get_provenance("model")
        assert "model" in provenance
        assert "env-model" in provenance
        assert "ENV" in provenance
        assert "os.environ" in provenance

    def test_dump_all_provenance(self, tmp_path):
        """Test dumping all config with provenance."""
        yaml_file = tmp_path / "config.yaml"
        yaml_file.write_text("model: granite\ntemperature: 0.0")

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file))
        resolver.resolve()

        dump = resolver.dump()
        assert "model" in dump
        assert "temperature" in dump
        assert "granite" in dump["model"]
        assert "YAML" in dump["model"]

    def test_resolve_before_access_error(self):
        """Test that accessing values before resolve() raises error."""
        resolver = ConfigResolver()

        with pytest.raises(RuntimeError, match="resolve.*must be called"):
            resolver.get("model")

        with pytest.raises(RuntimeError, match="resolve.*must be called"):
            resolver.get_value("model")

        with pytest.raises(RuntimeError, match="resolve.*must be called"):
            resolver.keys()

    def test_cache_invalidation_on_add_source(self, tmp_path):
        """Test that cache is invalidated when adding new sources."""
        yaml_file1 = tmp_path / "config1.yaml"
        yaml_file1.write_text("model: model1")

        resolver = ConfigResolver()
        resolver.add_source(YAMLSource(yaml_file1))
        resolver.resolve()

        assert resolver.get_value("model") == "model1"

        # Add second source (should invalidate cache)
        yaml_file2 = tmp_path / "config2.yaml"
        yaml_file2.write_text("model: model2\ntemperature: 0.0")

        resolver.add_source(YAMLSource(yaml_file2))
        resolver.resolve()  # Must resolve again

        # Second YAML should override
        assert resolver.get_value("model") == "model2"
        assert resolver.get_value("temperature") == 0.0
