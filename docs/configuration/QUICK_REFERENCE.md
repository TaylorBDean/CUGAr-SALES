# Configuration Quick Reference

> **Canonical Source**: See `docs/configuration/CONFIG_RESOLUTION.md` for complete documentation.

## Precedence Order (Highest → Lowest)

1. **CLI Arguments** - `--profile production --max-steps 10`
2. **Environment Variables** - `PROFILE=production`
3. **.env Files** - `.env > .env.mcp > .env.example`
4. **YAML Configs** - `configs/*.yaml, config/registry.yaml`
5. **TOML Configs** - `settings.toml, eval_config.toml`
6. **Configuration Defaults** - `configurations/_shared/*.yaml`
7. **Hardcoded Defaults** - In code `default="demo_power"`

## Configuration Sources

| Directory/File | Purpose | Loader | Layer |
|----------------|---------|--------|-------|
| `config/` | Hydra registry fragments (MCP v2) | Hydra `compose()` | 4 |
| `configs/` | Agent/memory/RAG/observability | Dynaconf, YAML | 4 |
| `configurations/` | MCP servers, policies, profiles | YAML, Dynaconf | 6 |
| `.env` | User environment overrides | dotenv | 3 |
| `.env.mcp` | MCP sandbox environment | dotenv | 3 |
| `registry.yaml` | Root tool registry | YAML, Hydra | 4 |
| `settings.toml` | LLM/backend settings | TOML, Dynaconf | 5 |
| `eval_config.toml` | Evaluation configuration | TOML, Dynaconf | 5 |

## Key Configuration Keys

```bash
# Agent Configuration
PROFILE=demo_power                # Execution profile
PLANNER_STRATEGY=react            # Planner strategy
PLANNER_MAX_STEPS=6               # Max planning steps (1-50)
MODEL_TEMPERATURE=0.3             # Model temperature (0.0-2.0)

# Model Configuration
MODEL_PROVIDER=openai
MODEL_NAME=gpt-4o-mini
OPENAI_API_KEY=sk-...

# Memory & RAG
VECTOR_BACKEND=local              # chroma|qdrant|weaviate|milvus|local
RAG_ENABLED=false

# Observability
LANGFUSE_ENABLED=true
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_PUBLIC_KEY=pk-...
LANGFUSE_SECRET_KEY=sk-...

# Sandbox & Registry
REGISTRY_FILE=registry.yaml
MCP_SERVERS_FILE=./build/mcp_servers.demo_power.yaml
CUGA_PROFILE_SANDBOX=./cuga_workspace/default_profile

# Server
PORT=8000
HOST=127.0.0.1
LOG_LEVEL=INFO
```

## Merge Rules

- **Dictionaries**: Deep merge (env overrides specific keys, preserves others)
- **Lists**: Override (replace entire list, no merge)
- **Scalars**: Override (higher precedence wins)

## Example: Local Development

```bash
# .env
PROFILE=demo_power
MODEL_TEMPERATURE=0.3
VECTOR_BACKEND=local
LOG_LEVEL=DEBUG
```

```yaml
# configs/agent.demo.yaml
profile: demo_power
model:
  provider: openai
  model: gpt-4o-mini
planner:
  max_steps: 6
```

**Result**:
- `profile`: `demo_power` (env + YAML agree)
- `model.temperature`: `0.3` (env overrides YAML default)
- `model.provider`: `openai` (from YAML)
- `log_level`: `DEBUG` (from env)

## Example: CLI Override

```bash
# CLI (highest precedence)
python -m cuga.cli orchestrate --profile production --max-steps 5

# Environment (ignored for CLI-specified keys)
export PROFILE=demo_power
export PLANNER_MAX_STEPS=10

# Result: CLI wins
# profile=production, max_steps=5
```

## Troubleshooting

### Check provenance (where did value come from?)

```python
from cuga.config import ConfigResolver

resolver = ConfigResolver()
value, source = resolver.get_with_provenance("profile")
print(f"{value} from {source}")
# Output: production from env:PROFILE
```

### Common Issues

1. **Value not what I expected** → Check precedence with provenance
2. **Validation failing** → Run `resolver.validate()` to see errors
3. **Env var not working** → Check prefix (`CUGA_PROFILE` vs `PROFILE`)
4. **Config conflicts** → Use unified ConfigResolver instead of direct reads

## Loaders

- **Dynaconf**: Multi-file composition, validators, env overrides
- **Hydra**: Fragment composition, env interpolation `${oc.env:VAR,default}`
- **dotenv**: Simple .env file loading
- **YAML/TOML**: Direct parsing with `yaml.safe_load()` / `tomllib.load()`

## Migration Checklist

- [ ] Audit all `os.getenv()` calls
- [ ] Document config keys in inventory
- [ ] Migrate to unified ConfigResolver
- [ ] Add validators for critical keys
- [ ] Update tests (isolation, fixtures)
- [ ] Enable provenance tracking for debugging

---

**See**: `docs/configuration/CONFIG_RESOLUTION.md` for complete documentation
