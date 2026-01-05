# Configuration Resolution Strategy

**Status**: Canonical  
**Last Updated**: 2025-12-31  
**Owner**: Configuration Team

## Problem Statement

### Before: Scattered Configuration

```
Config sources scattered across:
   ├── config/ (Hydra registry fragments)
   ├── configs/ (agent/memory/RAG/observability YAMLs)
   ├── configurations/ (MCP server definitions, policies, profiles)
   ├── .env.example (environment variable templates)
   ├── .env.mcp (MCP-specific sandbox env)
   ├── registry.yaml (root tool registry)
   ├── settings.toml (LLM/backend settings)
   ├── eval_config.toml (evaluation settings)
   └── Multiple loaders:
       ├── Dynaconf (settings.py, memory config)
       ├── Hydra/OmegaConf (MCP v2 registry)
       ├── Direct YAML (sandbox, old registry)
       ├── TOML (settings, eval config)
       └── os.getenv() (scattered across codebase)

Impact:
   ├── No documented precedence order
   ├── Hard to reason about runtime behavior
   ├── Config conflicts undetected
   ├── Observability gaps (where did this value come from?)
   └── Testing brittleness (env state leakage)
```

### After: Unified Resolution

```
Clear precedence layers (highest → lowest):
   1. CLI Arguments (--profile production)
   2. Environment Variables (PROFILE=production)
   3. .env Files (.env.mcp, .env, .env.example)
   4. YAML Configs (configs/*.yaml, config/registry.yaml)
   5. TOML Configs (settings.toml, eval_config.toml)
   6. Configuration Defaults (configurations/_shared/*.yaml)
   7. Hardcoded Defaults (in code)

Single ConfigResolver with:
   ├── Explicit precedence enforcement
   ├── Deep merge support (dicts/lists)
   ├── Schema validation (required fields, types)
   ├── Observability (provenance tracking)
   └── Testing support (isolation, fixtures)
```

## Configuration Landscape

### Directory Structure

| Directory | Purpose | Loader | Precedence |
|-----------|---------|--------|-----------|
| **config/** | Hydra registry fragments for MCP v2 | Hydra `compose()` | Layer 4 (YAML) |
| **configs/** | Agent/memory/RAG/observability configs | Dynaconf, direct YAML | Layer 4 (YAML) |
| **configurations/** | MCP server defs, policies, profiles | Direct YAML, Dynaconf | Layer 6 (Defaults) |
| **.env.example** | Environment variable templates | `dotenv` (reference only) | N/A (template) |
| **.env.mcp** | MCP sandbox environment | `dotenv` | Layer 3 (.env) |
| **.env** | User environment overrides | `dotenv` | Layer 3 (.env) |
| **registry.yaml** | Root tool registry | Direct YAML, Hydra | Layer 4 (YAML) |
| **settings.toml** | LLM/backend settings | `tomllib`, Dynaconf | Layer 5 (TOML) |
| **eval_config.toml** | Evaluation configuration | `tomllib`, Dynaconf | Layer 5 (TOML) |

### Current Loaders

1. **Dynaconf** (`src/cuga/config.py`):
   - Loads: `settings.toml`, `.env`, `eval_config.toml`, model/mode configs
   - Features: Validators, multi-file composition, env var overrides
   - Scope: LLM settings, backend config, feature flags

2. **Hydra/OmegaConf** (`src/cuga/mcp_v2/registry/loader.py`):
   - Loads: `config/registry.yaml` + fragments
   - Features: Composition, env interpolation `${oc.env:VAR,default}`, defaults
   - Scope: MCP v2 registry (servers, tools, routes)

3. **Direct YAML** (`src/mcp/loader.py`, `sandbox/registry_based_runner.py`):
   - Loads: `registry.yaml`, sandbox policies, MCP server configs
   - Features: Simple parsing, no composition
   - Scope: Legacy registry, sandbox runner, simple configs

4. **TOML** (`src/cuga/config.py`, `src/cuga/mcp/config.py`):
   - Loads: `settings.toml`, `settings.mcp.toml`, eval configs
   - Features: Type-safe, nested structures
   - Scope: LLM settings, MCP pool config, evaluation params

5. **os.getenv()** (scattered):
   - Loads: Environment variables directly
   - Features: Simple key-value lookup
   - Scope: Quick config reads (PROFILE, CUGA_HOST, feature flags)

## Schema Validation

### Pydantic Schemas

All configuration files are validated using Pydantic schemas for fail-fast error detection:

#### ToolRegistry Schema (`src/cuga/config/schemas/registry_schema.py`)

```python
from pydantic import BaseModel, field_validator

class ToolRegistryEntry(BaseModel):
    module: str  # Must start with "cuga.modular.tools."
    handler: str
    description: str  # Min 10 chars
    sandbox_profile: SandboxProfile  # py_slim, py_full, node_slim, node_full, orchestrator
    mounts: List[str] = []  # Format: "source:dest:mode" (mode: ro/rw)
    budget: Optional[ToolBudget] = None

class ToolRegistry(BaseModel):
    tools: Dict[str, ToolRegistryEntry]
    
    @field_validator('tools')
    def no_duplicate_modules(cls, tools):
        # Enforce unique module paths
        ...
```

**Validations:**
- Module allowlist: `module` must start with `cuga.modular.tools.*`
- Mount syntax: `source:dest:mode` with valid mode (`ro`/`rw`)
- Budget bounds: `max_tokens <= 100000`, `max_calls_per_session <= 10000`
- Unique constraints: No duplicate modules or tool names
- Description quality: Min 10 chars, no placeholder text

#### GuardsConfig Schema (`src/cuga/config/schemas/guards_schema.py`)

```python
class GuardCondition(BaseModel):
    field: str  # Dot notation: "request.user.role"
    operator: str  # eq, ne, in, not_in, gt, lt, gte, lte, contains, regex
    value: Any

class RoutingGuard(BaseModel):
    name: str  # Snake_case identifier
    priority: int = 50  # 0-100
    conditions: List[GuardCondition]
    actions: List[GuardAction]
```

**Validations:**
- Field path syntax: Valid dot notation for nested fields
- Operator validation: Only allowed operators (eq/ne/in/not_in/gt/lt/gte/lte/contains/regex)
- Value type matching: Value type must match operator (e.g., `in` requires list)
- Priority conflicts: Warn on same-priority guards with overlapping conditions
- Action validation: `route_to` requires `target` field

#### AgentConfig Schema (`src/cuga/config/schemas/agent_schema.py`)

```python
class AgentLLMConfig(BaseModel):
    provider: str  # watsonx, openai, anthropic, azure, groq, ollama
    model: str
    temperature: float = 0.7  # 0.0-2.0
    max_tokens: int = 4096  # 1-128000
    api_key: Optional[str] = None  # Warns if hardcoded
    
class AgentConfig(BaseModel):
    agent_type: str  # planner, worker, coordinator
    max_retries: int = 3  # 0-10
    timeout: float = 300.0  # 1-3600s
    llm: AgentLLMConfig
```

**Validations:**
- Provider validation: Only allowed providers
- Temperature bounds: 0.0-2.0 with warnings for non-deterministic values
- Timeout reasonableness: 1-3600 seconds
- API key warnings: Warns if `api_key` hardcoded (prefer env vars)
- Deterministic defaults: `temperature=0.0` for watsonx

#### MemoryConfig & ObservabilityConfig

```python
class MemoryConfig(BaseModel):
    backend: str  # local, faiss, chroma, qdrant
    retention_days: Optional[int] = None  # 1-3650
    
class ObservabilityConfig(BaseModel):
    emitter_type: str  # base, langfuse, openinference, otel
    trace_sampling_rate: float = 1.0  # 0.0-1.0
    redact_secrets: bool = True
```

### ConfigValidator Usage

```python
from cuga.config import ConfigValidator

# Validate registry
with open("config/registry.yaml") as f:
    registry_data = yaml.safe_load(f)
ConfigValidator.validate_registry(registry_data)  # Raises ValueError on failure

# Validate guards
with open("config/guards.yaml") as f:
    guards_data = yaml.safe_load(f)
ConfigValidator.validate_guards(guards_data)

# Validate agent config
with open("configs/agent.demo.yaml") as f:
    agent_config = yaml.safe_load(f)
ConfigValidator.validate_agent_config(agent_config)
```

### Fail-Fast Behavior

**Invalid Configuration:**
```yaml
# config/registry.yaml - INVALID
tools:
  malicious_tool:
    module: "evil.tools.backdoor"  # ❌ Not in allowlist
    handler: "run"
    sandbox_profile: "py_slim"
    mounts:
      - "/tmp:invalid"  # ❌ Invalid mount syntax (missing mode)
```

**Error Message:**
```
❌ Registry validation failed
Validation error for ToolRegistry:
tools -> malicious_tool -> module
  Value error, Module must start with 'cuga.modular.tools.' (allowlist enforcement) [type=value_error]
tools -> malicious_tool -> mounts -> 0
  Value error, Mount must follow 'source:dest:mode' format (got '/tmp:invalid') [type=value_error]
```

**Valid Configuration:**
```yaml
# config/registry.yaml - VALID
tools:
  file_search:
    module: "cuga.modular.tools.file_search"  # ✅ In allowlist
    handler: "search_files"
    description: "Search for files matching patterns"  # ✅ Min 10 chars
    sandbox_profile: "py_slim"
    mounts:
      - "/workdir:/workdir:ro"  # ✅ Valid mount syntax
    budget:
      max_tokens: 50000  # ✅ Within bounds
      max_calls_per_session: 100
```

## Precedence Rules

### Precedence Layers (Highest → Lowest)

```
┌─────────────────────────────────────────────┐
│ Layer 1: CLI Arguments                       │
│ --profile production --max-steps 10          │
│ Highest precedence, explicit user intent     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 2: Environment Variables               │
│ PROFILE=production PLANNER_MAX_STEPS=10      │
│ Runtime overrides, CI/CD configuration       │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 3: .env Files                          │
│ .env > .env.mcp > .env.example               │
│ User-local overrides, not committed          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 4: YAML Configs                        │
│ configs/*.yaml > config/registry.yaml        │
│ Structured config, profile-specific          │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 5: TOML Configs                        │
│ settings.toml, eval_config.toml              │
│ Type-safe backend config                     │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 6: Configuration Defaults              │
│ configurations/_shared/*.yaml                │
│ Shared defaults, templates                   │
└─────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────┐
│ Layer 7: Hardcoded Defaults                  │
│ default="demo_power", max_steps=6            │
│ Lowest precedence, last resort               │
└─────────────────────────────────────────────┘
```

### Resolution Algorithm

```python
def resolve_config(key: str, context: dict) -> Any:
    """
    Resolve configuration value with explicit precedence.
    
    Returns tuple of (value, source) for observability.
    """
    # Layer 1: CLI Arguments
    if key in context.get("cli_args", {}):
        return context["cli_args"][key], "cli"
    
    # Layer 2: Environment Variables
    env_key = key.upper()
    if env_key in os.environ:
        return os.environ[env_key], "env"
    
    # Layer 3: .env Files
    for env_file in [".env", ".env.mcp", ".env.example"]:
        value = load_from_env_file(env_file, key)
        if value is not None:
            return value, f"env_file:{env_file}"
    
    # Layer 4: YAML Configs
    yaml_sources = [
        f"configs/{context.get('profile', 'default')}.yaml",
        "config/registry.yaml",
        "registry.yaml",
    ]
    for yaml_file in yaml_sources:
        value = load_from_yaml(yaml_file, key)
        if value is not None:
            return value, f"yaml:{yaml_file}"
    
    # Layer 5: TOML Configs
    toml_sources = ["settings.toml", "eval_config.toml"]
    for toml_file in toml_sources:
        value = load_from_toml(toml_file, key)
        if value is not None:
            return value, f"toml:{toml_file}"
    
    # Layer 6: Configuration Defaults
    default_path = f"configurations/_shared/{key}.yaml"
    value = load_from_yaml(default_path, key)
    if value is not None:
        return value, f"default:{default_path}"
    
    # Layer 7: Hardcoded Defaults
    if key in HARDCODED_DEFAULTS:
        return HARDCODED_DEFAULTS[key], "hardcoded"
    
    raise ConfigurationError(f"Configuration key '{key}' not found")
```

## Merge Strategies

### Deep Merge (Dictionaries)

```python
# Layer 4 (YAML): configs/agent.demo.yaml
{
    "model": {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "temperature": 0.3,
    },
    "planner": {
        "strategy": "react",
        "max_steps": 6,
    }
}

# Layer 2 (Env Var): MODEL_TEMPERATURE=0.7
# Layer 1 (CLI Arg): --max-steps 10

# Result (deep merge):
{
    "model": {
        "provider": "openai",         # From YAML
        "model": "gpt-4o-mini",        # From YAML
        "temperature": 0.7,            # From ENV (overrides YAML)
    },
    "planner": {
        "strategy": "react",           # From YAML
        "max_steps": 10,               # From CLI (overrides YAML)
    }
}
```

### List Override (Arrays)

```python
# Layer 4 (YAML): registry.yaml
{
    "servers": {
        "mock_filesystem": {...},
        "mock_crm": {...},
    }
}

# Layer 3 (.env): ENABLED_SERVERS=mock_filesystem

# Result (list override - NOT merge):
{
    "servers": {
        "mock_filesystem": {...}  # Only enabled server
    }
}
```

**Rule**: Lists OVERRIDE (not merge) to avoid duplicate entries.

### Scalar Override

```python
# Layer 5 (TOML): settings.toml
profile = "demo_power"

# Layer 2 (Env): PROFILE=production

# Result: "production" (env overrides TOML)
```

**Rule**: Scalars always override (string, int, float, bool).

## Configuration Schema

### Core Configuration Keys

```yaml
# Agent Configuration
profile: str               # Execution profile (demo_power, production, restricted)
strategy: str              # Planner strategy (react, plan_execute)
max_steps: int             # Maximum planning steps (1-50)
temperature: float         # Model temperature (0.0-2.0)

# Model Configuration
model:
  provider: str            # LLM provider (openai, azure, groq, watsonx)
  model: str               # Model name (gpt-4o-mini, llama-3, granite-13b)
  base_url: str            # Custom API endpoint
  api_key: str             # API key (use env vars!)
  timeout_s: int           # Request timeout
  max_retries: int         # Retry attempts

# Memory & RAG
vector_backend: str        # Vector store (chroma, qdrant, weaviate, milvus, local)
vector_host: str           # Vector store host
vector_port: int           # Vector store port
vector_namespace: str      # Namespace for isolation
rag_enabled: bool          # Enable RAG retrieval
memory_scope: str          # Memory isolation scope

# Observability
observability_enabled: bool
langfuse_enabled: bool
langfuse_host: str
langfuse_public_key: str
langfuse_secret_key: str
openinference_enabled: bool
traceloop_api_key: str

# Sandbox & Registry
registry_file: str         # Tool registry path (registry.yaml)
mcp_servers_file: str      # MCP servers config
cuga_profile_sandbox: str  # Sandbox workspace directory

# Server
port: int                  # HTTP server port
host: str                  # HTTP server host
log_level: str             # Logging level (DEBUG, INFO, WARN, ERROR)

# Feature Flags
telemetry_opt_in: bool
local_sandbox: bool
tracker_enabled: bool
enable_memory: bool
enable_web_search: bool
```

### Validation Rules

```python
# Required Fields
REQUIRED_KEYS = [
    "profile",
    "model.provider",
    "model.model",
]

# Type Constraints
TYPE_CONSTRAINTS = {
    "max_steps": (int, range(1, 51)),
    "temperature": (float, range(0.0, 2.1)),
    "port": (int, range(1, 65536)),
    "profile": (str, ["demo_power", "production", "restricted"]),
}

# Dependency Rules
DEPENDENCIES = {
    "memory_scope": ["user_id"],  # memory_scope requires user_id
    "rag_enabled": ["vector_backend"],  # RAG requires vector backend
    "langfuse_enabled": ["langfuse_public_key", "langfuse_secret_key"],
}
```

## Configuration Examples

### Example 1: Local Development

```bash
# .env
PROFILE=demo_power
MODEL_TEMPERATURE=0.3
VECTOR_BACKEND=local
RAG_ENABLED=false
LOG_LEVEL=DEBUG
```

```yaml
# configs/agent.demo.yaml
profile: demo_power
model:
  provider: openai
  model: gpt-4o-mini
planner:
  strategy: react
  max_steps: 6
```

**Resolution**:
- `profile`: `"demo_power"` (both .env and YAML agree)
- `model.temperature`: `0.3` (from .env, overrides YAML default)
- `model.provider`: `"openai"` (from YAML, no env override)
- `vector_backend`: `"local"` (from .env)
- `log_level`: `"DEBUG"` (from .env)

### Example 2: Production with Overrides

```bash
# Environment Variables
export PROFILE=production
export MODEL_TEMPERATURE=0.1
export PLANNER_MAX_STEPS=20
export LANGFUSE_ENABLED=true
export LANGFUSE_HOST=https://cloud.langfuse.com
```

```yaml
# configs/agent.production.yaml
profile: production
model:
  provider: azure
  model: gpt-4o
  timeout_s: 120
planner:
  strategy: plan_execute
  max_steps: 10  # Overridden by env
observability:
  langfuse: true
  openinference: false
```

**Resolution**:
- `profile`: `"production"` (env matches YAML)
- `model.temperature`: `0.1` (env overrides YAML default 0.3)
- `planner.max_steps`: `20` (env overrides YAML value 10)
- `model.provider`: `"azure"` (from YAML, no env override)
- `observability.langfuse`: `true` (from YAML and env agree)

### Example 3: CLI Arguments (Highest Precedence)

```bash
# CLI invocation
python -m cuga.cli orchestrate \
    --goal "Book flight to NYC" \
    --profile production \
    --max-steps 5 \
    --temperature 0.0
```

```bash
# Environment (ignored for CLI-specified keys)
export PROFILE=demo_power
export PLANNER_MAX_STEPS=10
export MODEL_TEMPERATURE=0.7
```

**Resolution**:
- `profile`: `"production"` (CLI overrides env)
- `max_steps`: `5` (CLI overrides env)
- `temperature`: `0.0` (CLI overrides env)

**Rule**: CLI arguments always win.

## Configuration Providers

### ConfigResolver Implementation (Phase 3)

**Status**: Implemented  
**Location**: `src/cuga/config/resolver.py`

#### Architecture

```python
from cuga.config import ConfigResolver, ConfigLayer, ConfigValue

# Create resolver with multiple sources
resolver = ConfigResolver()

# Add sources in any order (sorted by layer automatically)
resolver.add_source(EnvSource(prefixes=["CUGA_", "AGENT_"]))
resolver.add_source(YAMLSource("configs/agent.yaml"))
resolver.add_source(TOMLSource("settings.toml"))
resolver.add_source(DefaultSource("configurations/_shared"))

# Resolve all sources
resolver.resolve()

# Get value with provenance
value = resolver.get("llm.model")
print(value)  # llm.model = granite-4-h-small (from ENV via WATSONX_MODEL)

# Get raw value only
model_name = resolver.get_value("llm.model")

# List all keys
print(resolver.keys())  # ['llm.model', 'llm.temperature', ...]

# Dump all config with provenance
dump = resolver.dump()
for key, provenance in dump.items():
    print(provenance)
```

#### ConfigLayer Precedence

```python
class ConfigLayer(IntEnum):
    """Higher value = higher precedence."""
    HARDCODED = 1   # Hardcoded defaults in source code
    DEFAULT = 2     # configurations/_shared/*.yaml
    TOML = 3        # settings.toml, eval_config.toml
    YAML = 4        # configs/*.yaml, config/registry.yaml
    DOTENV = 5      # .env.mcp, .env, .env.example
    ENV = 6         # os.environ (direct environment variables)
    CLI = 7         # CLI arguments (highest)
```

#### ConfigValue Provenance

```python
@dataclass(frozen=True)
class ConfigValue:
    """Immutable config value with full provenance."""
    value: Any                # The actual configuration value
    layer: ConfigLayer        # Which precedence layer provided this
    source: str               # Source identifier (filename, "os.environ", etc.)
    path: str                 # Dotted path (e.g., "llm.model.platform")
    timestamp: datetime       # When resolved (for debugging)
```

#### ConfigSource Interface

```python
class ConfigSource(ABC):
    """Abstract interface for configuration sources."""
    
    @property
    @abstractmethod
    def layer(self) -> ConfigLayer:
        """The precedence layer this source provides."""
        pass
    
    @property
    @abstractmethod
    def source_name(self) -> str:
        """Identifier for this source."""
        pass
    
    @abstractmethod
    def load(self) -> Dict[str, Any]:
        """Load configuration from this source."""
        pass
```

**Implementations**:
- `EnvSource`: Loads from `os.environ` with prefix filtering and nested key support (`AGENT__LLM__MODEL` → `agent.llm.model`)
- `DotEnvSource`: Parses .env files with quote stripping and nested keys
- `YAMLSource`: Loads YAML files with `yaml.safe_load()`
- `TOMLSource`: Loads TOML files with `tomllib.load()`
- `DefaultSource`: Loads and merges multiple YAML files from configurations/_shared/

#### Deep Merge Algorithm

```python
# For nested dicts, merge keys recursively
# For scalars/lists, higher precedence wins (override)

base = {"llm": {"model": "base", "temperature": 0.5}}
update = {"llm": {"model": "override"}}

# Result: {"llm": {"model": "override", "temperature": 0.5}}
```

#### Provenance Tracking

All resolved values track their source:

```python
resolver = ConfigResolver()
resolver.add_source(YAMLSource("configs/agent.yaml"))
resolver.add_source(EnvSource())
resolver.resolve()

# Get value with metadata
value = resolver.get("llm.model")
print(f"Value: {value.value}")
print(f"Layer: {value.layer.name}")
print(f"Source: {value.source}")
print(f"Resolved at: {value.timestamp}")

# Output:
# Value: granite-4-h-small
# Layer: ENV
# Source: os.environ
# Resolved at: 2025-12-31 12:34:56.789
```

#### Usage Patterns

**Pattern 1: Basic Resolution**

```python
from cuga.config import ConfigResolver, EnvSource, YAMLSource

resolver = ConfigResolver()
resolver.add_source(YAMLSource("configs/agent.yaml"))
resolver.add_source(EnvSource())
resolver.resolve()

model = resolver.get_value("llm.model", default="granite-4-h-small")
temperature = resolver.get_value("llm.temperature", default=0.0)
```

**Pattern 2: Observability-First**

```python
# Track all config sources for debugging
resolver = ConfigResolver()
resolver.add_source(DefaultSource("configurations/_shared"))
resolver.add_source(TOMLSource("settings.toml"))
resolver.add_source(YAMLSource(f"configs/{profile}.yaml"))
resolver.add_source(DotEnvSource(".env"))
resolver.add_source(EnvSource(prefixes=["CUGA_", "AGENT_"]))
resolver.resolve()

# Log provenance for all keys
for key in resolver.keys():
    logger.info(resolver.get_provenance(key))

# Example output:
# llm.model = granite-4-h-small (from ENV via os.environ)
# llm.temperature = 0.0 (from DOTENV via .env)
# profile = production (from YAML via configs/production.yaml)
```

**Pattern 3: Testing with Overrides**

```python
# In tests, use hardcoded values (no file I/O)
from cuga.config import ConfigResolver, ConfigLayer, ConfigValue

def test_config():
    resolver = ConfigResolver()
    # Manually inject test values
    resolver._cache = {
        "llm.model": "test-model",
        "llm.temperature": 0.0,
    }
    resolver._resolved = {
        "llm.model": ConfigValue("test-model", ConfigLayer.HARDCODED, "test", "llm.model"),
        "llm.temperature": ConfigValue(0.0, ConfigLayer.HARDCODED, "test", "llm.temperature"),
    }
    
    assert resolver.get_value("llm.model") == "test-model"
```

#### Integration with Existing Loaders

ConfigResolver is **additive** — it doesn't replace Dynaconf/Hydra:

```python
# Option 1: Use ConfigResolver alongside Dynaconf
from dynaconf import Dynaconf
from cuga.config import ConfigResolver, TOMLSource, EnvSource

# Dynaconf for complex validation/environments
dynaconf_settings = Dynaconf(settings_files=["settings.toml"])

# ConfigResolver for explicit precedence tracking
resolver = ConfigResolver()
resolver.add_source(TOMLSource("settings.toml"))
resolver.add_source(EnvSource())
resolver.resolve()

# Use whichever fits the use case
model_from_dynaconf = dynaconf_settings.llm.model
model_with_provenance = resolver.get("llm.model")

# Option 2: Migrate gradually (backward compatible)
# Add ConfigResolver calls alongside existing config reads
# Verify both return same value
# Once verified, remove old config reads
```

#### Environment Mode Validation

**Status**: Implemented  
**Location**: `src/cuga/config/validators.py`

```python
from cuga.config import validate_environment_mode, EnvironmentMode, validate_startup

# Validate environment for specific mode
result = validate_environment_mode(EnvironmentMode.SERVICE)

if not result.is_valid:
    print(f"Missing required vars: {result.missing_required}")
    print(f"Suggestions: {result.suggestions}")
    raise RuntimeError("Invalid environment")

# Or use fail-fast validation at startup
validate_startup(EnvironmentMode.SERVICE, fail_fast=True)  # Raises on error
```

**Supported Modes**:
- `LOCAL`: Local CLI development (requires model API key)
- `SERVICE`: FastAPI backend (requires `AGENT_TOKEN`, `AGENT_BUDGET_CEILING`, model API key)
- `MCP`: MCP orchestration (requires `MCP_SERVERS_FILE`, `CUGA_PROFILE_SANDBOX`, model API key)
- `TEST`: CI/test mode (no env vars required, uses defaults/mocks)

**Provider Detection**:

Validates at least one complete provider is configured:

```python
PROVIDER_VARS = {
    "watsonx": ["WATSONX_API_KEY", "WATSONX_PROJECT_ID"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "azure": ["AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT"],
    "groq": ["GROQ_API_KEY"],
}
```

If no provider is complete, suggests Watsonx (default) credentials first.

**Helpful Error Messages**:

```python
# Example validation failure
try:
    validate_startup(EnvironmentMode.SERVICE, fail_fast=True)
except RuntimeError as e:
    print(e)

# Output:
# Environment validation failed for service mode.
# Missing 2 required variables:
#   - AGENT_TOKEN
#   - WATSONX_PROJECT_ID
# 
# Suggestions:
#   • Set AGENT_TOKEN for API authentication (required for service mode). 
#     Generate with: openssl rand -hex 32
#   • Set WATSONX_PROJECT_ID with watsonx.ai project ID. 
#     See: https://dataplatform.cloud.ibm.com/projects
# 
# See docs/configuration/ENVIRONMENT_MODES.md for complete requirements.
```

#### Testing

**Coverage**: 
- `tests/unit/config/test_config_resolution.py` (59 tests)
- `tests/unit/config/test_env_validation.py` (24 tests)

**Key Test Scenarios**:
- Precedence order enforcement (ENV > DOTENV > YAML > TOML > DEFAULT)
- Deep merge for nested dicts
- Override for scalars/lists
- Provenance tracking across all layers
- Missing file graceful handling
- Environment mode validation (all 4 modes)
- Provider detection (watsonx, openai, anthropic, azure, groq)
- Partial credentials detection
- Helpful error messages

**Run Tests**:

```bash
# Run all config tests
pytest tests/unit/config/ -v

# Run with coverage
pytest tests/unit/config/ --cov=src/cuga/config --cov-report=term-missing

# Run specific test class
pytest tests/unit/config/test_config_resolution.py::TestConfigResolver -v
```

---

### Dynaconf Integration

```python
from dynaconf import Dynaconf

settings = Dynaconf(
    root_path=PACKAGE_ROOT,
    settings_files=[
        "settings.toml",
        ".env",
        "eval_config.toml",
    ],
    environments=True,  # Support dev/staging/prod
    load_dotenv=True,   # Auto-load .env
    envvar_prefix="CUGA",  # CUGA_PROFILE=production
    validators=[
        Validator("profile", must_exist=True),
        Validator("max_steps", gte=1, lte=50),
    ],
)
```

**Features**:
- Multi-file composition
- Environment-specific overrides (dev/staging/prod)
- Validators for type/range checking
- Env var prefix (`CUGA_PROFILE` instead of `PROFILE`)

### Hydra Integration

```python
from hydra import compose, initialize_config_dir

# Initialize Hydra with config directory
with initialize_config_dir(config_dir=str(config_dir), version_base=None):
    # Compose config with overrides
    cfg = compose(config_name="registry")
    
    # Access nested config
    servers = cfg.servers
    
    # Env interpolation
    # ${oc.env:SAMPLE_ECHO_URL,"http://localhost:8088"}
```

**Features**:
- Composition via `defaults` lists
- Fragment management (`server_fragments/`)
- Env interpolation `${oc.env:VAR,default}`
- Structured configs (DictConfig)

### Environment Variables

```python
import os

# Direct access
profile = os.getenv("PROFILE", "demo_power")

# Type conversion
max_steps = int(os.getenv("PLANNER_MAX_STEPS", "6"))

# Boolean parsing
rag_enabled = os.getenv("RAG_ENABLED", "false").lower() == "true"
```

**Features**:
- Simple key-value lookup
- Manual type conversion required
- No validation or composition

## Migration Guide

### From Scattered Configs to Unified Resolution

**Step 1: Audit Current Config Sources**

```bash
# Find all config reads
grep -r "os.getenv\|os.environ" src/
grep -r "Dynaconf\|load_dotenv\|yaml.safe_load" src/
grep -r "settings\." src/
```

**Step 2: Document Config Keys**

Create inventory:
```yaml
# config_inventory.yaml
keys:
  - name: PROFILE
    sources: [.env, configs/agent.demo.yaml, CLI --profile]
    type: str
    required: true
    default: "demo_power"
  
  - name: MODEL_TEMPERATURE
    sources: [.env, settings.toml, CLI --temperature]
    type: float
    required: false
    default: 0.3
    constraints: [0.0, 2.0]
```

**Step 3: Migrate to ConfigResolver**

```python
# Before (scattered)
profile = os.getenv("PROFILE", "demo_power")
temperature = float(os.getenv("MODEL_TEMPERATURE", "0.3"))

# After (unified)
from cuga.config import ConfigResolver

resolver = ConfigResolver()
profile = resolver.get("profile", default="demo_power")
temperature = resolver.get("model.temperature", default=0.3, type=float)

# Observability: where did this value come from?
value, source = resolver.get_with_provenance("profile")
print(f"profile={value} (from {source})")
# Output: profile=production (from env:PROFILE)
```

**Step 4: Add Validation**

```python
from cuga.config import ConfigResolver, Validator

resolver = ConfigResolver(
    validators=[
        Validator("profile", required=True, choices=["demo_power", "production"]),
        Validator("max_steps", type=int, gte=1, lte=50),
        Validator("model.temperature", type=float, gte=0.0, lte=2.0),
    ]
)

# Validate all config
errors = resolver.validate()
if errors:
    raise ConfigurationError(f"Invalid config: {errors}")
```

**Step 5: Update Tests**

```python
# Before (env leakage)
def test_planner():
    os.environ["PROFILE"] = "demo_power"
    planner = Planner()
    assert planner.profile == "demo_power"

# After (isolated)
def test_planner():
    resolver = ConfigResolver(overrides={"profile": "demo_power"})
    planner = Planner(config=resolver)
    assert planner.profile == "demo_power"
```

## Testing Strategy

### Configuration Isolation

```python
import pytest
from cuga.config import ConfigResolver

@pytest.fixture
def isolated_config():
    """Provide isolated config resolver for tests."""
    return ConfigResolver(
        sources=[],  # No file loading
        env={},      # Clean environment
        overrides={  # Explicit test values
            "profile": "test",
            "max_steps": 3,
            "temperature": 0.0,
        }
    )

def test_planner_config(isolated_config):
    """Test planner respects config."""
    planner = Planner(config=isolated_config)
    assert planner.profile == "test"
    assert planner.max_steps == 3
```

### Precedence Testing

```python
def test_config_precedence():
    """Test precedence layers work correctly."""
    resolver = ConfigResolver(
        sources=["configs/agent.demo.yaml"],  # Layer 4
        env={"PROFILE": "production"},        # Layer 2
        overrides={"profile": "cli_override"} # Layer 1 (CLI)
    )
    
    # CLI override wins
    assert resolver.get("profile") == "cli_override"
    
    # Without CLI override, env wins
    resolver2 = ConfigResolver(
        sources=["configs/agent.demo.yaml"],
        env={"PROFILE": "production"},
    )
    assert resolver2.get("profile") == "production"
```

### Validation Testing

```python
def test_config_validation():
    """Test config validation catches errors."""
    resolver = ConfigResolver(
        overrides={"max_steps": 100},  # Exceeds max (50)
        validators=[
            Validator("max_steps", gte=1, lte=50),
        ]
    )
    
    errors = resolver.validate()
    assert "max_steps" in errors
    assert "exceeds maximum" in errors["max_steps"]
```

## Troubleshooting

### Problem: Config value not what I expected

**Solution**: Check precedence with provenance tracking:

```python
from cuga.config import ConfigResolver

resolver = ConfigResolver()
value, source = resolver.get_with_provenance("profile")

print(f"Value: {value}")
print(f"Source: {source}")

# Output:
# Value: production
# Source: env:PROFILE
```

**Check order**:
1. CLI args (`cli`)
2. Environment variables (`env:PROFILE`)
3. .env files (`env_file:.env`)
4. YAML configs (`yaml:configs/agent.demo.yaml`)
5. TOML configs (`toml:settings.toml`)
6. Defaults (`default:configurations/_shared/profile.yaml`)
7. Hardcoded (`hardcoded`)

### Problem: Config validation failing

**Solution**: Check validation errors:

```python
resolver = ConfigResolver()
errors = resolver.validate()

if errors:
    for key, error in errors.items():
        print(f"❌ {key}: {error}")

# Output:
# ❌ max_steps: Value 100 exceeds maximum 50
# ❌ model.api_key: Required field missing
```

### Problem: Config conflicts between loaders

**Solution**: Use unified ConfigResolver:

```python
# ❌ Before (conflicts possible)
dynaconf_settings = Dynaconf(settings_files=["settings.toml"])
yaml_config = yaml.safe_load(open("configs/agent.demo.yaml"))
env_profile = os.getenv("PROFILE")

# Which one wins? Unclear!

# ✅ After (explicit precedence)
resolver = ConfigResolver()
profile = resolver.get("profile")  # Precedence guaranteed
```

### Problem: Environment variable not taking effect

**Solution**: Check env var name matches:

```bash
# ❌ Wrong prefix
export PROFILE=production  # Might be ignored if prefix required

# ✅ Correct prefix (if Dynaconf envvar_prefix="CUGA")
export CUGA_PROFILE=production

# ✅ Or use .env file (no prefix required)
echo "PROFILE=production" >> .env
```

## FAQ

### Q: Should I use Dynaconf or Hydra?

**A**: Depends on use case:

- **Dynaconf**: General settings, multi-environment (dev/staging/prod), validators
- **Hydra**: Composition, fragments, registry management, experiment configs
- **ConfigResolver**: Unified precedence across both

**Recommendation**: Use ConfigResolver as single entry point, it handles both backends.

### Q: How do I add a new configuration key?

**A**: Follow this checklist:

1. Add to `.env.example` (template)
2. Add to appropriate YAML/TOML config file
3. Add to schema in `docs/configuration/CONFIG_RESOLUTION.md`
4. Add validator if needed
5. Update tests
6. Document in CHANGELOG.md

### Q: Can I mix environment variables and YAML?

**A**: Yes! Environment variables override YAML:

```yaml
# configs/agent.demo.yaml
model:
  temperature: 0.3
```

```bash
# Override with env var
export MODEL_TEMPERATURE=0.7
```

Result: `model.temperature = 0.7` (env wins)

### Q: How do I debug config resolution?

**A**: Enable config tracing:

```python
from cuga.config import ConfigResolver

resolver = ConfigResolver(trace=True)
profile = resolver.get("profile")

# Output (traces each lookup):
# [CONFIG] Checking cli_args.profile: Not found
# [CONFIG] Checking env:PROFILE: Found "production"
# [CONFIG] Resolved profile="production" (source: env:PROFILE)
```

### Q: What happens if a required config is missing?

**A**: ConfigResolver raises `ConfigurationError`:

```python
resolver = ConfigResolver(
    validators=[
        Validator("model.api_key", required=True),
    ]
)

# Raises: ConfigurationError: Required field 'model.api_key' not found
```

## Change Management

Configuration resolution changes require:

1. **Update this doc**: Document new precedence rules or loaders
2. **Update schema**: Add/modify keys in schema section
3. **Add tests**: Cover new resolution paths
4. **Update `AGENTS.md`**: Guardrail changes if validation rules change
5. **Update `CHANGELOG.md`**: Record config resolution changes
6. **Migration notes**: Provide upgrade path for existing configs

All changes MUST maintain backward compatibility for existing config keys unless explicitly documented as breaking changes.

---

**See Also**:
- `docs/orchestrator/EXECUTION_CONTEXT.md` - Context configuration
- `docs/mcp/registry.yaml` - MCP registry configuration
- `docs/REGISTRY_MERGE.md` - Hydra registry merge semantics
- `src/cuga/config.py` - Dynaconf configuration
- `src/cuga/modular/config.py` - AgentConfig from env
- `src/cuga/mcp_v2/registry/loader.py` - Hydra registry loader

## Migration Guide

### Before: Scattered Configuration Files

```
project_root/
├── registry.yaml                      # Root tool registry
├── docs/mcp/registry.yaml             # MCP tool registry (duplicate)
├── routing/guards.yaml                # Routing guards
├── configurations/models/*.toml       # TOML model configs
└── src/cuga/settings.toml             # Backend settings
```

### After: Unified Configuration Structure

```
project_root/
├── config/
│   ├── registry.yaml                  # Merged tool registry (canonical)
│   ├── guards.yaml                    # Routing guards (moved from routing/)
│   └── defaults/
│       ├── models/*.yaml              # Converted from TOML
│       └── backend.yaml               # Converted from settings.toml
├── configs/
│   ├── agent.demo.yaml                # Agent configurations
│   ├── memory.yaml                    # Memory configurations
│   └── observability.yaml             # Observability configurations
└── backups/
    └── config_backup_YYYYMMDD_HHMMSS/ # Timestamped backups
```

### Running the Migration

**Step 1: Dry Run (Preview Changes)**

```bash
# See what would be changed without modifying files
python scripts/migrate_config.py --dry-run
```

**Step 2: Run Migration with Backups**

```bash
# Apply changes (creates backups automatically)
python scripts/migrate_config.py
```

**Step 3: Update Code References**

Replace scattered config loading with unified ConfigResolver:

```python
# Before: Direct YAML loading
with open("registry.yaml") as f:
    registry = yaml.safe_load(f)

# After: ConfigResolver with validation
from cuga.config import ConfigResolver, ConfigValidator

resolver = ConfigResolver(sources=["config/registry.yaml"])
registry_data = resolver.get("tools")
ConfigValidator.validate_registry({"tools": registry_data})
```

**Step 4: Test and Verify**

```bash
# Run configuration tests
pytest tests/unit/config/ -v

# Verify startup with new config
python src/cuga/main.py --profile demo_power
```

**Step 5: Cleanup Deprecated Files**

```bash
# After confirming everything works
rm registry.yaml docs/mcp/registry.yaml routing/guards.yaml
rm configurations/models/*.toml
```

### Rollback Procedure

If migration causes issues:

```bash
# Restore from timestamped backup
cp -r backups/config_backup_YYYYMMDD_HHMMSS/* .
rm -rf config/  # Clean up migrated files
```
