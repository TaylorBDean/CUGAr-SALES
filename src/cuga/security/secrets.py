"""
Secrets management and validation per AGENTS.md guardrails.

Enforces:
- Env-only credential storage (no hardcoded secrets)
- .env.example parity validation
- Secret redaction in logs/errors
- Required env var validation by execution mode
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Set
from loguru import logger


# Sensitive key patterns per AGENTS.md redaction rules
SENSITIVE_KEY_PATTERNS = [
    r".*secret.*",
    r".*token.*",
    r".*password.*",
    r".*api[_-]?key.*",
    r".*auth.*",
    r".*credential.*",
]


def is_sensitive_key(key: str) -> bool:
    """
    Check if key name indicates sensitive data requiring redaction.
    
    Per AGENTS.md: redact values for secret, token, password keys.
    """
    key_lower = key.lower()
    return any(re.match(pattern, key_lower, re.IGNORECASE) for pattern in SENSITIVE_KEY_PATTERNS)


def redact_dict(data: Dict[str, any]) -> Dict[str, any]:
    """
    Redact sensitive values in dict for safe logging.
    
    Args:
        data: Dictionary potentially containing secrets
        
    Returns:
        New dict with sensitive values replaced by "<redacted>"
    """
    redacted = {}
    for key, value in data.items():
        if is_sensitive_key(key):
            redacted[key] = "<redacted>"
        elif isinstance(value, dict):
            redacted[key] = redact_dict(value)
        elif isinstance(value, list):
            redacted[key] = [redact_dict(item) if isinstance(item, dict) else item for item in value]
        else:
            redacted[key] = value
    return redacted


def validate_env_parity(
    env_example_path: Path = Path(".env.example"),
    env_path: Optional[Path] = None,
    ignore_keys: Optional[Set[str]] = None
) -> tuple[bool, List[str]]:
    """
    Validate .env.example parity - ensure no missing keys.
    
    Per user requirement: "validate .env.example parity in CI (no missing keys)"
    
    Args:
        env_example_path: Path to .env.example template
        env_path: Path to actual .env (optional, defaults to environment vars)
        ignore_keys: Keys to skip in validation (e.g., optional vars)
        
    Returns:
        (is_valid, missing_keys) tuple
    """
    ignore_keys = ignore_keys or set()
    
    if not env_example_path.exists():
        logger.warning(f".env.example not found at {env_example_path}")
        return True, []  # Skip validation if template missing
    
    # Parse .env.example for required keys
    example_keys = set()
    with open(env_example_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                key = line.split('=')[0].strip()
                if key and key not in ignore_keys:
                    example_keys.add(key)
    
    # Check against actual environment
    if env_path and env_path.exists():
        # Parse .env file
        actual_keys = set()
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    key = line.split('=')[0].strip()
                    if key:
                        actual_keys.add(key)
    else:
        # Check environment variables
        actual_keys = set(os.environ.keys())
    
    # Find missing keys
    missing_keys = sorted(example_keys - actual_keys)
    is_valid = len(missing_keys) == 0
    
    if not is_valid:
        logger.warning(
            f".env parity check failed: {len(missing_keys)} missing keys: "
            f"{', '.join(missing_keys)}"
        )
    else:
        logger.debug(f".env parity check passed: all {len(example_keys)} keys present")
    
    return is_valid, missing_keys


def enforce_env_only_secrets(
    required_keys: List[str],
    execution_mode: str = "local"
) -> Dict[str, str]:
    """
    Enforce env-only secrets per AGENTS.md Environment Requirements.
    
    Per AGENTS.md:
    - LOCAL: model API key (watsonx/openai/anthropic/azure/groq)
    - SERVICE: AGENT_TOKEN + AGENT_BUDGET_CEILING + model keys
    - MCP: MCP_SERVERS_FILE + CUGA_PROFILE_SANDBOX + model keys
    - TEST: no env vars required (uses defaults/mocks)
    
    Args:
        required_keys: List of required environment variable names
        execution_mode: One of: local, service, mcp, test
        
    Returns:
        Dict of validated environment variables
        
    Raises:
        RuntimeError: If required env vars missing with helpful error messages
    """
    if execution_mode == "test":
        logger.debug("Test mode: skipping env var validation")
        return {}
    
    missing = []
    secrets = {}
    
    for key in required_keys:
        value = os.getenv(key)
        if not value:
            missing.append(key)
        else:
            secrets[key] = value
    
    if missing:
        mode_hints = {
            "local": "Set model API key: OPENAI_API_KEY, WATSONX_API_KEY, etc.",
            "service": "Set AGENT_TOKEN, AGENT_BUDGET_CEILING, and model keys",
            "mcp": "Set MCP_SERVERS_FILE, CUGA_PROFILE_SANDBOX, and model keys",
        }
        hint = mode_hints.get(execution_mode, "Check docs/configuration/ENVIRONMENT_MODES.md")
        
        raise RuntimeError(
            f"Missing required environment variables for {execution_mode} mode: "
            f"{', '.join(missing)}\n\n"
            f"Setup instructions: {hint}\n"
            f"See docs/configuration/ENVIRONMENT_MODES.md for details."
        )
    
    logger.debug(
        f"Validated {len(secrets)} env vars for {execution_mode} mode: "
        f"{', '.join(secrets.keys())}"
    )
    return secrets


def detect_hardcoded_secrets(code: str) -> List[Dict[str, any]]:
    """
    Detect potential hardcoded secrets in code (basic static analysis).
    
    Per AGENTS.md: "No secrets in logs or configs; use env vars and .env.example patterns."
    
    Args:
        code: Source code to scan
        
    Returns:
        List of findings with line numbers and matched patterns
    """
    findings = []
    
    # Patterns indicating potential hardcoded secrets
    secret_patterns = [
        (r'api[_-]?key\s*=\s*["\']([^"\']{20,})["\']', "API key assignment"),
        (r'token\s*=\s*["\']([^"\']{20,})["\']', "Token assignment"),
        (r'password\s*=\s*["\']([^"\']{8,})["\']', "Password assignment"),
        (r'secret\s*=\s*["\']([^"\']{16,})["\']', "Secret assignment"),
        (r'bearer\s+([a-zA-Z0-9_\-\.]{20,})', "Bearer token"),
        (r'basic\s+([a-zA-Z0-9+/=]{20,})', "Basic auth"),
    ]
    
    for line_num, line in enumerate(code.split('\n'), start=1):
        for pattern, description in secret_patterns:
            if match := re.search(pattern, line, re.IGNORECASE):
                # Skip if it's clearly an env var reference
                if 'os.getenv' in line or 'os.environ' in line or 'settings.' in line:
                    continue
                
                findings.append({
                    "line": line_num,
                    "description": description,
                    "snippet": line.strip()[:80],  # Truncate for safety
                    "pattern": pattern,
                })
    
    return findings


def validate_startup_env(execution_mode: str) -> None:
    """
    Validate required environment variables before startup.
    
    Per AGENTS.md: "Validators MUST check requirements before startup per mode 
    with helpful error messages suggesting missing vars."
    
    Args:
        execution_mode: One of: local, service, mcp, test
        
    Raises:
        RuntimeError: If validation fails
    """
    mode_requirements = {
        "local": ["OPENAI_API_KEY"],  # Or any valid provider key
        "service": ["AGENT_TOKEN", "AGENT_BUDGET_CEILING", "OPENAI_API_KEY"],
        "mcp": ["MCP_SERVERS_FILE", "CUGA_PROFILE_SANDBOX", "OPENAI_API_KEY"],
        "test": [],  # No requirements for test mode
    }
    
    required_keys = mode_requirements.get(execution_mode, [])
    
    # For local/service/mcp modes, allow any valid provider key
    if execution_mode in ["local", "service", "mcp"]:
        provider_keys = [
            "OPENAI_API_KEY",
            "WATSONX_API_KEY",
            "ANTHROPIC_API_KEY",
            "AZURE_OPENAI_API_KEY",
            "GROQ_API_KEY",
        ]
        has_provider_key = any(os.getenv(key) for key in provider_keys)
        
        if not has_provider_key:
            required_keys = [k for k in required_keys if k not in provider_keys]
            required_keys.append("OPENAI_API_KEY or WATSONX_API_KEY or similar")
    
    enforce_env_only_secrets(required_keys, execution_mode)
    logger.info(f"Environment validation passed for {execution_mode} mode")
