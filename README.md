<div align="center">
  <img src="docs/image/CUGAr.png" alt="CUGAr Logo" width="600"/>
</div>

# CUGAR Agent (2025 Edition)

[![CI](https://github.com/TylrDn/cugar-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/TylrDn/cugar-agent/actions/workflows/ci.yml)
[![Tests](https://github.com/TylrDn/cugar-agent/actions/workflows/tests.yml/badge.svg)](https://github.com/TylrDn/cugar-agent/actions/workflows/tests.yml)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Coverage](https://img.shields.io/badge/coverage-pytest--cov-success)](./TESTING.md)

CUGAR Agent is a production-grade, modular agent stack that embraces 2025’s best practices for LangGraph/LangChain orchestration, LlamaIndex-powered RAG, CrewAI/AutoGen-style multi-agent patterns, and modern observability (Langfuse/OpenInference/Traceloop). The repository is optimized for rapid setup, reproducible demos, and safe extension into enterprise environments.
Policy and change-management guardrails are maintained in [AGENTS.md](AGENTS.md) and must be reviewed before modifying agents or tools.

## At a Glance
- **Composable agent graph**: Planner → Tool/User executor → Memory+Observability hooks, wired for LangGraph.
- **RAG-ready**: LlamaIndex loader/retriever scaffolding with pluggable vector stores (Chroma, Qdrant, Weaviate, Milvus).
- **Multi-agent**: CrewAI/AutoGen-compatible patterns and coordination helpers.
- **Observability-first**: Langfuse/OpenInference emitters, structured audit logs, profile-aware sandboxing.
- **Developer experience**: Typer CLI, Makefile tasks, uv-based env management, Ruff/Black/isort + mypy, pytest+coverage, pre-commit.
- **Deployment**: Dockerfile, GitHub Actions CI/CD, sample configs and .env.example for cloud/on-prem setups.

## Recent updates (scaffolding)

- Added Watsonx Granite provider stub with deterministic defaults and JSONL audit trail to simplify enterprise alignment.
- Added Langflow component placeholders (planner, executor, guard, Granite LLM) to prep for flow export/import commands.
- Added registry validation, sandbox profile starter, and documentation shells for security and guardrail mapping.

## 🚀 External Data Integration - 100% Complete

**Phase 4 Complete**: All 10 external data adapters are now production-ready with comprehensive test coverage!

### Available Adapters

| Adapter | Status | LOC | Tests | Priority | Capabilities |
|---------|--------|-----|-------|----------|-------------|
| **IBM Sales Cloud** | ✅ | 360 | Mock | 🔴 Critical | CRM platform, OAuth |
| **Salesforce** | ✅ | 650 | 11 | 🔴 Critical | CRM, SOQL queries |
| **ZoomInfo** | ✅ | 565 | 13 | 🟡 High | Contact enrichment |
| **Clearbit** | ✅ | 476 | 19 | 🟢 Medium | Company enrichment |
| **HubSpot** | ✅ | 501 | 19 | 🟡 High | Marketing automation |
| **6sense** | ✅ | 570 | 15 | 🟢 Medium | Predictive intent |
| **Apollo.io** | ✅ | 450 | 12 | 🟢 Medium | Email verification |
| **Pipedrive** | ✅ | 420 | 12 | 🟢 Medium | SMB CRM |
| **Crunchbase** | ✅ | 410 | 12 | 🔵 Low | Funding intelligence |
| **BuiltWith** | ✅ | 350 | 10 | 🔵 Low | Tech tracking |

**Total**: 4,752 LOC | 123 tests | 32 signal types | 10/10 adapters (100% coverage)

### Key Features

- ✅ **Hot-Swap Architecture**: Toggle mock ↔ live mode via environment variables (zero code changes)
- ✅ **Interactive Setup Wizard**: Secure credential management with capability showcase
- ✅ **SafeClient Integration**: Enforced timeouts (10s read, 5s connect), automatic retry with exponential backoff
- ✅ **Comprehensive Testing**: 123 unit tests using mocks (no API dependencies required)
- ✅ **32 Signal Types**: Buying signals across all adapters (intent, funding, tech changes, deal progression)
- ✅ **Production-Ready**: Security-first design, offline-capable, fully documented

### Quick Start

```bash
# Interactive setup with credential management
python3 -m cuga.frontend.setup_wizard

# Or test all adapters (mock mode)
python3 scripts/setup_data_feeds.py

# Test specific adapter (live mode)
export SALES_SALESFORCE_ADAPTER_MODE=live
export SALES_SALESFORCE_CLIENT_ID=<your-id>
export SALES_SALESFORCE_CLIENT_SECRET=<your-secret>
python3 scripts/setup_data_feeds.py
```

### Documentation

- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)**: Quick reference with usage examples for all 10 adapters
- **[QUICK_TEST_GUIDE.md](QUICK_TEST_GUIDE.md)**: Complete testing guide with credentials and setup steps
- **[PHASE_4_FINAL_SUMMARY.md](PHASE_4_FINAL_SUMMARY.md)**: Comprehensive Phase 4 completion summary
- **[EXTERNAL_DATA_FEEDS_STATUS.md](EXTERNAL_DATA_FEEDS_STATUS.md)**: Progress tracker (100% complete)

### Usage Example

```python
from cuga.adapters.sales.factory import create_adapter

# Create adapter (auto-detects mode from env)
adapter = create_adapter('salesforce', trace_id='demo')

# Fetch data
accounts = adapter.fetch_accounts({'limit': 10})
contacts = adapter.fetch_contacts('account-123')
signals = adapter.fetch_buying_signals('account-123')

# Check mode
print(f"Mode: {adapter.get_mode()}")  # MOCK or LIVE
```

See [QUICK_REFERENCE.md](QUICK_REFERENCE.md) for advanced examples including 6sense intent scoring, Apollo email verification, Crunchbase funding intelligence, and more.

## Architecture
```
                       ┌──────────────────────────┐
                       │        Controller        │
                       │ (policy + correlation ID)│
                       └────────────┬─────────────┘
                                    │
                           plan(goal, registry)
                                    │
┌──────────────┐          ┌─────────▼─────────┐          ┌────────────────────┐
│ Registry/CFG │──sandbox▶│    Planner        │──steps──▶│   Executor/Tools   │
│ (Hydra/Dyn)  │          │ (ReAct/Plan&Exec) │          │ (LCEL, MCP, HTTP)  │
└──────────────┘          └─────────┬─────────┘          └─────────┬──────────┘
                                    │                              │
                          traces + memory writes         Langfuse/OpenInference
                                    │                              │
                            ┌───────▼────────┐                   ┌─▼────────┐
                            │ Memory / RAG   │◀────context───────│  Clients │
                            │ (LlamaIndex)   │                   │ (CLI/API)│
                            └────────────────┘                   └──────────┘
```

For a role-by-role, mode-aware walkthrough of how the controller, planners, executors, and MCP tool packs fit together (plus configuration keys), see [docs/agents/architecture.md](docs/agents/architecture.md). For an MCP + LangChain web stack overview that covers the FastAPI backend, Vue 3 frontend, streaming flows, and configuration surfaces, see [docs/MCP_LANGCHAIN_OVERVIEW.md](docs/MCP_LANGCHAIN_OVERVIEW.md). A step-by-step stable local launch checklist (registry + sandbox + Langflow readiness) lives in [docs/local_stable_launch.md](docs/local_stable_launch.md).

## Documentation

📘 **[System Execution Narrative](docs/SYSTEM_EXECUTION_NARRATIVE.md)** - Complete request → response flow for contributor onboarding (3 entry points: CLI/FastAPI/MCP, 8 execution phases with security boundaries, observability integration, debugging tips, testing guidance)

🔧 **[FastAPI Role Clarification](docs/architecture/FASTAPI_ROLE.md)** - Defines FastAPI as transport layer only (HTTP/SSE, auth, budget enforcement) vs orchestration (planning, coordination, execution) to prevent mixing concerns

⚙️ **[Orchestrator Interface and Semantics](docs/orchestrator/README.md)** - Formal specification for orchestrator API with lifecycle callbacks, failure taxonomy, retry semantics, execution context, routing authority, and implementation patterns

🏢 **[Enterprise Workflow Examples](docs/examples/ENTERPRISE_WORKFLOWS.md)** - Comprehensive end-to-end workflow examples for typical enterprise use cases (customer onboarding, incident response, data pipelines) with planning, error recovery, HITL gates, and external API automation

📊 **[Observability and Debugging Guide](docs/observability/OBSERVABILITY_GUIDE.md)** - Comprehensive instrumentation guide with structured logging, distributed tracing (OpenTelemetry/LangFuse/LangSmith), metrics collection, error introspection, replayable traces, dashboards, and troubleshooting playbooks

🧪 **[Test Coverage Map](docs/testing/TEST_COVERAGE_MAP.md)** - Comprehensive test coverage aligned with architectural components showing what's tested (orchestrator 80%, routing 85%, failures 90%) and critical gaps (tools 30%, memory 20%, config 0%, observability 0%) with priorities for additional testing

👋 **[Developer Onboarding Guide](docs/DEVELOPER_ONBOARDING.md)** - Step-by-step walkthrough for newcomers: environment setup (15 min), first agent interaction (10 min), create custom tool (20 min), build custom agent (30 min), wire components together (15 min) with full working examples (calculator tool, math tutor agent, tutoring workflow)

## 🖥️ Desktop Deployment for Sales Reps

**CUGAr-SALES is now optimized for local deployment targeting sales representatives and technical specialists!**

### ✅ Deployment Status: Production-Ready

**What's Complete:**
- ✅ Native desktop application (Electron wrapper)
- ✅ One-click launch scripts (Windows/Mac/Linux)
- ✅ Quick Actions Panel with 15 pre-configured workflows
- ✅ Backend status monitoring
- ✅ Keyboard shortcuts (Cmd/Ctrl+K for Quick Actions)
- ✅ Offline-first architecture
- ✅ First-run setup wizard
- ✅ Demo data fixtures

### One-Click Launch

#### **macOS / Linux**
```bash
./launch_sales_assistant.sh
```

#### **Windows**
```
launch_sales_assistant.bat
```

#### **Desktop Application**
Build native installers for zero-friction deployment:
```bash
cd src/frontend_workspaces/agentic_chat
npm install
npm run electron:build          # Auto-detect platform
npm run electron:build:mac      # macOS (Intel & Apple Silicon)
npm run electron:build:win      # Windows installer
npm run electron:build:linux    # AppImage & .deb
```

### Sales-Focused Features

**Quick Actions** (Press Cmd/Ctrl+K):
- 🎯 **Prospecting**: Score prospects, research accounts, find decision makers
- ✉️ **Outreach**: Draft emails, build sequences, use templates
- ✅ **Qualification**: BANT/MEDDIC scoring, risk assessment, next actions
- 📊 **Planning**: Territory analysis, capacity simulation

**What you get:**
- ✅ Automatic backend startup
- ✅ Browser-based UI (localhost:3000)
- ✅ Backend status monitoring
- ✅ First-run setup wizard
- ✅ Demo data pre-loaded
- ✅ Offline-first capabilities
- ✅ System tray integration (desktop app)
- ✅ Built-in safety guardrails

### Documentation

- **[DESKTOP_DEPLOYMENT.md](DESKTOP_DEPLOYMENT.md)** - Comprehensive deployment guide
- **[DESKTOP_UI_INTEGRATION_COMPLETE.md](DESKTOP_UI_INTEGRATION_COMPLETE.md)** - Technical implementation details
- **[PRODUCTION_LAUNCH_PLAN.md](PRODUCTION_LAUNCH_PLAN.md)** - 3-week rollout plan
- **[QUICK_REFERENCE_CARD.md](QUICK_REFERENCE_CARD.md)** - Sales rep cheat sheet

**Quick Test**: Run `./launch_sales_assistant.sh` and press `Cmd/Ctrl+K` to see Quick Actions!

---

## Quickstart (Development)
```bash
# 1) Install (Python >=3.10)
uv sync --all-extras --dev
uv run playwright install --with-deps chromium

# 2) Configure environment
cp .env.example .env
# set OPENAI_API_KEY / LANGFUSE_SECRET / etc inside .env

# 3) Run demo agent locally
uv run cuga start demo

# 4) Try modular stack example
uv run python examples/run_langgraph_demo.py --goal "triage a support ticket"
```

## Installation
- **Dependencies**: `uv` (or `pip`), optional browsers for Playwright, optional vector DB service (Chroma/Weaviate/Qdrant/Milvus).
- **Development**: `uv sync --all-extras --dev` installs dev + optional extras (`memory`, `sandbox`, `groq`, etc.).
- **Pre-commit**: `uv run pre-commit install` then `uv run pre-commit run --all-files`.

## Configuration
- `.env.example` lists required variables for LLMs, tracing, and storage.
- `configs/` holds YAML/TOML profiles for agents, LangGraph graphs, memory backends, and observability.
- `registry.yaml` and `config/` house MCP/registry defaults; use `scripts/verify_guardrails.py` before shipping changes.

## Guardrails & Change Management
- Review [AGENTS.md](AGENTS.md) before altering planners, tools, or registry entries; it is the single source of truth for allowlists, sandbox expectations, budgets, and redaction.
- Guardrail and registry changes are enforced by CI: `scripts/verify_guardrails.py --base <branch>` collects diffs and fails if `README.md`, `PRODUCTION_READINESS.md`, `CHANGELOG.md`, or `todo1.md` are not updated alongside guardrail changes or if `## vNext` lacks a guardrail note.
- Keep production checklists ([PRODUCTION_READINESS.md](PRODUCTION_READINESS.md)) and security docs in sync with guardrail adjustments so downstream users understand the default policies and where to override them.
- Developer checklist: ensure registry entries declare sandboxes + `/workdir` pinning for exec scopes, budget/observability env keys (`AGENT_*`, `OTEL_*`, LangFuse/LangSmith, Traceloop) are wired, `docs/mcp/tiers.md` is regenerated from `docs/mcp/registry.yaml`, and new/updated tests exercise planner ranking, import guardrails, and registry hot-swap determinism.

## Agent Types
- **Planner**: ReAct or Plan-and-Execute; emits steps with policy-aware cost/latency hints.
- **Tool Executor**: LCEL/LangChain tools, MCP adapters, HTTP/OpenAPI runners with sandboxed registry resolution.
- **RAG/Data Agent**: LlamaIndex loader+retriever (docs in `rag/`), vector memory connectors in `memory/`.
- **Coordinator**: CrewAI/AutoGen-like orchestrator for multi-agent hand-offs.
- **Observer**: Langfuse/OpenInference emitters with correlation IDs and redaction hooks.

See `AGENTS.md` for role details and `USAGE.md` for end-to-end flows.

## RAG Setup
- Drop documents into `rag/sources/` or configure a remote store.
- Choose a backend in `configs/memory.yaml` (chroma|qdrant|weaviate|milvus|local).
- Run `uv run python scripts/load_corpus.py --source rag/sources --backend chroma`.
- Query via `uv run python examples/rag_query.py --query "How do I add a new MCP tool?"`.

## Memory & State
- `memory/` exposes `VectorMemory` (in-memory fallback), summarization hooks, and profile-scoped stores.
- State keys are namespaced by profile to preserve sandbox isolation.
- Persistence is opt-in; see `configs/memory.yaml` and `TESTING.md` for guidance.

## Observability
- Langfuse client is wired via `observability/langfuse.py` with sampling + PII redaction hooks.
- OpenInference/Traceloop emitters are optional and can be toggled per profile.
- Structured audit logs live under `logs/` when enabled; avoid committing artifacts.
- Watsonx Granite calls validate credentials up front and append JSONL audit rows with timestamp, actor, parameters, and outcome for offline review.

### Observability preview

- The FastAPI orchestrator exposes a Prometheus-compatible metrics endpoint at `/metrics` (default port 8000). This endpoint exports golden-signal metrics such as `cuga_requests_total`, `cuga_success_rate`, `cuga_latency_ms{percentile="p50|p95|p99"}`, `cuga_tool_error_rate`, `cuga_budget_warnings_total`, and `cuga_budget_exceeded_total`.
- Configure OpenTelemetry (OTLP) or console exporters via environment variables. Common envs:
  - `OTEL_EXPORTER_OTLP_ENDPOINT` — OTLP HTTP/gRPC endpoint for traces/metrics (optional; when unset the console exporter is used).
  - `OTEL_SERVICE_NAME` — service name to appear in traces (default: `cuga-orchestrator`).
  - `OTEL_TRACES_EXPORTER` / `OTEL_METRICS_EXPORTER` — exporter type (otlp, logging, none).

Example: curl the metrics endpoint locally

```bash
# If running the orchestrator locally on port 8000
curl -sS http://localhost:8000/metrics | head -n 80

# Expected sample lines (Prometheus format):
# cuga_requests_total 42
# cuga_success_rate 0.95
# cuga_latency_ms{percentile="p50"} 150.0
# cuga_latency_ms{percentile="p95"} 450.0
# cuga_tool_error_rate 0.02
# cuga_budget_warnings_total 3
# cuga_budget_exceeded_total 0
```

## Multi-Agent & Coordination
- `agents/` outlines planner/worker/tool-user patterns and how to register them with CrewAI/AutoGen.
- `examples/multi_agent_dispatch.py` demonstrates round-robin delegation with shared vector context.
- Hand-offs carry correlation IDs and redacted summaries, not raw prompts.

## Testing & Quality Gates
- Run `make lint test typecheck` locally.
- Pytest with coverage is configured (see `TESTING.md`).
- CI (GitHub Actions) runs lint, type-check, tests, and guardrail verification on pushes/PRs.

## Security Model

CUGAR Agent enforces **security-first design with deny-by-default policies** per [AGENTS.md](AGENTS.md):

### Core Security Principles
1. **Allowlist-First Tool Selection**: Only explicitly allowed tools from `cuga.modular.tools.*` can execute
2. **Deny-by-Default Network**: Network egress restricted to domain allowlist; localhost/private networks blocked by default
3. **Sandbox Isolation**: All tool execution in isolated sandboxes (py/node slim|full, orchestrator profiles) with read-only mounts
4. **Budget Enforcement**: Cost ceilings (default: 100 units/task) with `warn` or `block` policies
5. **Human-in-the-Loop Approval**: High-risk operations (DELETE, FINANCIAL) require explicit approval before execution

### Security Architecture
```
Request → Budget Guard → Tool Allowlist → Parameter Validation → Network Policy → Sandbox Execution
            ↓               ↓                    ↓                      ↓               ↓
       (ceiling=100)   (cuga.modular   (type/range/pattern)    (domain allowlist) (read-only)
                        .tools.* only)                          (no localhost)
```

**Approval Flow** (HITL):
- **Low-risk (READ)**: Auto-approved, logged
- **Medium-risk (WRITE)**: Auto-approved with audit trail
- **High-risk (DELETE, FINANCIAL)**: Requires human approval (5min timeout, reject on timeout)

**Budget Policy**:
- `AGENT_BUDGET_CEILING=100` (default): Max cost units per task
- `AGENT_BUDGET_POLICY=warn|block`: Warn and continue, or block execution
- `AGENT_ESCALATION_MAX=2`: Max approval escalations before admin approval required

See [SECURITY.md](SECURITY.md) for complete security controls and [docs/security/GOVERNANCE.md](docs/security/GOVERNANCE.md) for governance architecture.

## Security & Safe Execution

CUGAR Agent enforces security-first design with deny-by-default policies per [AGENTS.md](AGENTS.md) § 4 Sandbox Expectations:

### MCP & OpenAPI Governance

- **Policy Gates**: HITL approval points for WRITE/DELETE/FINANCIAL actions (Slack send, file delete, stock orders)
- **Per-Tenant Capability Maps**: 8 organizational roles (marketing/trading/engineering/support) with tool allowlists/denylists
- **Runtime Health Checks**: Tool discovery ping, schema drift detection, cache TTLs to prevent huge cold-start lists
- **Layered Access Control**: Tool registration → Tenant map → Tool-level restrictions → Rate limits

See [docs/security/GOVERNANCE.md](docs/security/GOVERNANCE.md) for complete governance architecture, configuration files, and integration patterns.

### Eval/Exec Elimination
- **No eval/exec**: All `eval()` and `exec()` calls eliminated from production code paths
- **AST-based expression evaluation**: Use `safe_eval_expression()` from `cuga.backend.tools_env.code_sandbox.safe_eval` for mathematical expressions
  - Allowlisted operators: Add/Sub/Mul/Div/FloorDiv/Mod/Pow
  - Allowlisted functions: math.sin/cos/tan/sqrt/log/exp, abs/round/min/max/sum
  - Denies: assignments, imports, attribute access, eval/exec/__import__
- **SafeCodeExecutor**: All code execution routed through `SafeCodeExecutor` or `safe_execute_code()` from `cuga.backend.tools_env.code_sandbox.safe_exec`
  - Import allowlist: Only `cuga.modular.tools.*` permitted
  - Import denylist: os/sys/subprocess/socket/pickle/eval/exec/compile
  - Restricted builtins: Safe operations (math/types/iteration) allowed; eval/exec/open/__import__ denied
  - Filesystem deny-default: No file operations unless explicitly allowed
  - Timeout enforcement: 30s default, configurable
  - Audit trail: All imports/executions logged with trace_id

### HTTP & Secrets Hardening
- **SafeClient wrapper**: All HTTP requests MUST use `SafeClient` from `cuga.security.http_client`
  - Enforced timeouts: 10.0s read, 5.0s connect, 10.0s write, 10.0s total
  - Automatic retry: Exponential backoff (4 attempts max, 8s max wait)
  - URL redaction: Query params and credentials stripped from logs
- **Env-only secrets**: Credentials MUST be loaded from environment variables
  - CI enforces `.env.example` parity validation (no missing keys)
  - Secret scanning: trufflehog + gitleaks on every push/PR
  - Hardcoded API keys/tokens trigger CI failure

### Import & Sandbox Controls
- **Import restrictions**: Dynamic imports limited to `cuga.modular.tools.*` namespace only
- **Profile isolation**: Memory and tool access namespaced per profile; no cross-profile leakage
- **Sandbox profiles**: All registry entries declare sandbox profile (py/node slim|full, orchestrator)
- **Read-only defaults**: Mounts are read-only by default; `/workdir` pinning for exec scopes

See [AGENTS.md](AGENTS.md) for complete guardrail specifications and [docs/security/](docs/security/) for detailed security controls.

## Observability & Monitoring

CUGAR Agent provides **production-grade observability** with structured events, golden signals, and multi-backend export:

### Observability Stack
- **Structured Events**: `plan_created`, `route_decision`, `tool_call_start/complete/error`, `budget_warning/exceeded`, `approval_requested/received/timeout`
- **Golden Signals**: Success rate (%), latency (P50/P95/P99), tool error rate (%), mean steps/task, approval wait time, budget utilization
- **Trace Propagation**: `trace_id` flows through CLI → planner → worker → coordinator → tools with parent-child relationships
- **PII Redaction**: Auto-redact sensitive keys (`secret`, `token`, `password`, `api_key`, `credential`, `auth`) before emission

### Monitoring Endpoints
```bash
# Prometheus metrics endpoint (scrape target)
curl http://localhost:8000/metrics

# Expected metrics:
cuga_requests_total              # Total requests handled
cuga_success_rate               # % successful requests
cuga_latency_ms{percentile}     # P50/P95/P99 latency
cuga_tool_error_rate            # % failed tool calls
cuga_steps_per_task             # Mean planning steps
cuga_budget_warnings_total      # Budget warnings emitted
cuga_budget_exceeded_total      # Budget hard blocks
cuga_approval_requests_total{status}  # Approval flow tracking
```

### Multi-Backend Support
- **OpenTelemetry (OTLP)**: Set `OTEL_EXPORTER_OTLP_ENDPOINT=http://collector:4318` for Jaeger/Zipkin/Tempo
- **LangFuse**: Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` for LLM tracing
- **LangSmith**: Set `LANGCHAIN_API_KEY`, `LANGCHAIN_PROJECT`, `LANGCHAIN_ENDPOINT`
- **Console (Default)**: Offline-first JSON logs to stdout (no network required)

### Grafana Dashboard
Import pre-built dashboard from `observability/grafana_dashboard.json`:
- Request rate & success rate panels
- Latency percentile charts (P50/P95/P99)
- Tool error breakdown by tool/type
- Budget utilization gauge
- Approval queue depth
- Event timeline with filtering

**Configuration**:
```bash
# Enable OTEL export
export OTEL_EXPORTER_OTLP_ENDPOINT="http://localhost:4318"
export OTEL_SERVICE_NAME="cuga-orchestrator"

# Start with observability
uv run cuga start demo
```

See [docs/observability/OBSERVABILITY_GUIDE.md](docs/observability/OBSERVABILITY_GUIDE.md) for detailed instrumentation guide and [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for metrics scraping setup.

## FAQ
- **Which LLMs are supported?** 
  - OpenAI (GPT-4o, GPT-4 Turbo)
  - Azure OpenAI
  - Anthropic (Claude 3.5 Sonnet, Opus, Haiku)
  - **IBM Watsonx / Granite 4.0** (granite-4-h-small, granite-4-h-micro, granite-4-h-tiny) — **Default provider** with deterministic temperature=0.0
  - Groq (Mixtral)
  - Google GenAI
  - Any LangChain-compatible model via adapters
- **Do I need a vector DB?** Not for quickstarts; an in-memory store is bundled. For production use Chroma/Qdrant/Weaviate/Milvus.
- **How do I add a new tool?** Implement `ToolSpec` in `tools/registry.py` or wrap an MCP server; see `USAGE.md`.
- **Is this production-ready?** Core stack follows sandboxed, profile-scoped design with observability. Harden configs before internet-facing use.
- **How do I configure Watsonx/Granite?** Set environment variables: `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, and optionally `WATSONX_URL`. See `docs/configuration/ENVIRONMENT_MODES.md` for details.

## Documentation

For a complete understanding of system execution flow:
- 📘 **[System Execution Narrative](docs/SYSTEM_EXECUTION_NARRATIVE.md)** - Complete request → response flow for contributor onboarding (CLI/FastAPI/MCP modes, routing, agents, memory, tools)
- 🏗️ [Architecture](ARCHITECTURE.md) - High-level design overview
- 🚀 [Quick Start](QUICK_START.md) - Get up and running quickly
- 🤝 [Contributing](CONTRIBUTING.md) - How to contribute to the project
- 🔒 [Production Readiness](PRODUCTION_READINESS.md) - Deployment considerations

## Roadmap Highlights
- Streaming-first ReAct policies with beta support for Strands/semantic state machines.
- Built-in eval harness for self-play and regression suites.
- Optional LangServe or FastAPI hosting for SaaS-style deployments (see `ROADMAP.md`).

## License
Apache 2.0. See [LICENSE](LICENSE).
