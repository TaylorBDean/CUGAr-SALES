# Environment Expectations Per Execution Mode

**Status**: Canonical  
**Last Updated**: 2025-12-31  
**Owner**: Configuration Team

## Problem Statement

### Before: Unclear Environment Requirements

```
Which env vars are needed for:
   ├── Local execution (CLI)?
   ├── FastAPI service (production)?
   ├── MCP agents (orchestrator)?
   └── Tests (CI/CD)?

Impact:
   ├── Trial and error environment setup
   ├── Production deployment failures
   ├── CI/CD brittleness (env leakage)
   ├── Developer friction (missing vars not caught early)
   └── Security risks (running with wrong profile/credentials)
```

### After: Explicit Mode Requirements

```
Clear env requirements per mode:
   ├── Local Mode (Development/CLI)
   │   ├── PROFILE, MODEL_*, LOG_LEVEL
   │   └── Optional: Observability, vector backends
   │
   ├── Service Mode (FastAPI Production)
   │   ├── AGENT_TOKEN (required)
   │   ├── AGENT_BUDGET_CEILING (required)
   │   ├── MODEL_* (required)
   │   └── PORT, HOST, LANGFUSE_*
   │
   ├── MCP Mode (Agent Orchestration)
   │   ├── MCP_SERVERS_FILE (required)
   │   ├── CUGA_PROFILE_SANDBOX (required)
   │   ├── MODEL_* (required)
   │   └── Observability for trace propagation
   │
   └── Test Mode (CI/CD)
       ├── Minimal defaults (isolated)
       ├── No real API keys (mocked)
       └── Temp configs (no state leakage)
```

## Execution Modes

### 1. Local Mode (Development / CLI)

**Use Case**: Developer running agents locally for testing, experimentation, or ad-hoc tasks.

**Entry Points**:
- `python -m cuga.cli orchestrate --goal "task"`
- Direct planner/coordinator usage
- Interactive notebooks

#### Required Environment Variables

```bash
# Model Configuration (REQUIRED - choose one provider)

# IBM Watsonx / Granite 4.0 (DEFAULT PROVIDER)
WATSONX_API_KEY=...                    # IBM Cloud API key (required)
WATSONX_PROJECT_ID=...                 # Watsonx project ID (required)
WATSONX_URL=...                        # Watsonx API endpoint (optional, defaults to IBM Cloud)
# Available models: granite-4-h-small (default), granite-4-h-micro, granite-4-h-tiny

# OR OpenAI
OPENAI_API_KEY=sk-...                  # OpenAI API key

# OR Azure OpenAI
AZURE_OPENAI_API_KEY=...               # Azure OpenAI key
AZURE_OPENAI_ENDPOINT=https://...      # Azure endpoint

# OR Groq
GROQ_API_KEY=gsk_...                   # Groq API key

# OR Anthropic
ANTHROPIC_API_KEY=...                  # Anthropic API key

# Profile Configuration (OPTIONAL - has defaults)
PROFILE=demo_power                     # Execution profile (default: demo_power)
```

#### Optional Environment Variables

```bash
# Planner Configuration
PLANNER_STRATEGY=react                 # Planning strategy (default: react)
PLANNER_MAX_STEPS=6                    # Max planning steps (default: 6)
MODEL_TEMPERATURE=0.3                  # Model temperature (default: 0.3)

# Memory & RAG
VECTOR_BACKEND=local                   # Vector store (default: local)
VECTOR_HOST=localhost                  # Vector host (if not local)
VECTOR_PORT=6333                       # Vector port (if not local)
VECTOR_NAMESPACE=cuga-demo             # Namespace (default: cuga-demo)
RAG_ENABLED=false                      # Enable RAG (default: false)

# Observability
LANGFUSE_ENABLED=false                 # Enable Langfuse (default: false)
LANGFUSE_HOST=                         # Langfuse host
LANGFUSE_PUBLIC_KEY=                   # Langfuse public key
LANGFUSE_SECRET_KEY=                   # Langfuse secret key
OPENINFERENCE_ENABLED=false            # Enable OpenInference (default: false)
TRACELOOP_API_KEY=                     # Traceloop API key

# Logging
LOG_LEVEL=INFO                         # Logging level (default: INFO)
TELEMETRY_OPT_IN=false                 # Telemetry opt-in (default: false)

# Registry
REGISTRY_FILE=registry.yaml            # Tool registry path (default: registry.yaml)
```

#### Example: Local Development

```bash
# .env
PROFILE=demo_power
OPENAI_API_KEY=sk-proj-...
MODEL_TEMPERATURE=0.3
VECTOR_BACKEND=local
LOG_LEVEL=DEBUG

# Run local CLI
python -m cuga.cli orchestrate --goal "Find flights to NYC"
```

#### Validation

```python
from cuga.config import validate_mode_env

# Validate local mode environment
errors = validate_mode_env("local")
if errors:
    for var, error in errors.items():
        print(f"❌ {var}: {error}")
    exit(1)

# Output if missing API key:
# ❌ OPENAI_API_KEY: At least one model API key required 
#    (WATSONX_API_KEY, OPENAI_API_KEY, AZURE_OPENAI_API_KEY, GROQ_API_KEY, or ANTHROPIC_API_KEY)
```

---

## Provider-Specific Configuration

### IBM Watsonx / Granite 4.0 (Default Provider)

**Granite 4.0** is the default LLM provider with deterministic, reproducible outputs (temperature=0.0).

#### Required Environment Variables

```bash
WATSONX_API_KEY=...                    # IBM Cloud API key (required)
WATSONX_PROJECT_ID=...                 # Watsonx project ID (required)
```

#### Optional Environment Variables

```bash
WATSONX_URL=...                        # Watsonx API endpoint (optional, defaults to IBM Cloud)
MODEL_NAME=granite-4-h-small           # Granite 4.0 model variant (default: granite-4-h-small)
```

#### Available Granite 4.0 Models

| Model ID | Description | Use Case | Max Tokens |
|----------|-------------|----------|------------|
| `granite-4-h-small` | Balanced performance (default) | General purpose, production | 8192 |
| `granite-4-h-micro` | Lightweight, fast inference | High-throughput, cost-sensitive | 8192 |
| `granite-4-h-tiny` | Minimal resource usage | Edge deployment, rapid prototyping | 8192 |

#### Configuration Files

- **Provider defaults**: `src/cuga/providers/watsonx_provider.py`
- **Agent-specific models**: `src/cuga/configurations/models/settings.watsonx.toml`
- **Example usage**: `examples/granite_function_calling.py`

#### Startup Validation

WatsonxProvider validates required credentials at initialization:

```python
from cuga.providers.watsonx_provider import WatsonxProvider

# Raises RuntimeError if WATSONX_API_KEY or WATSONX_PROJECT_ID missing
provider = WatsonxProvider()
```

**Error Message**:
```
RuntimeError: Missing required Watsonx credentials: WATSONX_API_KEY, WATSONX_PROJECT_ID. 
Set these environment variables or pass them to WatsonxProvider constructor. 
See docs/configuration/ENVIRONMENT_MODES.md for setup instructions.
```

#### Deterministic Configuration

Granite 4.0 uses deterministic defaults for reproducible outputs:

- **temperature**: 0.0 (stable, no randomness)
- **decoding_method**: "greedy" (deterministic token selection)
- **seed**: Optional (e.g., `seed=42` for full reproducibility)

```python
# Fully deterministic call
provider = WatsonxProvider(temperature=0.0)
result = provider.generate("hello granite", seed=42)
```

#### LangFlow Integration

Granite 4.0 is available in LangFlow workflows via the `Watsonx Granite` component:

```python
# LangFlow component: src/cuga/langflow_components/watsonx_llm_component.py
display_name = "Watsonx Granite"
```

---

### 2. Service Mode (FastAPI Production)

**Use Case**: Production deployment as HTTP service with authentication, budget enforcement, and observability.

**Entry Points**:
- `uvicorn cuga.backend.app:app`
- Docker container deployment
- Kubernetes service

#### Required Environment Variables

```bash
# Authentication & Security (REQUIRED)
AGENT_TOKEN=secret-token-here          # API authentication token
AGENT_BUDGET_CEILING=100               # Budget ceiling per request
AGENT_BUDGET_POLICY=block              # Budget policy (warn|block)

# Model Configuration (REQUIRED)
OPENAI_API_KEY=sk-...                  # Or other model provider keys
# (Same model key requirements as Local Mode)

# Profile Configuration (REQUIRED for production)
PROFILE=production                     # Execution profile (default: demo_power)

# Server Configuration
PORT=8000                              # HTTP port (default: 8000)
HOST=0.0.0.0                           # HTTP host (default: 0.0.0.0)
```

#### Optional Environment Variables

```bash
# Observability (RECOMMENDED for production)
LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=cuga-production

# Budget & Throttling
AGENT_ESCALATION_MAX=2                 # Escalation limit (default: 2)

# Memory & RAG
VECTOR_BACKEND=chroma                  # Vector store (production recommended)
VECTOR_HOST=chroma.svc.cluster.local
VECTOR_PORT=8000
RAG_ENABLED=true

# Logging
LOG_LEVEL=WARNING                      # Production log level
```

#### Example: Production Service

```bash
# .env.production
AGENT_TOKEN=prod-secret-token-xyz123
AGENT_BUDGET_CEILING=1000
AGENT_BUDGET_POLICY=block
PROFILE=production

OPENAI_API_KEY=sk-proj-prod-...

LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-prod-...
LANGFUSE_SECRET_KEY=sk-lf-prod-...

VECTOR_BACKEND=chroma
VECTOR_HOST=chroma.prod.svc.cluster.local
VECTOR_PORT=8000

PORT=8000
HOST=0.0.0.0
LOG_LEVEL=WARNING

# Run production service
uvicorn cuga.backend.app:app --host 0.0.0.0 --port 8000
```

#### Validation

```python
from cuga.config import validate_mode_env

errors = validate_mode_env("service")
if errors:
    print("❌ Service mode validation failed:")
    for var, error in errors.items():
        print(f"   {var}: {error}")
    exit(1)

# Output if missing AGENT_TOKEN:
# ❌ AGENT_TOKEN: Required for service mode (authentication)
# ❌ AGENT_BUDGET_CEILING: Required for service mode (budget enforcement)
```

#### Security Checklist

- ✅ `AGENT_TOKEN` set (not default/example value)
- ✅ `AGENT_BUDGET_CEILING` appropriate for workload
- ✅ `AGENT_BUDGET_POLICY=block` (not warn) for production
- ✅ `PROFILE=production` (not demo_power)
- ✅ API keys stored securely (secrets manager, not .env files committed)
- ✅ Observability enabled (`LANGFUSE_*` or `OTEL_*`)

---

### 3. MCP Mode (Agent Orchestration)

**Use Case**: Running orchestrator with MCP (Model Context Protocol) servers for multi-agent coordination.

**Entry Points**:
- `python -m cuga.cli orchestrate --mcp`
- `uvicorn cuga.backend.tools_env.registry.registry.api_registry_server:app`
- MCP agent coordinator processes

#### Required Environment Variables

```bash
# MCP Configuration (REQUIRED)
MCP_SERVERS_FILE=./config/mcp_servers.yaml  # MCP servers config
CUGA_PROFILE_SANDBOX=./cuga_workspace/default_profile  # Sandbox directory

# Model Configuration (REQUIRED)
OPENAI_API_KEY=sk-...                  # Or other model provider keys
# (Same model key requirements as Local Mode)

# Profile Configuration
PROFILE=demo_power                     # Execution profile (default: demo_power)
```

#### Optional Environment Variables

```bash
# Planner & Coordinator
PLANNER_STRATEGY=react
PLANNER_MAX_STEPS=10
MODEL_TEMPERATURE=0.3

# Observability (RECOMMENDED for MCP orchestration)
LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...

OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=cuga-mcp

# Memory & RAG
VECTOR_BACKEND=local
RAG_ENABLED=false

# Logging
LOG_LEVEL=INFO

# API Registry Server (if running registry)
CUGA_HOST=127.0.0.1
DYNACONF_SERVER_PORTS__REGISTRY=8001
```

#### Example: MCP Orchestrator

```bash
# .env.mcp
MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml
CUGA_PROFILE_SANDBOX=./cuga_workspace/demo_sandbox

OPENAI_API_KEY=sk-proj-...
PROFILE=demo_power

LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-lf-dev-...
LANGFUSE_SECRET_KEY=sk-lf-dev-...

LOG_LEVEL=INFO

# Run MCP orchestrator
python -m cuga.cli orchestrate --goal "Multi-agent task" --mcp
```

#### MCP Servers Configuration

```yaml
# mcp_servers.yaml
mcpServers:
  vault_tools:
    version: "0.1.0"
    transport: stdio
    command: python
    args: ["-m", "cuga.mcp_servers.vault_tools.server"]
    env:
      CUGA_PROFILE_SANDBOX: "${CUGA_PROFILE_SANDBOX}"
    description: "Vault MCP tools"

  digital_sales_mcp:
    url: "http://127.0.0.1:8000/sse"
    description: "Digital Sales MCP server (SSE)"
    type: mcp_server
```

#### Validation

```python
from cuga.config import validate_mode_env

errors = validate_mode_env("mcp")
if errors:
    print("❌ MCP mode validation failed:")
    for var, error in errors.items():
        print(f"   {var}: {error}")
    exit(1)

# Output if MCP_SERVERS_FILE missing:
# ❌ MCP_SERVERS_FILE: Required for MCP mode (server definitions)
# ❌ CUGA_PROFILE_SANDBOX: Required for MCP mode (sandbox isolation)
```

---

### 4. Test Mode (CI/CD)

**Use Case**: Running automated tests in CI/CD pipelines with isolated, deterministic environments.

**Entry Points**:
- `pytest tests/`
- CI/CD pipelines (GitHub Actions, GitLab CI)

#### Required Environment Variables

```bash
# NONE - Tests should work with defaults and mocks
```

#### Optional Environment Variables (CI/CD Only)

```bash
# Test Configuration
PYTEST_TIMEOUT=60                      # Test timeout (default: 60s)
CUGA_STRICT_CONFIG=0                   # Disable strict config (default: 1)

# Coverage
COV_FAIL_UNDER=1                       # Coverage threshold (default: 1%)

# Temporary Paths
TMPDIR=/tmp                            # Temp directory for test artifacts
```

#### Test Environment Principles

1. **Isolation**: No env var leakage between tests
2. **Mocking**: Mock external API calls (no real API keys needed)
3. **Determinism**: Reproducible results (no network dependencies)
4. **Cleanup**: Teardown temp configs, sandboxes, processes

#### Example: Test Configuration

```python
# conftest.py
import pytest
import os
import tempfile

@pytest.fixture
def isolated_env():
    """Provide isolated environment for tests."""
    original_env = dict(os.environ)
    
    # Set test defaults
    os.environ["PROFILE"] = "test"
    os.environ["OPENAI_API_KEY"] = "sk-test-mock-key"
    os.environ["LOG_LEVEL"] = "ERROR"
    os.environ["TELEMETRY_OPT_IN"] = "false"
    os.environ["LANGFUSE_ENABLED"] = "false"
    
    yield
    
    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

@pytest.fixture
def temp_mcp_config():
    """Create temporary MCP config for tests."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write("""
mcpServers:
  test_server:
    url: "http://localhost:8000/sse"
    description: "Test MCP server"
""")
        config_path = f.name
    
    os.environ["MCP_SERVERS_FILE"] = config_path
    
    yield config_path
    
    # Cleanup
    os.remove(config_path)
    del os.environ["MCP_SERVERS_FILE"]
```

#### Example: Test Invocation

```bash
# Run tests with isolated environment
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/cuga --cov-report=term-missing

# Run specific test mode
pytest tests/unit/ -k "test_local_mode"
```

#### CI/CD Example (GitHub Actions)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: |
          pip install -r constraints.txt
          pip install pytest pytest-cov pytest-asyncio
      
      - name: Run tests (isolated)
        env:
          # No real API keys - tests use mocks
          PROFILE: test
          LOG_LEVEL: ERROR
          TELEMETRY_OPT_IN: false
          LANGFUSE_ENABLED: false
        run: |
          pytest tests/ \
            --cov=src/cuga \
            --cov-report=term-missing \
            --cov-fail-under=1
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

#### Validation

```python
# No validation needed - tests should work with defaults
# Tests use mocks for external dependencies

def test_local_mode_defaults():
    """Test local mode works with minimal env."""
    from cuga.config import AgentConfig
    
    config = AgentConfig.from_env()
    assert config.profile == "demo_power"  # Default
    assert config.max_steps == 6           # Default
    assert config.temperature == 0.3       # Default
```

---

## Environment Variable Reference

### Core Configuration

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **PROFILE** | Optional | **Required** | Optional | N/A | `demo_power` | Execution profile (demo_power, production, restricted) |
| **OPENAI_API_KEY** | **Required*** | **Required*** | **Required*** | Mocked | None | OpenAI API key |
| **AZURE_OPENAI_API_KEY** | **Required*** | **Required*** | **Required*** | Mocked | None | Azure OpenAI key |
| **AZURE_OPENAI_ENDPOINT** | **Required*** | **Required*** | **Required*** | Mocked | None | Azure endpoint |
| **GROQ_API_KEY** | **Required*** | **Required*** | **Required*** | Mocked | None | Groq API key |
| **IBM_WATSONX_APIKEY** | **Required*** | **Required*** | **Required*** | Mocked | None | IBM Watsonx key |

*At least one model API key required

### Service Mode (Authentication & Budget)

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **AGENT_TOKEN** | N/A | **Required** | N/A | N/A | None | API authentication token |
| **AGENT_BUDGET_CEILING** | N/A | **Required** | N/A | N/A | `100` | Budget ceiling per request |
| **AGENT_BUDGET_POLICY** | N/A | Optional | N/A | N/A | `warn` | Budget policy (warn\|block) |
| **AGENT_ESCALATION_MAX** | N/A | Optional | N/A | N/A | `2` | Escalation limit |

### MCP Mode (Orchestration)

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **MCP_SERVERS_FILE** | N/A | N/A | **Required** | Temp | `mcp_servers.yaml` | MCP servers config path |
| **CUGA_PROFILE_SANDBOX** | N/A | N/A | **Required** | Temp | `./cuga_workspace/default_profile` | Sandbox directory |
| **REGISTRY_FILE** | Optional | Optional | Optional | N/A | `registry.yaml` | Tool registry path |

### Planner & Coordinator

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **PLANNER_STRATEGY** | Optional | Optional | Optional | N/A | `react` | Planning strategy (react\|plan_execute) |
| **PLANNER_MAX_STEPS** | Optional | Optional | Optional | N/A | `6` | Max planning steps (1-50) |
| **MODEL_TEMPERATURE** | Optional | Optional | Optional | N/A | `0.3` | Model temperature (0.0-2.0) |

### Memory & RAG

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **VECTOR_BACKEND** | Optional | Optional | Optional | N/A | `local` | Vector store (chroma\|qdrant\|weaviate\|milvus\|local) |
| **VECTOR_HOST** | Optional | Optional | Optional | N/A | `localhost` | Vector store host |
| **VECTOR_PORT** | Optional | Optional | Optional | N/A | `6333` | Vector store port |
| **VECTOR_NAMESPACE** | Optional | Optional | Optional | N/A | `cuga-demo` | Vector namespace |
| **RAG_ENABLED** | Optional | Optional | Optional | N/A | `false` | Enable RAG retrieval |

### Observability

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **LANGFUSE_ENABLED** | Optional | **Recommended** | **Recommended** | N/A | `false` | Enable Langfuse tracing |
| **LANGFUSE_HOST** | Optional | **Recommended** | **Recommended** | N/A | None | Langfuse host URL |
| **LANGFUSE_PUBLIC_KEY** | Optional | **Recommended** | **Recommended** | N/A | None | Langfuse public key |
| **LANGFUSE_SECRET_KEY** | Optional | **Recommended** | **Recommended** | N/A | None | Langfuse secret key |
| **OPENINFERENCE_ENABLED** | Optional | Optional | Optional | N/A | `false` | Enable OpenInference |
| **TRACELOOP_API_KEY** | Optional | Optional | Optional | N/A | None | Traceloop API key |
| **OTEL_EXPORTER_OTLP_ENDPOINT** | Optional | Optional | Optional | N/A | None | OTEL collector endpoint |
| **OTEL_SERVICE_NAME** | Optional | Optional | Optional | N/A | `cuga` | OTEL service name |

### Server Configuration

| Variable | Local | Service | MCP | Test | Default | Description |
|----------|-------|---------|-----|------|---------|-------------|
| **PORT** | N/A | Optional | Optional | N/A | `8000` | HTTP server port |
| **HOST** | N/A | Optional | Optional | N/A | `127.0.0.1` | HTTP server host |
| **CUGA_HOST** | N/A | Optional | Optional | N/A | `127.0.0.1` | CUGA internal host |
| **LOG_LEVEL** | Optional | Optional | Optional | N/A | `INFO` | Logging level (DEBUG\|INFO\|WARNING\|ERROR) |
| **TELEMETRY_OPT_IN** | Optional | Optional | Optional | N/A | `false` | Telemetry opt-in |

## Environment Validation

### Validation Script

```python
# scripts/validate_env.py
import os
import sys
from typing import Dict, List

def validate_model_keys() -> List[str]:
    """Validate at least one model API key is present."""
    keys = [
        "OPENAI_API_KEY",
        "AZURE_OPENAI_API_KEY",
        "GROQ_API_KEY",
        "IBM_WATSONX_APIKEY",
    ]
    
    for key in keys:
        if os.getenv(key):
            return []
    
    return [f"At least one model API key required: {', '.join(keys)}"]

def validate_mode_env(mode: str) -> Dict[str, List[str]]:
    """Validate environment for specific mode."""
    errors = {}
    
    # Common validation (all modes except test)
    if mode != "test":
        model_errors = validate_model_keys()
        if model_errors:
            errors["MODEL_KEYS"] = model_errors
    
    # Service mode validation
    if mode == "service":
        if not os.getenv("AGENT_TOKEN"):
            errors["AGENT_TOKEN"] = ["Required for service mode (authentication)"]
        
        if not os.getenv("AGENT_BUDGET_CEILING"):
            errors["AGENT_BUDGET_CEILING"] = ["Required for service mode (budget enforcement)"]
        
        profile = os.getenv("PROFILE", "demo_power")
        if profile == "demo_power":
            errors["PROFILE"] = ["Production profile recommended for service mode (not demo_power)"]
    
    # MCP mode validation
    if mode == "mcp":
        if not os.getenv("MCP_SERVERS_FILE"):
            errors["MCP_SERVERS_FILE"] = ["Required for MCP mode (server definitions)"]
        
        if not os.getenv("CUGA_PROFILE_SANDBOX"):
            errors["CUGA_PROFILE_SANDBOX"] = ["Required for MCP mode (sandbox isolation)"]
    
    return errors

if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "local"
    errors = validate_mode_env(mode)
    
    if errors:
        print(f"❌ Environment validation failed for mode: {mode}")
        for var, msgs in errors.items():
            print(f"\n{var}:")
            for msg in msgs:
                print(f"  - {msg}")
        sys.exit(1)
    else:
        print(f"✅ Environment validated for mode: {mode}")
        sys.exit(0)
```

### Usage

```bash
# Validate local mode
python scripts/validate_env.py local

# Validate service mode
python scripts/validate_env.py service

# Validate MCP mode
python scripts/validate_env.py mcp
```

## Troubleshooting

### Problem: Service mode failing with 500 error

**Symptom**: `RuntimeError: AGENT_TOKEN not configured`

**Solution**: Set `AGENT_TOKEN` environment variable:

```bash
export AGENT_TOKEN=your-secret-token-here
```

### Problem: MCP orchestrator can't find servers

**Symptom**: `MCP_SERVERS_FILE not found`

**Solution**: Set `MCP_SERVERS_FILE` to valid config path:

```bash
export MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml
```

### Problem: Tests failing with API errors

**Symptom**: Tests trying to call real APIs

**Solution**: Ensure tests use isolated environment and mocks:

```python
@pytest.fixture
def isolated_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-mock")
    monkeypatch.setenv("LANGFUSE_ENABLED", "false")
    monkeypatch.setenv("TELEMETRY_OPT_IN", "false")
```

### Problem: Mode confusion (wrong env vars for mode)

**Symptom**: Environment variables from one mode interfering with another

**Solution**: Use mode-specific .env files:

```bash
# Local mode
cp .env.example .env.local
ln -sf .env.local .env

# Service mode
cp .env.example .env.production
# Edit .env.production with service-specific vars

# Use specific env file
dotenv -f .env.production run uvicorn cuga.backend.app:app
```

## Migration Guide

### From Ad-Hoc to Mode-Specific Environments

**Step 1**: Identify current execution mode

```bash
# What am I running?
# - Local CLI? → Local Mode
# - Production API? → Service Mode
# - MCP orchestrator? → MCP Mode
# - CI/CD tests? → Test Mode
```

**Step 2**: Create mode-specific .env file

```bash
# Copy template
cp .env.example .env.<mode>

# Edit with mode-specific requirements
vim .env.<mode>
```

**Step 3**: Validate environment

```bash
# Load env and validate
dotenv -f .env.<mode> python scripts/validate_env.py <mode>
```

**Step 4**: Update launch configuration

```bash
# Local mode
dotenv -f .env.local python -m cuga.cli orchestrate --goal "task"

# Service mode
dotenv -f .env.production uvicorn cuga.backend.app:app

# MCP mode
dotenv -f .env.mcp python -m cuga.cli orchestrate --goal "task" --mcp
```

## FAQ

### Q: Can I use the same environment for multiple modes?

**A**: Not recommended. Each mode has different requirements:
- **Local** mode doesn't need `AGENT_TOKEN`
- **Service** mode requires `AGENT_TOKEN` and `AGENT_BUDGET_CEILING`
- **MCP** mode requires `MCP_SERVERS_FILE` and `CUGA_PROFILE_SANDBOX`

Use mode-specific `.env` files (`.env.local`, `.env.production`, `.env.mcp`).

### Q: What happens if I don't set required variables?

**A**: 
- **Local mode**: Defaults to `demo_power` profile, local vector backend
- **Service mode**: Fails with `RuntimeError` (missing `AGENT_TOKEN` or budget config)
- **MCP mode**: Fails with `FileNotFoundError` (missing `MCP_SERVERS_FILE`)
- **Test mode**: Works with defaults and mocks

### Q: How do I know which mode I'm in?

**A**: Check the entry point:
- `python -m cuga.cli` → Local Mode
- `uvicorn cuga.backend.app:app` → Service Mode
- `MCP_SERVERS_FILE` set → MCP Mode
- `pytest tests/` → Test Mode

### Q: Can I override mode defaults?

**A**: Yes, via environment variables or CLI arguments:

```bash
# Override local mode defaults
PROFILE=production python -m cuga.cli orchestrate --goal "task"

# Override service mode defaults
AGENT_BUDGET_CEILING=500 uvicorn cuga.backend.app:app
```

### Q: What about Docker/Kubernetes deployments?

**A**: Use ConfigMaps/Secrets for environment variables:

```yaml
# kubernetes-deployment.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cuga-config
data:
  PROFILE: production
  AGENT_BUDGET_CEILING: "1000"
  LANGFUSE_ENABLED: "true"
---
apiVersion: v1
kind: Secret
metadata:
  name: cuga-secrets
type: Opaque
stringData:
  AGENT_TOKEN: prod-secret-token
  OPENAI_API_KEY: sk-proj-prod-...
  LANGFUSE_SECRET_KEY: sk-lf-prod-...
---
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: cuga-service
        envFrom:
        - configMapRef:
            name: cuga-config
        - secretRef:
            name: cuga-secrets
```

## Change Management

Environment mode documentation changes require:

1. **Update this doc**: Document new variables or modes
2. **Update validation script**: Add validation logic
3. **Update `.env.example`**: Add new variables with comments
4. **Update tests**: Cover new environment requirements
5. **Update `AGENTS.md`**: Guardrail changes if validation rules change
6. **Update `CHANGELOG.md`**: Record environment changes

All changes MUST maintain backward compatibility for existing environment variables unless explicitly documented as breaking changes.

---

**See Also**:
- `docs/configuration/CONFIG_RESOLUTION.md` - Configuration precedence and resolution
- `docs/configuration/QUICK_REFERENCE.md` - Quick configuration reference
- `.env.example` - Environment variable template
- `AGENTS.md` - Agent guardrails and policies
