<div align="center">
  <img src="../image/CUGAr.png" alt="CUGAr Logo" width="500"/>
</div>

# Getting Started with CUGAR Agent

This guide walks you through setting up and running the CUGAR agent system.

> **For a complete understanding of how requests flow through the system**, see [System Execution Narrative](SYSTEM_EXECUTION_NARRATIVE.md) - traces request → routing → agent → memory → response with examples for CLI, FastAPI, and MCP modes.
>
> **For the orchestrator interface and semantics**, see [Orchestrator Interface](orchestrator/README.md) - formal specification for lifecycle callbacks, failure modes, retry semantics, and implementation patterns.
>
> **For enterprise workflow examples**, see [Enterprise Workflows](examples/ENTERPRISE_WORKFLOWS.md) - comprehensive end-to-end examples with planning, error recovery, HITL gates, and external API automation.
>
> **For observability and debugging**, see [Observability Guide](observability/OBSERVABILITY_GUIDE.md) - structured logging, distributed tracing, metrics, error introspection, and troubleshooting.
>
> **For test coverage mapping**, see [Test Coverage Map](testing/TEST_COVERAGE_MAP.md) - comprehensive coverage by architectural component with critical gaps and testing priorities.
>
> **For developer onboarding**, see [Developer Onboarding Guide](DEVELOPER_ONBOARDING.md) - step-by-step walkthrough for newcomers with hands-on examples building your first tool and agent.

## Prerequisites

- Python 3.9 or higher (3.10+ recommended)
- Docker (for containerized deployments)
- Basic understanding of command-line interfaces

## Quick Setup

### 1. Install Dependencies

```bash
# Using uv (recommended)
uv sync --all-extras --dev
uv run playwright install --with-deps chromium

# Or using pip
pip install -e ".[all]"
```

### 2. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit .env and set required variables:
# - OPENAI_API_KEY (or your preferred LLM provider key)
# - Optional: LANGFUSE_SECRET, OTEL_* for observability
```

See [`docs/configuration/ENVIRONMENT_MODES.md`](configuration/ENVIRONMENT_MODES.md) for detailed environment requirements per execution mode (local/service/MCP/test).

### 3. Run Your First Agent

```bash
# CLI mode - plan and execute
python -m cuga.modular.cli plan "search for flights to NYC"

# Check the generated state file
cat .cuga_modular_state.json | jq
```

## Understanding the Flow

When you run a command like `plan "search for flights"`, here's what happens:

1. **Request Entry** - CLI parses args, generates trace_id, loads memory state
2. **Planning** - PlannerAgent ranks tools by goal similarity, searches memory for context
3. **Coordination** - CoordinatorAgent selects worker (round-robin), delegates execution
4. **Execution** - WorkerAgent resolves tools from registry, executes handlers in sandboxes
5. **Memory** - Results stored in VectorMemory with profile isolation
6. **Response** - JSON output with complete trace, state persisted to disk

**For the complete flow diagram**, see [System Execution Narrative - Complete Flow Diagram](SYSTEM_EXECUTION_NARRATIVE.md#complete-flow-diagram).

## Next Steps

### CLI Mode (Local Development)

```bash
# Ingest documents for RAG
python -m cuga.modular.cli ingest docs/**/*.md --backend local

# Query memory
python -m cuga.modular.cli query "how to add tools" --top-k 5

# Plan with custom profile
python -m cuga.modular.cli plan "analyze data" --profile production
```

### FastAPI Service Mode (Production)

> **FastAPI's Role**: FastAPI is a **transport layer only** - it handles HTTP/SSE endpoints, authentication, and budget enforcement, then delegates to Planner/Coordinator/Workers for orchestration. See [`architecture/FASTAPI_ROLE.md`](architecture/FASTAPI_ROLE.md) for architectural boundaries.

```bash
# Start the service
uvicorn src.cuga.backend.app:app --reload

# Test the /plan endpoint
curl -X POST http://localhost:8000/plan \
  -H "X-Trace-Id: test-123" \
  -H "Content-Type: application/json" \
  -d '{"goal": "find flights"}'

# Test streaming /execute endpoint
curl -X POST http://localhost:8000/execute \
  -H "X-Trace-Id: test-456" \
  -H "Content-Type: application/json" \
  -d '{"goal": "analyze sales data"}'
```

**Environment Requirements for Service Mode**:
- `AGENT_TOKEN` (authentication)
- `AGENT_BUDGET_CEILING` (budget enforcement)
- Model API key (OPENAI_API_KEY or provider-specific)
- Recommended: OTEL_*, LANGFUSE_* (observability)

See [`docs/configuration/ENVIRONMENT_MODES.md#service-mode`](configuration/ENVIRONMENT_MODES.md#service-mode) for details.

### MCP Mode (Tool Registry)

```bash
# Configure MCP servers
export MCP_SERVERS_FILE="configurations/mcp_servers.yaml"
export CUGA_PROFILE_SANDBOX="py-slim"

# Start registry server
python src/cuga/backend/tools_env/registry/registry/api_registry_server.py

# List available tools
curl http://localhost:8080/applications

# Call a tool
curl -X POST http://localhost:8080/functions/call \
  -H "Content-Type: application/json" \
  -d '{
    "app_name": "weather_api",
    "function_name": "get_forecast",
    "args": {"city": "NYC"}
  }'
```

See [`docs/MCP_INTEGRATION.md`](MCP_INTEGRATION.md) for MCP server setup and tool lifecycle.

## Development Workflow

### Running Tests

```bash
# Unit tests
pytest tests/test_planner.py -v

# Scenario tests (end-to-end)
pytest tests/scenario/test_agent_composition.py -v

# Coverage report
pytest --cov=src --cov-report=html
```

See [`docs/testing/SCENARIO_TESTING.md`](testing/SCENARIO_TESTING.md) for test patterns and [`docs/testing/COVERAGE_MATRIX.md`](testing/COVERAGE_MATRIX.md) for coverage analysis.

### Adding Tools

1. Create tool handler in `src/cuga/modular/tools/`
2. Register in ToolRegistry with sandbox profile
3. Test with `pytest tests/test_tools.py`

```python
# Example tool
from cuga.modular.tools import ToolSpec

def my_handler(inputs: dict, context: dict) -> str:
    trace_id = context.get("trace_id")
    text = inputs.get("text", "")
    return f"Processed: {text}"

registry.register(ToolSpec(
    name="my_tool",
    description="Process text",
    handler=my_handler,
    sandbox_profile="py-slim"
))
```

See [`AGENTS.md#tool-contract`](../AGENTS.md#tool-contract) for guardrails.

### Debugging

```bash
# Trace a request end-to-end
python -m cuga.modular.cli plan "test" --trace-id "debug-123" 2>&1 | jq '.trace_id'

# Inspect memory state
cat .cuga_modular_state.json | jq '.records[] | {text, metadata}'

# Check logs for trace correlation
grep "debug-123" logs/*.log | jq -s '.'
```

See [System Execution Narrative - Debugging Tips](SYSTEM_EXECUTION_NARRATIVE.md#debugging-tips) for more.

## Common Issues

### "Tool not found in registry"
- Ensure tool is registered in ToolRegistry
- Check profile filter matches execution profile
- Verify allowlist (only `cuga.modular.tools.*` allowed)

### "Memory backend not connected"
- Run `memory.connect_backend()` before first use
- Check backend dependencies installed (pip install chromadb / qdrant-client)
- For local mode, no connection needed

### "Budget exceeded"
- Check AGENT_BUDGET_CEILING in environment
- Review budget policy (warn vs block)
- Monitor logs for budget decisions

See [`docs/configuration/ENVIRONMENT_MODES.md#troubleshooting`](configuration/ENVIRONMENT_MODES.md#troubleshooting) for mode-specific issues.

## Architecture Deep Dive

For comprehensive understanding:

- 📘 **[System Execution Narrative](SYSTEM_EXECUTION_NARRATIVE.md)** - Complete request → response flow (START HERE)
- 🏗️ [Architecture Overview](../ARCHITECTURE.md) - High-level design
- 🎯 [Orchestrator Contract](orchestrator/ORCHESTRATOR_CONTRACT.md) - Orchestration lifecycle
- 🧭 [Routing Authority](orchestrator/ROUTING_AUTHORITY.md) - Routing decisions
- 📋 [Agent I/O Contract](agents/AGENT_IO_CONTRACT.md) - AgentRequest/AgentResponse
- 🔧 [Tools Documentation](TOOLS.md) - Tool development guide
- 🧠 [Memory Systems](memory/) - VectorMemory, embeddings, backends
- 🔐 [Security Controls](security/SECURITY_CONTROLS.md) - Security boundaries

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for:
- Code style guidelines (Ruff, Black, mypy)
- Testing requirements (unit + scenario tests)
- PR checklist (docs, tests, guardrails)
- Guardrail update process (AGENTS.md must be updated first)

## Need Help?

- 📖 Read the [System Execution Narrative](SYSTEM_EXECUTION_NARRATIVE.md) (most comprehensive)
- 🐛 Check [GitHub Issues](https://github.com/TylrDn/cugar-agent/issues)
- 💬 See [CODE_OF_CONDUCT.md](../CODE_OF_CONDUCT.md) for community guidelines
- 📝 Review [AGENTS.md](../AGENTS.md) for canonical guardrails
