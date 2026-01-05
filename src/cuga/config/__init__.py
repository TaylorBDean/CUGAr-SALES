"""
Configuration Resolution Package

Provides unified configuration resolution with explicit precedence layers,
provenance tracking, and environment validation.

Canonical precedence order (highest to lowest):
    1. CLI arguments
    2. Environment variables
    3. .env files (.env.mcp, .env, .env.example)
    4. YAML configs (configs/*.yaml, config/registry.yaml)
    5. TOML configs (settings.toml, eval_config.toml)
    6. Configuration defaults (configurations/_shared/*.yaml)
    7. Hardcoded defaults (in code)

See docs/configuration/CONFIG_RESOLUTION.md for complete specification.
"""

from .resolver import ConfigResolver, ConfigLayer, ConfigValue, ConfigSource
from .validators import (
    validate_environment_mode,
    EnvironmentMode,
    ValidationResult,
    ConfigValidator,
)

# Re-export legacy config values for backward compatibility
try:
    import sys
    from pathlib import Path
    # Import from sibling config.py file
    config_py_path = Path(__file__).parent.parent / "config.py"
    if config_py_path.exists():
        import importlib.util
        spec = importlib.util.spec_from_file_location("cuga_config_legacy", config_py_path)
        if spec and spec.loader:
            legacy_config = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(legacy_config)
            TRAJECTORY_DATA_DIR = legacy_config.TRAJECTORY_DATA_DIR
            settings = legacy_config.settings
except Exception:
    # Fallback defaults if legacy config unavailable
    import os
    TRAJECTORY_DATA_DIR = os.path.join(os.getcwd(), "logging", "trajectory_data")
    settings = None

__all__ = [
    "ConfigResolver",
    "ConfigLayer",
    "ConfigValue",
    "ConfigSource",
    "validate_environment_mode",
    "EnvironmentMode",
    "ValidationResult",
    "ConfigValidator",
    "TRAJECTORY_DATA_DIR",
    "settings",
]
