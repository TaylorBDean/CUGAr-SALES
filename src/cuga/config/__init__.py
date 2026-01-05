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
            PACKAGE_ROOT = legacy_config.PACKAGE_ROOT
            DBS_DIR = getattr(legacy_config, "DBS_DIR", None)
            LOGGING_DIR = getattr(legacy_config, "LOGGING_DIR", None)
            TRACES_DIR = getattr(legacy_config, "TRACES_DIR", None)
            ENV_FILE_PATH = getattr(legacy_config, "ENV_FILE_PATH", None)
            get_user_data_path = getattr(legacy_config, "get_user_data_path", None)
            get_app_name_from_url = getattr(legacy_config, "get_app_name_from_url", None)
            load_llm_settings = getattr(legacy_config, "load_llm_settings", None)
            LLMSettings = getattr(legacy_config, "LLMSettings", None)
            TRAJECTORY_DATA_DIR = legacy_config.TRAJECTORY_DATA_DIR
            settings = legacy_config.settings
except Exception:
    # Fallback defaults if legacy config unavailable
    import os
    from pathlib import Path

    PACKAGE_ROOT = Path(__file__).resolve().parent.parent
    LOGGING_DIR = os.path.join(os.getcwd(), "logging")
    DBS_DIR = os.path.join(os.getcwd(), "dbs")
    TRACES_DIR = os.path.join(LOGGING_DIR, "traces")
    ENV_FILE_PATH = os.path.join(os.getcwd(), ".env")
    get_user_data_path = None
    get_app_name_from_url = None
    load_llm_settings = None
    LLMSettings = None
    TRAJECTORY_DATA_DIR = os.path.join(LOGGING_DIR, "trajectory_data")
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
    "PACKAGE_ROOT",
    "DBS_DIR",
    "LOGGING_DIR",
    "TRACES_DIR",
    "ENV_FILE_PATH",
    "get_user_data_path",
    "get_app_name_from_url",
    "load_llm_settings",
    "LLMSettings",
    "TRAJECTORY_DATA_DIR",
    "settings",
]
