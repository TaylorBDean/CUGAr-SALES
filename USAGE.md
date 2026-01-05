# Usage Guide

This guide shows how to run, compose, and extend the CUGAR Agent stack via CLI and Python. All commands assume Python >=3.10 and `uv` for environment management.

## Setup
```bash
uv sync --all-extras --dev
uv run playwright install --with-deps chromium
cp .env.example .env
```
Set provider keys (e.g., `OPENAI_API_KEY`, `LANGFUSE_SECRET`) inside `.env` or your shell.

## CLI Flows
The Typer CLI is exposed as `uv run cuga`.

### Start a demo agent
```bash
uv run cuga start demo
```
- Starts registry + demo tool servers on the default sandbox profile.
- Uses `configs/agent.demo.yaml` for model + policy defaults.

### Run a goal with LangGraph planner
```bash
uv run python examples/run_langgraph_demo.py --goal "Draft a changelog from pull request notes" \
  --profile demo_power --observability langfuse
```
- Plans with ReAct; executes via LangChain tool runtime.
- Sends traces to Langfuse if `LANGFUSE_SECRET` is set.

### Inspect registries and profiles
```bash
uv run cuga registry list --profile demo_power
uv run cuga profile validate --profile demo_power
```
- Registries live in `config/` and `registry.yaml`.
- Profiles apply sandbox isolation and guardrail enforcement.

### Run memory/RAG helpers
```bash
uv run python scripts/load_corpus.py --source rag/sources --backend chroma
uv run python examples/rag_query.py --query "How does the planner select tools?" --backend chroma
```
- Uses `memory/vector_store.py` with in-memory fallback when no backend is reachable.

### Multi-agent hand-off
```bash
uv run python examples/multi_agent_dispatch.py --goal "Summarize docs and propose next steps"
```
- Demonstrates coordinator/worker/tool-user roles with shared memory summaries.

## Python API Quickstart
```python
from cuga.modular.agents import PlannerAgent, WorkerAgent
from cuga.modular.tools import ToolRegistry, ToolSpec
from cuga.modular.memory import VectorMemory

registry = ToolRegistry([
    ToolSpec(name="echo", description="echo text", handler=lambda i, c: i["text"]),
])
memory = VectorMemory()
planner = PlannerAgent(registry=registry, memory=memory)
worker = WorkerAgent(registry=registry, memory=memory)

plan = planner.plan(goal="echo hello", metadata={"profile": "demo"})
result = worker.execute(plan.steps)
print(result.output)
```

## Adding a Tool
1. Implement `ToolSpec` in `tools/registry.py` or wrap an MCP server.
2. Register it via `ToolRegistry([...])` or YAML in `configs/tools.yaml`.
3. Add tests under `tests/` to cover handler success/failure.

## LlamaIndex RAG Path
- Configure `configs/rag.yaml` with storage path or remote vector DB.
- Use `rag/loader.py` to ingest content and `rag/retriever.py` for queries.
- Toggle `RAG_ENABLED=true` in `.env` to opt-in.

## Config Reference & Precedence

Configuration precedence follows the canonical order described in `AGENTS.md` (Configuration Policy):

1. CLI arguments (highest precedence)
2. Environment variables (for Dynaconf use `DYNACONF_<SECTION>__<KEY>` or explicit envs like `AGENT_*`, `OTEL_*`)
3. `.env` files (project `.env`, `ops/env/*.env`, `.env.mcp`)
4. YAML configs (e.g., `registry.yaml`, `configs/*.yaml`)
5. TOML configs (e.g., `settings.toml`, `eval_config.toml`)
6. Configuration defaults (Dynaconf validators)
7. Hardcoded defaults (lowest precedence)

Notes:
- Deep merges are used for nested dictionaries (dicts merge), while lists are replaced (no implicit list merging).
- Use `DYNACONF_` envvar prefixes for Dynaconf-managed sections when you need to override nested values from the environment (e.g. `DYNACONF_ADVANCED_FEATURES__LITE_MODE=false`).

Example: override message window limit via env

```bash
export DYNACONF_ADVANCED_FEATURES__MESSAGE_WINDOW_LIMIT=50
```

Guardrail & policy configuration examples (YAML snippets)

`configs/guardrail_policy.yaml` (example)

```yaml
tool_allowlist:
  - filesystem_read
  - web_search

tool_denylist:
  - dangerous_tool

parameter_schemas:
  filesystem_read:
    path:
      type: string
      required: true
      pattern: "^[a-zA-Z0-9/_\-\.]+$"

network_egress:
  allowed_domains:
    - api.openai.com
    - example.com
  block_localhost: true
  block_private_networks: true

budget:
  AGENT_BUDGET_CEILING: 100
  AGENT_BUDGET_POLICY: warn
  AGENT_ESCALATION_MAX: 2
```

Loading precedence sanity check (local)

```bash
# 1) Make a small TOML
cat > /tmp/test_settings.toml <<'TOML'
[features]
thoughts = false
TOML

# 2) Override via env
export DYNACONF_FEATURES__THOUGHTS=true

# 3) Create Dynaconf instance (Python)
python - <<'PY'
from dynaconf import Dynaconf
settings = Dynaconf(settings_files=['/tmp/test_settings.toml'], envvar_prefix='DYNACONF')
print('thoughts:', settings.features.thoughts)
PY
```

## Observability Hooks
- **Langfuse**: set `LANGFUSE_SECRET` + `LANGFUSE_PUBLIC_KEY`; calls are emitted via `observability/langfuse.py`.
- **OpenInference/Traceloop**: enable with `OPENINFERENCE_ENABLED=true` and configure URLs in `configs/observability.yaml`.
- All emitters redact secrets and run in the current profile sandbox.

## Troubleshooting
- Ports 7860/8000/8001/9000 must be free for demos.
- If Playwright browsers are missing, re-run `uv run playwright install --with-deps chromium`.
- Use `--verbose` flags for detailed logs; traces are stored under `logs/` when enabled.
