"""
Unified Configuration Resolver

Enforces explicit precedence order across configuration sources with
provenance tracking and observability.

Architecture:
- ConfigLayer: Enum defining precedence layers (CLI > ENV > DOTENV > YAML > TOML > DEFAULT)
- ConfigValue: Value + metadata (layer, source_file, timestamp)
- ConfigSource: Interface for loading config from different sources
- ConfigResolver: Main resolution engine with deep merge, validation, provenance

Usage:
    resolver = ConfigResolver()
    resolver.add_source(EnvSource())
    resolver.add_source(YAMLSource("configs/agent.yaml"))
    resolver.add_source(TOMLSource("settings.toml"))
    
    value = resolver.get("llm.model")
    # Returns: ConfigValue(value="granite-4-h-small", layer=ENV, source="WATSONX_MODEL")
    
    provenance = resolver.get_provenance("llm.model")
    # Returns: "llm.model = granite-4-h-small (from ENV via WATSONX_MODEL)"

See docs/configuration/CONFIG_RESOLUTION.md for complete specification.
"""

import os
import re
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import tomllib
import yaml
from loguru import logger


# ---------------------------------------------------------------------------
# Precedence Layer Definitions
# ---------------------------------------------------------------------------


class ConfigLayer(IntEnum):
    """
    Configuration precedence layers (higher value = higher precedence).
    
    Precedence order (highest to lowest):
        CLI (7) > ENV (6) > DOTENV (5) > YAML (4) > TOML (3) > DEFAULT (2) > HARDCODED (1)
    """

    HARDCODED = 1  # Hardcoded defaults in source code
    DEFAULT = 2  # Configuration defaults in configurations/_shared/*.yaml
    TOML = 3  # TOML configs (settings.toml, eval_config.toml)
    YAML = 4  # YAML configs (configs/*.yaml, config/registry.yaml)
    DOTENV = 5  # .env files (.env.mcp, .env, .env.example)
    ENV = 6  # Environment variables (direct os.environ access)
    CLI = 7  # CLI arguments (--profile, --model, etc.)


@dataclass(frozen=True)
class ConfigValue:
    """
    Configuration value with provenance metadata.
    
    Attributes:
        value: The actual configuration value (can be any JSON-serializable type)
        layer: Which precedence layer provided this value
        source: Source identifier (filename, env var name, "CLI arg", etc.)
        timestamp: When this value was resolved
        path: Dotted path to this value (e.g., "llm.model.platform")
    """

    value: Any
    layer: ConfigLayer
    source: str
    path: str
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def __str__(self) -> str:
        layer_name = self.layer.name
        return f"{self.path} = {self.value} (from {layer_name} via {self.source})"


# ---------------------------------------------------------------------------
# Configuration Source Interfaces
# ---------------------------------------------------------------------------


class ConfigSource(ABC):
    """
    Abstract interface for configuration sources.
    
    Each source (ENV, DOTENV, YAML, TOML) implements this protocol to provide
    values at a specific precedence layer with source tracking.
    """

    @property
    @abstractmethod
    def layer(self) -> ConfigLayer:
        """The precedence layer this source provides."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for this source (e.g., filename, 'os.environ')."""
        pass

    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """
        Load configuration from this source.
        
        Returns:
            Nested dict with configuration keys/values
        """
        pass


class EnvSource(ConfigSource):
    """
    Loads configuration from environment variables.
    
    Supports prefixes (e.g., CUGA_*, AGENT_*) and nested key mapping
    (e.g., AGENT__LLM__MODEL -> {"agent": {"llm": {"model": "..."}}}).
    """

    def __init__(self, prefixes: Optional[List[str]] = None):
        """
        Args:
            prefixes: List of env var prefixes to include (e.g., ["CUGA_", "AGENT_"])
                     If None, includes all environment variables.
        """
        self.prefixes = prefixes or []

    @property
    def layer(self) -> ConfigLayer:
        return ConfigLayer.ENV

    @property
    def source_name(self) -> str:
        return "os.environ"

    def load(self) -> Dict[str, Any]:
        """Load env vars matching prefixes into nested dict."""
        config = {}
        for key, value in os.environ.items():
            # Filter by prefixes if specified
            if self.prefixes and not any(key.startswith(p) for p in self.prefixes):
                continue

            # Convert AGENT__LLM__MODEL -> agent.llm.model
            nested_key = key.lower().replace("__", ".")
            self._set_nested(config, nested_key, value)

        return config

    def _set_nested(self, config: dict, path: str, value: Any) -> None:
        """Set value in nested dict using dotted path."""
        keys = path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


class DotEnvSource(ConfigSource):
    """
    Loads configuration from .env files.
    
    Supports multiple .env files with precedence (.env.mcp > .env > .env.example).
    """

    def __init__(self, file_path: Union[str, Path], override: bool = False):
        """
        Args:
            file_path: Path to .env file
            override: If True, override previously set env vars (useful for .env.mcp)
        """
        self.file_path = Path(file_path)
        self.override = override

    @property
    def layer(self) -> ConfigLayer:
        return ConfigLayer.DOTENV

    @property
    def source_name(self) -> str:
        return str(self.file_path)

    def load(self) -> Dict[str, Any]:
        """Parse .env file into nested dict."""
        if not self.file_path.exists():
            logger.warning(f"DotEnv file not found: {self.file_path}")
            return {}

        config = {}
        pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")

        with self.file_path.open("r") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue

                match = pattern.match(line)
                if match:
                    key, value = match.groups()
                    # Remove surrounding quotes
                    value = value.strip().strip('"').strip("'")
                    # Convert KEY -> key, support nested KEY__SUB -> key.sub
                    nested_key = key.lower().replace("__", ".")
                    self._set_nested(config, nested_key, value)

        return config

    def _set_nested(self, config: dict, path: str, value: Any) -> None:
        """Set value in nested dict using dotted path."""
        keys = path.split(".")
        current = config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value


class YAMLSource(ConfigSource):
    """Loads configuration from YAML files."""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)

    @property
    def layer(self) -> ConfigLayer:
        return ConfigLayer.YAML

    @property
    def source_name(self) -> str:
        return str(self.file_path)

    def load(self) -> Dict[str, Any]:
        """Load YAML file into dict."""
        if not self.file_path.exists():
            logger.warning(f"YAML file not found: {self.file_path}")
            return {}

        with self.file_path.open("r") as f:
            return yaml.safe_load(f) or {}


class TOMLSource(ConfigSource):
    """Loads configuration from TOML files."""

    def __init__(self, file_path: Union[str, Path]):
        self.file_path = Path(file_path)

    @property
    def layer(self) -> ConfigLayer:
        return ConfigLayer.TOML

    @property
    def source_name(self) -> str:
        return str(self.file_path)

    def load(self) -> Dict[str, Any]:
        """Load TOML file into dict."""
        if not self.file_path.exists():
            logger.warning(f"TOML file not found: {self.file_path}")
            return {}

        with self.file_path.open("rb") as f:
            return tomllib.load(f)


class DefaultSource(ConfigSource):
    """
    Loads configuration defaults from configurations/_shared/*.yaml.
    
    Lower precedence than explicit config files (YAML/TOML).
    """

    def __init__(self, defaults_dir: Union[str, Path]):
        self.defaults_dir = Path(defaults_dir)

    @property
    def layer(self) -> ConfigLayer:
        return ConfigLayer.DEFAULT

    @property
    def source_name(self) -> str:
        return str(self.defaults_dir)

    def load(self) -> Dict[str, Any]:
        """Load all YAML files in defaults directory and merge."""
        if not self.defaults_dir.exists():
            logger.warning(f"Defaults directory not found: {self.defaults_dir}")
            return {}

        merged = {}
        for yaml_file in sorted(self.defaults_dir.glob("*.yaml")):
            with yaml_file.open("r") as f:
                data = yaml.safe_load(f) or {}
                self._deep_merge(merged, data)

        return merged

    def _deep_merge(self, base: dict, update: dict) -> None:
        """Deep merge update dict into base dict (modifies base in-place)."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value


# ---------------------------------------------------------------------------
# Configuration Resolver
# ---------------------------------------------------------------------------


class ConfigResolver:
    """
    Unified configuration resolver with explicit precedence and provenance.
    
    Usage:
        resolver = ConfigResolver()
        resolver.add_source(EnvSource(prefixes=["CUGA_", "AGENT_"]))
        resolver.add_source(YAMLSource("configs/agent.yaml"))
        resolver.add_source(TOMLSource("settings.toml"))
        
        # Get value with provenance
        model = resolver.get("llm.model")
        print(model)  # granite-4-h-small (from ENV via WATSONX_MODEL)
        
        # Get raw value only
        model_name = resolver.get_value("llm.model")
        
        # List all config keys
        print(resolver.keys())
        
        # Get provenance for specific key
        print(resolver.get_provenance("llm.model"))
    """

    def __init__(self):
        self.sources: List[ConfigSource] = []
        self._resolved: Dict[str, ConfigValue] = {}
        self._cache: Dict[str, Any] = {}

    def add_source(self, source: ConfigSource) -> None:
        """
        Add a configuration source.
        
        Sources are resolved in order of precedence (higher layer wins).
        """
        self.sources.append(source)
        self._invalidate_cache()

    def resolve(self) -> None:
        """
        Load all sources and resolve configuration with precedence.
        
        Must be called after adding all sources and before accessing values.
        """
        # Sort sources by layer (lowest precedence first)
        sorted_sources = sorted(self.sources, key=lambda s: s.layer)

        # Load all sources and merge with precedence
        merged = {}
        provenance = {}

        for source in sorted_sources:
            logger.debug(f"Loading config from {source.source_name} (layer={source.layer.name})")
            data = source.load()
            self._merge_with_provenance(merged, data, provenance, source)

        # Flatten provenance into ConfigValue objects
        self._resolved = {}
        self._flatten_provenance(merged, provenance, self._resolved, path="")

        # Build flat cache for fast lookups
        self._cache = self._flatten_dict(merged)

        logger.info(
            f"Resolved {len(self._cache)} config keys from {len(self.sources)} sources "
            f"(layers: {[s.layer.name for s in sorted_sources]})"
        )

    def get(self, key: str, default: Any = None) -> Optional[ConfigValue]:
        """
        Get configuration value with provenance metadata.
        
        Args:
            key: Dotted path to config key (e.g., "llm.model.platform")
            default: Default value if key not found
            
        Returns:
            ConfigValue with provenance, or None if not found
        """
        if not self._cache:
            raise RuntimeError("ConfigResolver.resolve() must be called before accessing values")

        return self._resolved.get(key, ConfigValue(default, ConfigLayer.HARDCODED, "default", key))

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        Get raw configuration value (without provenance metadata).
        
        Args:
            key: Dotted path to config key
            default: Default value if key not found
            
        Returns:
            Raw value (str, int, dict, etc.)
        """
        if not self._cache:
            raise RuntimeError("ConfigResolver.resolve() must be called before accessing values")

        return self._cache.get(key, default)

    def keys(self) -> List[str]:
        """Return list of all resolved config keys (dotted paths)."""
        if not self._cache:
            raise RuntimeError("ConfigResolver.resolve() must be called before accessing keys")

        return sorted(self._cache.keys())

    def get_provenance(self, key: str) -> str:
        """
        Get human-readable provenance for a config key.
        
        Returns:
            String like "llm.model = granite-4-h-small (from ENV via WATSONX_MODEL)"
        """
        config_value = self.get(key)
        if config_value:
            return str(config_value)
        return f"{key} = <not found>"

    def dump(self) -> Dict[str, str]:
        """
        Dump all resolved config with provenance.
        
        Returns:
            Dict mapping config keys to provenance strings
        """
        return {key: self.get_provenance(key) for key in self.keys()}

    def _merge_with_provenance(
        self,
        base: dict,
        update: dict,
        provenance: dict,
        source: ConfigSource,
        path: str = "",
    ) -> None:
        """
        Deep merge update dict into base, tracking provenance.
        
        Args:
            base: Base dict to merge into (modified in-place)
            update: Update dict with new values
            provenance: Provenance tracking dict (modified in-place)
            source: ConfigSource providing the update
            path: Current dotted path (for nested dicts)
        """
        for key, value in update.items():
            current_path = f"{path}.{key}" if path else key

            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                # Deep merge for nested dicts
                if key not in provenance:
                    provenance[key] = {}
                self._merge_with_provenance(base[key], value, provenance[key], source, current_path)
            else:
                # Override for scalars/lists (higher precedence wins)
                if key not in base:
                    base[key] = value
                    provenance[key] = (source.layer, source.source_name)
                else:
                    # Check precedence
                    existing_layer, _ = provenance.get(key, (ConfigLayer.HARDCODED, "unknown"))
                    if source.layer >= existing_layer:
                        base[key] = value
                        provenance[key] = (source.layer, source.source_name)

    def _flatten_provenance(
        self,
        data: dict,
        provenance: dict,
        result: dict,
        path: str = "",
    ) -> None:
        """
        Flatten nested dict + provenance into flat dict of ConfigValue objects.
        
        Args:
            data: Nested config dict
            provenance: Nested provenance dict
            result: Output dict (modified in-place)
            path: Current dotted path
        """
        for key, value in data.items():
            current_path = f"{path}.{key}" if path else key

            if isinstance(value, dict):
                # Recurse for nested dicts
                sub_provenance = provenance.get(key, {}) if isinstance(provenance.get(key), dict) else {}
                self._flatten_provenance(value, sub_provenance, result, current_path)
            else:
                # Leaf node - create ConfigValue
                layer, source = provenance.get(key, (ConfigLayer.HARDCODED, "unknown"))
                result[current_path] = ConfigValue(
                    value=value,
                    layer=layer,
                    source=source,
                    path=current_path,
                )

    def _flatten_dict(self, data: dict, parent_key: str = "") -> dict:
        """
        Flatten nested dict to dotted keys.
        
        Example:
            {"llm": {"model": "granite"}} -> {"llm.model": "granite"}
        """
        items = []
        for key, value in data.items():
            new_key = f"{parent_key}.{key}" if parent_key else key
            if isinstance(value, dict):
                items.extend(self._flatten_dict(value, new_key).items())
            else:
                items.append((new_key, value))
        return dict(items)

    def _invalidate_cache(self) -> None:
        """Clear cached resolved config (call after adding sources)."""
        self._cache = {}
        self._resolved = {}

    def validate_all(self, fail_fast: bool = True) -> Dict[str, List[str]]:
        """
        Validate all resolved configuration using ConfigValidator.
        
        Validates:
            - Tool registry (config.tools or registry.tools)
            - Routing guards (config.guards or guards)
            - Agent configuration (config.agent or agent)
            - Memory configuration (config.memory or memory)
            - Observability configuration (config.observability or observability)
        
        Args:
            fail_fast: If True, raise ValueError on first validation error.
                      If False, collect all errors and return them.
        
        Returns:
            Dict mapping config sections to lists of error messages.
            Empty dict if all validations pass.
        
        Raises:
            ValueError: If fail_fast=True and any validation fails.
        
        Example:
            resolver = ConfigResolver()
            resolver.add_source(YAMLSource("config/registry.yaml"))
            resolver.resolve()
            
            # Fail-fast mode (raises on first error)
            resolver.validate_all()  # Raises ValueError with detailed message
            
            # Collect all errors mode
            errors = resolver.validate_all(fail_fast=False)
            if errors:
                for section, error_list in errors.items():
                    print(f"{section}: {error_list}")
        """
        from cuga.config import ConfigValidator

        errors = {}

        # Get full resolved config
        full_config = {}
        for key in self.keys():
            value = self.get_value(key)
            # Reconstruct nested dict from dotted keys
            keys = key.split(".")
            current = full_config
            for k in keys[:-1]:
                if k not in current:
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value

        # Validate tool registry
        registry_data = full_config.get("config", {}).get("tools") or full_config.get("tools")
        if registry_data:
            try:
                ConfigValidator.validate_registry({"tools": registry_data})
                logger.debug("✅ Tool registry validation passed")
            except ValueError as e:
                error_msg = str(e)
                errors["registry"] = [error_msg]
                logger.error(f"❌ Tool registry validation failed: {error_msg}")
                if fail_fast:
                    raise

        # Validate guards
        guards_data = full_config.get("config", {}).get("guards") or full_config.get("guards")
        if guards_data:
            try:
                ConfigValidator.validate_guards(guards_data)
                logger.debug("✅ Guards validation passed")
            except ValueError as e:
                error_msg = str(e)
                errors["guards"] = [error_msg]
                logger.error(f"❌ Guards validation failed: {error_msg}")
                if fail_fast:
                    raise

        # Validate agent config
        agent_data = full_config.get("config", {}).get("agent") or full_config.get("agent")
        if agent_data:
            try:
                ConfigValidator.validate_agent_config(agent_data)
                logger.debug("✅ Agent config validation passed")
            except ValueError as e:
                error_msg = str(e)
                errors["agent"] = [error_msg]
                logger.error(f"❌ Agent config validation failed: {error_msg}")
                if fail_fast:
                    raise

        # Validate memory config
        memory_data = full_config.get("config", {}).get("memory") or full_config.get("memory")
        if memory_data:
            try:
                ConfigValidator.validate_memory_config(memory_data)
                logger.debug("✅ Memory config validation passed")
            except ValueError as e:
                error_msg = str(e)
                errors["memory"] = [error_msg]
                logger.error(f"❌ Memory config validation failed: {error_msg}")
                if fail_fast:
                    raise

        # Validate observability config
        observability_data = (
            full_config.get("config", {}).get("observability") or full_config.get("observability")
        )
        if observability_data:
            try:
                ConfigValidator.validate_observability_config(observability_data)
                logger.debug("✅ Observability config validation passed")
            except ValueError as e:
                error_msg = str(e)
                errors["observability"] = [error_msg]
                logger.error(f"❌ Observability config validation failed: {error_msg}")
                if fail_fast:
                    raise

        if not errors:
            logger.info("✅ All configuration validation checks passed")

        return errors
