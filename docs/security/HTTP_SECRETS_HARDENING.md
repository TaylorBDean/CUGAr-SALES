# HTTP & Secrets Hardening Implementation Summary

## Overview

Implemented comprehensive HTTP client wrapper and secrets management system per AGENTS.md security guardrails and user requirements.

## Components Created

### 1. SafeClient HTTP Wrapper (`src/cuga/security/http_client.py`)

**Features:**
- Enforced timeouts: 10.0s read, 5.0s connect, 10.0s write, 10.0s total
- Automatic retry with exponential backoff: 4 attempts max, 8s max wait, 0.5s multiplier
- Retry on: `TimeoutException`, `ConnectError`, `NetworkError`
- Redirect following enabled by default
- URL redaction in logs (strips query params and credentials)
- Context manager support for automatic cleanup
- Both sync (`SafeClient`) and async (`AsyncSafeClient`) variants

**Usage:**
```python
from cuga.security import SafeClient

# Sync usage
with SafeClient() as client:
    response = client.get("https://api.example.com/data")
    
# Async usage
async with AsyncSafeClient() as client:
    response = await client.get("https://api.example.com/data")
```

**Supported Methods:**
- `get()`, `post()`, `put()`, `patch()`, `delete()`
- All methods enforce timeout and retry automatically

### 2. Secrets Management (`src/cuga/security/secrets.py`)

**Features:**
- Sensitive key detection: `secret`, `token`, `password`, `api_key`, `auth`, `credential` patterns
- Dict redaction with recursive traversal for nested dicts/lists
- `.env.example` parity validation (checks for missing keys)
- Env-only secrets enforcement with mode-specific validation
- Hardcoded secret detection (basic static analysis)
- Startup validation with helpful error messages

**Functions:**
- `is_sensitive_key(key)`: Check if key indicates sensitive data
- `redact_dict(data)`: Redact sensitive values for safe logging
- `validate_env_parity(env_example_path)`: Validate .env.example parity
- `enforce_env_only_secrets(required_keys, mode)`: Enforce required env vars
- `detect_hardcoded_secrets(code)`: Detect hardcoded credentials
- `validate_startup_env(mode)`: Validate environment before startup

**Execution Modes:**
- **LOCAL**: Requires model API key (OPENAI_API_KEY or provider-specific)
- **SERVICE**: Requires AGENT_TOKEN + AGENT_BUDGET_CEILING + model key
- **MCP**: Requires MCP_SERVERS_FILE + CUGA_PROFILE_SANDBOX + model key
- **TEST**: No requirements (uses defaults/mocks)

### 3. Secret Scanning CI Workflow (`.github/workflows/secret-scan.yml`)

**Jobs:**
1. **trufflehog**: Scans full git history for verified secrets
2. **gitleaks**: Parallel secret scan with different patterns
3. **env-parity-check**: Validates .env.example has no missing keys
4. **hardcoded-secrets-check**: Static analysis for hardcoded API keys/tokens
5. **secrets-summary**: Aggregates results, fails if any job failed

**Triggers:**
- Push to main/develop
- Pull requests to main/develop
- Weekly scheduled scan (Sundays at midnight)
- Manual workflow dispatch

### 4. Comprehensive Test Coverage

**HTTP Client Tests** (`tests/unit/security/test_http_client.py`):
- Default timeout configuration
- Client initialization with correct defaults
- Context manager lifecycle
- GET/POST requests with timeout enforcement
- Retry on timeout/network errors (3 retries then success)
- Retry exhaustion after max attempts
- URL redaction (query params, credentials)
- Custom timeout override
- All HTTP methods supported

**Secrets Tests** (`tests/unit/security/test_secrets.py`):
- Sensitive key pattern matching
- Dict redaction (nested dicts, lists)
- .env.example parity validation
- Env-only secrets enforcement by mode
- Hardcoded secret detection
- Startup validation with helpful error messages
- Test mode has no requirements

## AGENTS.md Updates

### Added to Tool Contract:
```markdown
- **HTTP Client (Canonical)**: All HTTP requests MUST use `cuga.security.http_client.SafeClient` 
  wrapper with enforced timeouts (10.0s read, 5.0s connect), automatic retry with exponential 
  backoff (4 attempts max, 8s max wait), and redirect following. No raw httpx/requests/urllib 
  usage outside SafeClient. URL redaction in logs (strip query params/credentials).

- **Secrets Management (Canonical)**: All credentials MUST be env-only (no hardcoded secrets). 
  CI enforces `.env.example` parity validation (no missing keys) and runs SECRET_SCANNER=on 
  (trufflehog/gitleaks) on every push/PR. Secrets validated per execution mode 
  (local/service/mcp/test) with helpful error messages. See `cuga.security.secrets` for enforcement.
```

### Added to Sandbox Expectations:
```markdown
- **HTTP Enforcement**: Network I/O MUST use `SafeClient` from `cuga.security.http_client` with 
  enforced timeouts (10.0s read, 5.0s connect, 10.0s write, 10.0s total), automatic exponential 
  backoff retry (4 attempts, 8s max wait), and URL redaction. Raw httpx/requests calls rejected.

- **Secrets Enforcement**: Credentials MUST be loaded from environment variables only. Hardcoded 
  API keys/tokens/passwords trigger CI failure. All secret values redacted in logs/errors per 
  `cuga.security.secrets.redact_dict()`.
```

## Documentation Updates

### CHANGELOG.md
- Added comprehensive "HTTP & Secrets Hardening" section under `vNext`
- Documented all features, breaking changes, and migration paths
- Listed environment requirements per execution mode
- Described CI workflow jobs

### PRODUCTION_READINESS.md
- Added HTTP Client Hardening checklist item
- Added Secrets Management checklist item
- Added Mode-Specific Validation checklist item

### todo1.md
- Updated Governance & Guardrails section with completion status

## Dependencies Added

```toml
"tenacity>=8.2.0"  # For retry policy with exponential backoff
```

## Breaking Changes

1. **All HTTP requests MUST use SafeClient wrapper**
   - Replace: `httpx.Client()` → `SafeClient()`
   - Replace: `requests.get()` → `SafeClient().get()`

2. **All credentials MUST be env-only**
   - Replace hardcoded API keys → `os.getenv("PROVIDER_API_KEY")`
   - CI fails on hardcoded secrets

3. **CI enforces .env.example parity**
   - Must keep template in sync with actual environment
   - Add missing keys to template

## Migration Examples

### HTTP Client Migration

**Before:**
```python
import httpx

with httpx.Client(timeout=10.0) as client:
    response = client.get("https://api.example.com/data")
```

**After:**
```python
from cuga.security import SafeClient

with SafeClient() as client:
    response = client.get("https://api.example.com/data")
```

### Secrets Migration

**Before:**
```python
api_key = "sk-1234567890abcdefghijklmnop"
client = OpenAI(api_key=api_key)
```

**After:**
```python
import os

api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not set")
client = OpenAI(api_key=api_key)
```

### Startup Validation

**Before:**
```python
# No validation
app.run()
```

**After:**
```python
from cuga.security import validate_startup_env

validate_startup_env("service")  # Validates AGENT_TOKEN, budget, model key
app.run()
```

## Testing

Run tests:
```bash
# All security tests
pytest tests/unit/security/ -v

# HTTP client tests only
pytest tests/unit/security/test_http_client.py -v

# Secrets tests only
pytest tests/unit/security/test_secrets.py -v

# CI secret scanning (local)
python scripts/verify_guardrails.py
```

## CI Integration

The secret scanning workflow runs automatically on:
- Every push to main/develop
- Every pull request
- Weekly schedule (Sundays)

View results in GitHub Actions:
```
Repository → Actions → Secret Scanning
```

## Environment Setup

### Local Development
```bash
cp .env.example .env
# Edit .env with your API keys
export OPENAI_API_KEY=sk-your-key-here
```

### Service Mode
```bash
export AGENT_TOKEN=your-auth-token
export AGENT_BUDGET_CEILING=100
export OPENAI_API_KEY=sk-your-key-here
```

### MCP Mode
```bash
export MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml
export CUGA_PROFILE_SANDBOX=py_slim
export OPENAI_API_KEY=sk-your-key-here
```

## Security Benefits

1. **Enforced Timeouts**: No unbounded HTTP requests
2. **Automatic Retry**: Transient failures handled gracefully
3. **URL Redaction**: Secrets never logged
4. **Env-Only Secrets**: Prevents credential leaks in code
5. **Parity Validation**: Config drift caught early
6. **Multi-Tool Scanning**: TruffleHog + Gitleaks for comprehensive coverage
7. **Mode-Specific Validation**: Clear requirements per execution context

## References

- **AGENTS.md**: Canonical guardrails and policies
- **docs/configuration/ENVIRONMENT_MODES.md**: Execution mode requirements
- **docs/security/SECURITY_CONTROLS.md**: Security architecture
- **.env.example**: Environment variable template
