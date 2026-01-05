"""
Tests for secrets validation and enforcement.

Per AGENTS.md:
- Verify env-only credential enforcement
- Verify .env.example parity validation
- Verify secret redaction in logs
- Verify hardcoded secret detection
"""

import os
import pytest
from pathlib import Path
from unittest.mock import patch
from cuga.security.secrets import (
    is_sensitive_key,
    redact_dict,
    validate_env_parity,
    enforce_env_only_secrets,
    detect_hardcoded_secrets,
    validate_startup_env,
)


class TestSensitiveKeyDetection:
    """Test sensitive key pattern matching."""
    
    def test_sensitive_key_patterns(self):
        """Verify sensitive key detection covers all AGENTS.md patterns."""
        # Should match
        assert is_sensitive_key("api_key")
        assert is_sensitive_key("API_KEY")
        assert is_sensitive_key("secret")
        assert is_sensitive_key("SECRET_VALUE")
        assert is_sensitive_key("token")
        assert is_sensitive_key("ACCESS_TOKEN")
        assert is_sensitive_key("password")
        assert is_sensitive_key("db_password")
        assert is_sensitive_key("auth_token")
        assert is_sensitive_key("credential")
        
        # Should not match
        assert not is_sensitive_key("database_url")
        assert not is_sensitive_key("timeout")
        assert not is_sensitive_key("max_retries")


class TestDictRedaction:
    """Test dictionary value redaction."""
    
    def test_redact_sensitive_values(self):
        """Verify sensitive values are redacted."""
        data = {
            "api_key": "sk-secret123",
            "timeout": 30,
            "password": "mypassword",
            "database_url": "postgres://localhost",
        }
        
        redacted = redact_dict(data)
        
        assert redacted["api_key"] == "<redacted>"
        assert redacted["password"] == "<redacted>"
        assert redacted["timeout"] == 30
        assert redacted["database_url"] == "postgres://localhost"
    
    def test_redact_nested_dicts(self):
        """Verify nested dictionary redaction."""
        data = {
            "config": {
                "api_key": "secret",
                "timeout": 10,
            },
            "credentials": {
                "token": "bearer-token",
            }
        }
        
        redacted = redact_dict(data)
        
        assert redacted["config"]["api_key"] == "<redacted>"
        assert redacted["config"]["timeout"] == 10
        assert redacted["credentials"]["token"] == "<redacted>"
    
    def test_redact_lists_with_dicts(self):
        """Verify list items containing dicts are redacted."""
        data = {
            "servers": [
                {"host": "server1", "api_key": "key1"},
                {"host": "server2", "api_key": "key2"},
            ]
        }
        
        redacted = redact_dict(data)
        
        assert redacted["servers"][0]["api_key"] == "<redacted>"
        assert redacted["servers"][1]["api_key"] == "<redacted>"
        assert redacted["servers"][0]["host"] == "server1"


class TestEnvParityValidation:
    """Test .env.example parity validation."""
    
    def test_valid_parity(self, tmp_path):
        """Verify validation passes when all keys present."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("""
# API Keys
OPENAI_API_KEY=
WATSONX_API_KEY=

# Config
DATABASE_URL=
        """)
        
        with patch.dict(os.environ, {
            "OPENAI_API_KEY": "sk-test",
            "WATSONX_API_KEY": "wx-test",
            "DATABASE_URL": "postgres://localhost",
        }):
            is_valid, missing = validate_env_parity(env_example)
            
            assert is_valid
            assert len(missing) == 0
    
    def test_missing_keys(self, tmp_path):
        """Verify validation fails when keys missing."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("""
OPENAI_API_KEY=
WATSONX_API_KEY=
DATABASE_URL=
        """)
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            is_valid, missing = validate_env_parity(env_example)
            
            assert not is_valid
            assert "WATSONX_API_KEY" in missing
            assert "DATABASE_URL" in missing
    
    def test_ignore_keys(self, tmp_path):
        """Verify ignore_keys parameter works."""
        env_example = tmp_path / ".env.example"
        env_example.write_text("""
OPENAI_API_KEY=
OPTIONAL_FEATURE=
        """)
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}, clear=True):
            # Without ignore
            is_valid, missing = validate_env_parity(env_example)
            assert not is_valid
            assert "OPTIONAL_FEATURE" in missing
            
            # With ignore
            is_valid, missing = validate_env_parity(
                env_example,
                ignore_keys={"OPTIONAL_FEATURE"}
            )
            assert is_valid
            assert len(missing) == 0


class TestEnvOnlySecrets:
    """Test env-only secrets enforcement."""
    
    def test_local_mode_validation(self):
        """Verify local mode requires model API key."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            secrets = enforce_env_only_secrets(["OPENAI_API_KEY"], "local")
            assert secrets["OPENAI_API_KEY"] == "sk-test"
    
    def test_service_mode_validation(self):
        """Verify service mode requires AGENT_TOKEN + budget + model key."""
        with patch.dict(os.environ, {
            "AGENT_TOKEN": "token123",
            "AGENT_BUDGET_CEILING": "100",
            "OPENAI_API_KEY": "sk-test",
        }):
            secrets = enforce_env_only_secrets(
                ["AGENT_TOKEN", "AGENT_BUDGET_CEILING", "OPENAI_API_KEY"],
                "service"
            )
            assert len(secrets) == 3
    
    def test_mcp_mode_validation(self):
        """Verify MCP mode requires MCP_SERVERS_FILE + profile + model key."""
        with patch.dict(os.environ, {
            "MCP_SERVERS_FILE": "./servers.yaml",
            "CUGA_PROFILE_SANDBOX": "py_slim",
            "OPENAI_API_KEY": "sk-test",
        }):
            secrets = enforce_env_only_secrets(
                ["MCP_SERVERS_FILE", "CUGA_PROFILE_SANDBOX", "OPENAI_API_KEY"],
                "mcp"
            )
            assert len(secrets) == 3
    
    def test_test_mode_no_validation(self):
        """Verify test mode skips validation."""
        # Should not raise even with no env vars
        secrets = enforce_env_only_secrets([], "test")
        assert secrets == {}
    
    def test_missing_secrets_raises_error(self):
        """Verify missing secrets raise RuntimeError with helpful message."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                enforce_env_only_secrets(["OPENAI_API_KEY"], "local")
            
            assert "Missing required environment variables" in str(exc_info.value)
            assert "OPENAI_API_KEY" in str(exc_info.value)
            assert "local mode" in str(exc_info.value)


class TestHardcodedSecretDetection:
    """Test static analysis for hardcoded secrets."""
    
    def test_detect_api_key_assignment(self):
        """Verify detection of hardcoded API keys."""
        code = '''
api_key = "sk-1234567890abcdefghijklmnop"
client = OpenAI(api_key=api_key)
        '''
        
        findings = detect_hardcoded_secrets(code)
        assert len(findings) > 0
        assert any("API key" in f["description"] for f in findings)
    
    def test_detect_token_assignment(self):
        """Verify detection of hardcoded tokens."""
        code = '''
token = "ghp_1234567890abcdefghijklmnop"
headers = {"Authorization": f"Bearer {token}"}
        '''
        
        findings = detect_hardcoded_secrets(code)
        assert len(findings) > 0
        assert any("Token" in f["description"] or "Bearer" in f["description"] for f in findings)
    
    def test_skip_env_var_references(self):
        """Verify env var references are not flagged."""
        code = '''
api_key = os.getenv("OPENAI_API_KEY")
token = os.environ["GITHUB_TOKEN"]
secret = settings.SECRET_KEY
        '''
        
        findings = detect_hardcoded_secrets(code)
        # Should not flag env var references
        assert len(findings) == 0
    
    def test_detect_bearer_token(self):
        """Verify detection of Bearer tokens in code."""
        code = '''
headers = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
}
        '''
        
        findings = detect_hardcoded_secrets(code)
        assert len(findings) > 0


class TestStartupValidation:
    """Test startup environment validation."""
    
    def test_local_mode_startup(self):
        """Verify local mode startup validation."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test"}):
            # Should not raise
            validate_startup_env("local")
    
    def test_service_mode_startup(self):
        """Verify service mode startup validation."""
        with patch.dict(os.environ, {
            "AGENT_TOKEN": "token123",
            "AGENT_BUDGET_CEILING": "100",
            "OPENAI_API_KEY": "sk-test",
        }):
            # Should not raise
            validate_startup_env("service")
    
    def test_test_mode_no_requirements(self):
        """Verify test mode has no requirements."""
        with patch.dict(os.environ, {}, clear=True):
            # Should not raise even with empty env
            validate_startup_env("test")
    
    def test_missing_vars_raises_helpful_error(self):
        """Verify helpful error messages for missing vars."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(RuntimeError) as exc_info:
                validate_startup_env("service")
            
            error_msg = str(exc_info.value)
            assert "Missing required environment variables" in error_msg
            assert "service mode" in error_msg
            assert "AGENT_TOKEN" in error_msg or "Setup instructions" in error_msg
