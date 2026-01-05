# Testing Guide

This project uses `uv` for dependency management and `pytest` for execution. Tests are grouped to keep registry checks, e2e tasks, and sandbox features isolated.

---

## 🧪 Test Coverage Matrix

The following matrix defines test categories, coverage targets, and current status across all architectural layers:

| Layer | Test Type | Coverage Target | Current Status | Priority | Notes |
|-------|-----------|-----------------|----------------|----------|-------|
| **Orchestrator** | Unit | ≥ 80% | 🟢 | Critical | Lifecycle stages, routing decisions, failure modes |
| **Orchestrator** | Integration | ≥ 80% | 🟡 | Critical | Plan→Route→Execute state machine, context propagation |
| **Orchestrator** | Scenario | 100% paths | 🟡 | Critical | Multi-agent dispatch, memory-augmented planning, error recovery |
| **Routing** | Unit | ≥ 80% | 🟢 | Critical | RoutingAuthority, PlanningAuthority, policy enforcement |
| **Routing** | Integration | ≥ 80% | 🟡 | Critical | Round-robin, capability-based, load-balanced routing |
| **Routing** | Scenario | 100% policies | 🔴 | High | Allowlist-only, HITL approval gates, budget enforcement |
| **Tools** | Unit | ≥ 60% | 🟡 | High | Tool schema validation, parameter parsing, error handling |
| **Tools** | Integration | ≥ 60% | 🟡 | High | Sandbox execution, resource limits, import guardrails |
| **Tools** | E2E (MCP) | Key tools | 🟡 | High | Filesystem, search, web automation with fake MCP servers |
| **Memory** | Unit | ≥ 60% | 🟡 | Medium | Embedding generation, vector search, metadata isolation |
| **Memory** | Integration | ≥ 60% | 🔴 | Medium | Cross-request persistence, profile isolation, RAG queries |
| **Memory** | Scenario | Key flows | 🔴 | Medium | Stateful conversations, memory-augmented planning |
| **Config** | Unit | ≥ 70% | 🟢 | High | Precedence layers, env parsing, validation |
| **Config** | Integration | ≥ 70% | 🟡 | High | Multi-source merging, Hydra composition, secrets validation |
| **Observability** | Unit | ≥ 70% | 🟡 | Medium | Event emission, metric collection, PII redaction |
| **Observability** | Integration | ≥ 70% | 🔴 | Medium | OTEL export, Prometheus metrics, golden signals |
| **Security** | Unit | ≥ 90% | 🟢 | Critical | Secret redaction, HTTP client, eval/exec guards |
| **Security** | Integration | ≥ 90% | 🟢 | Critical | Sandbox escape prevention, allowlist enforcement |
| **CLI/API** | E2E | Key workflows | 🟢 | High | Ingest/query cycle, planner execution, tool invocation |

### Legend
- 🟢 **Green**: Coverage target met or exceeded
- 🟡 **Yellow**: Partial coverage, in progress or needs improvement
- 🔴 **Red**: Below target or missing, blocks production deployment

### Priority Definitions
- **Critical**: Blocks production deployment if failing
- **High**: Required for v1.0 release
- **Medium**: Should have for production readiness
- **Low**: Nice to have, can be deferred

---

## 📊 Test Categories

### 1. Unit Tests
**Purpose**: Test individual functions, classes, and modules in isolation with mocked dependencies.

**Coverage Targets**:
- Orchestrator & Routing: ≥ 80%
- Tools & Memory: ≥ 60%
- Config & Observability: ≥ 70%
- Security: ≥ 90%

**Location**: `tests/unit/`

**Key Test Areas**:
- Function logic and edge cases
- Error handling and validation
- State transitions and invariants
- Type checking and schema validation

**Example**:
```bash
# Run all unit tests
uv run pytest tests/unit/ --cov=src --cov-report=term-missing

# Run unit tests for orchestrator
uv run pytest tests/unit/test_orchestrator.py -v

# Run with coverage threshold enforcement
uv run pytest tests/unit/ --cov=src --cov-fail-under=80
```

---

### 2. Integration Tests
**Purpose**: Test interactions between multiple components with real (non-mocked) dependencies where feasible.

**Coverage Targets**:
- Orchestrator & Routing: ≥ 80%
- Tools & Memory: ≥ 60%
- Config: ≥ 70%

**Location**: `tests/integration/`

**Key Test Areas**:
- Orchestrator → RoutingAuthority → Worker coordination
- PlanningAuthority → ToolRegistry → Sandbox execution
- VectorMemory → Embeddings → RAG retrieval
- ConfigResolver → Hydra → Environment validation

**Test Infrastructure**:
- **Fake MCP Servers**: Mock HTTP servers implementing MCP protocol for tool testing
  - `tests/integration/fixtures/fake_mcp_filesystem.py`
  - `tests/integration/fixtures/fake_mcp_search.py`
  - `tests/integration/fixtures/fake_mcp_crm.py`

- **Test Databases**: In-memory SQLite, Redis fakeredis for state persistence tests
- **Sandbox Containers**: Lightweight Docker containers for tool execution tests

**Example**:
```bash
# Run integration tests with fake MCP servers
uv run pytest tests/integration/ --mcp-fake-servers

# Run memory persistence integration tests
uv run pytest tests/integration/test_memory_persistence.py -v

# Run orchestrator integration suite
uv run pytest tests/integration/test_orchestrator_integration.py --trace-spans
```

---

### 3. End-to-End (E2E) Tests
**Purpose**: Test complete user workflows from CLI/API input to final output, including web automation.

**Coverage**: Key user workflows and critical paths

**Location**: `tests/e2e/`

**Key Test Areas**:
- CLI ingest → planning → tool execution → result aggregation
- Web automation with real headless Chromium/Playwright
- Multi-step workflows with memory persistence
- Error recovery and retry logic

**Web Automation Tests**:
- Browser launching and page navigation
- Element interaction (click, type, screenshot)
- Network interception and mocking
- Dynamic content handling (wait for selectors)

**Prerequisites**:
```bash
# Install Playwright browsers
uv run playwright install --with-deps chromium

# Verify installation
uv run playwright --version
```

**Example**:
```bash
# Run all e2e tests
uv run pytest tests/e2e/ --headed --slowmo=100

# Run web automation e2e tests only
uv run pytest tests/e2e/test_web_automation.py --browser=chromium

# Run with video recording for debugging
uv run pytest tests/e2e/ --video=on --screenshot=on

# Run CLI end-to-end smoke test
uv run pytest tests/test_cli_end_to_end.py -v
```

---

### 4. Scenario Tests
**Purpose**: Validate complete agent composition patterns and orchestration logic with real components (minimal mocks).

**Coverage**: 100% of documented scenario patterns

**Location**: `tests/scenarios/`

**Key Scenario Patterns**:
1. **Multi-Agent Dispatch**: Coordinator distributes tasks across multiple worker agents
2. **Memory-Augmented Planning**: Planner uses RAG to retrieve relevant context before planning
3. **Profile-Based Isolation**: Different profiles with isolated tool allowlists and budgets
4. **Error Recovery**: Graceful degradation and retry with fallback strategies
5. **Stateful Conversations**: Multi-turn interactions with persistent memory
6. **Complex Workflows**: Nested tool calls with approval gates and budget tracking
7. **Nested Coordination**: Parent orchestrator delegates to child orchestrators

**Test Characteristics**:
- Real orchestrator, memory, and tool components
- Real embeddings and vector search (local models)
- Real sandbox execution (containerized or subprocess)
- Mocked only external APIs (model providers, external HTTP services)

**Example**:
```bash
# Run all scenario tests
uv run pytest tests/scenarios/ -v

# Run memory-augmented planning scenario
uv run pytest tests/scenarios/test_memory_augmented_planning.py --profile=production

# Run with detailed trace logging
uv run pytest tests/scenarios/ --log-cli-level=DEBUG --trace-ids
```

**Scenario Test Template**:
```python
def test_multi_agent_dispatch_scenario(orchestrator, worker_pool, memory):
    """Validate multi-agent dispatch with real components."""
    # Setup: Real orchestrator + 3 workers + shared memory
    # Execute: Complex task requiring parallel tool execution
    # Verify: Task distributed correctly, traces preserved, memory shared
    # Assert: Success rate, latency, resource cleanup
```

---

## 🚀 Setup

### Install Dependencies
```bash
# Install all dependencies including dev and test extras
uv sync --all-extras --dev

# Install Playwright browsers for web automation
uv run playwright install --with-deps chromium
```

### Environment Configuration
```bash
# Copy example env file
cp .env.example .env

# Required for tests (minimal set)
export OPENAI_API_KEY=test_key  # or other model provider
export ENABLE_FILESYSTEM_MCP=true
export ENABLE_CRM_MCP=true
```

---

## 🔍 Pull Request Quality Gates

All PRs must pass the following quality gates enforced in CI (`.github/workflows/ci.yml`):

### 1. Linting & Formatting
```bash
uv run ruff check
uv run ruff format --check
```

### 2. Type Checking
```bash
uv run mypy src/
```

### 3. Unit Test Coverage
```bash
uv run pytest tests/unit/ --cov=src --cov-report=term-missing --cov-fail-under=80
```

### 4. Integration Tests
```bash
uv run pytest tests/integration/ --mcp-fake-servers
```

### 5. E2E Smoke Tests
```bash
uv run python examples/run_langgraph_demo.py --goal "demo smoke" --profile demo_power
uv run pytest tests/test_cli_end_to_end.py tests/test_tools_import_security.py
```

### 6. Guardrail Verification
```bash
python scripts/verify_guardrails.py --base origin/main
```

### 7. Stability Harness
```bash
python src/scripts/run_stability_tests.py
```

---

## ⚡ Fast Checks (Pre-Commit)

Run these locally before opening a PR:

```bash
# Guardrail verification
python scripts/verify_guardrails.py

# Linting
uv run ruff check
uv run ruff format --check

# Quick unit tests (no integration/e2e)
uv run pytest tests/unit/ -x --ff
```

---

## 🧩 Test Runner Scripts

### Comprehensive Test Suite
```bash
# Run all tests (unit + integration + e2e + scenarios)
bash src/scripts/run_tests.sh

# Run specific test suite
bash src/scripts/run_tests.sh unit_tests
bash src/scripts/run_tests.sh integration_tests
bash src/scripts/run_tests.sh e2e_tests
bash src/scripts/run_tests.sh scenario_tests
```

### CI-Style Test Execution
```bash
# Mirrors GitHub Actions matrix (Python 3.10-3.12)
uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80

# With stability harness
python src/scripts/run_stability_tests.py
```

---

## 🎯 Coverage Targets Summary

| Component | Target | Rationale |
|-----------|--------|-----------|
| Orchestrator | 80% | Critical path for all workflows |
| Routing | 80% | Deterministic decision-making required |
| Tools | 60% | Large surface area, external dependencies |
| Memory | 60% | Complex state management, can improve iteratively |
| Config | 70% | Many edge cases in precedence/merging |
| Observability | 70% | Instrumentation, not core logic |
| Security | 90% | No gaps in guardrails or redaction |

**Overall Project Target**: ≥ 75% combined coverage

---

## 🐛 Debugging Tests

### Run with Verbose Output
```bash
uv run pytest tests/ -v --tb=short
```

### Run with Trace Logging
```bash
uv run pytest tests/ --log-cli-level=DEBUG
```

### Run Single Test with PDB
```bash
uv run pytest tests/unit/test_orchestrator.py::test_plan_execution -v --pdb
```

### Capture Test Output
```bash
uv run pytest tests/ -v --capture=no
```

### Re-run Failed Tests Only
```bash
uv run pytest tests/ --lf  # last failed
uv run pytest tests/ --ff  # failed first, then others
```

---

## 🔧 Tips & Best Practices

### Port Management
Close stray processes on ports 7860, 8000, 8001, 8888, and 9000 when tests spawn local services:
```bash
# Kill processes on test ports
lsof -ti:8000 | xargs kill -9
lsof -ti:8001 | xargs kill -9
```

### Narrowing Test Scope
Use pytest's `-k` flag to filter tests by name pattern:
```bash
# Run only orchestrator-related tests
PYTEST_ADDOPTS="-k orchestrator" uv run pytest tests/

# Run only allowlist policy tests
uv run pytest tests/ -k "allowlist"
```

### Memory-Backed Tests
Enable the memory dependency group before running memory tests:
```bash
uv sync --group memory
uv run pytest tests/unit/test_memory.py
```

### Registry Fragment Changes
When changing registry fragments or guardrails:
```bash
# 1. Verify guardrails
python scripts/verify_guardrails.py

# 2. Regenerate tier table
python build/gen_tiers_table.py

# 3. Run stability tests
python src/scripts/run_stability_tests.py

# 4. Run relevant integration tests
uv run pytest tests/integration/test_registry_resolution.py -v
```

---

## 📈 Coverage Reports

### Generate HTML Coverage Report
```bash
uv run pytest --cov=src --cov-report=html
open htmlcov/index.html
```

### Generate Terminal Coverage Report
```bash
uv run pytest --cov=src --cov-report=term-missing
```

### Coverage by Layer
```bash
# Orchestrator coverage
uv run pytest tests/unit/test_orchestrator*.py tests/integration/test_orchestrator*.py --cov=src/cuga/orchestrator --cov-report=term

# Routing coverage
uv run pytest tests/unit/test_routing*.py tests/integration/test_routing*.py --cov=src/cuga/routing --cov-report=term

# Tools coverage
uv run pytest tests/unit/test_tools*.py tests/integration/test_tools*.py --cov=src/cuga/modular/tools --cov-report=term
```

---

## 🚦 Test Status Dashboard

Track test coverage and status in the project dashboard:

- **Coverage Badges**: Update in `README.md` based on CI results
- **Test Metrics**: Monitor via Prometheus + Grafana (see `observability/grafana_dashboard.json`)
- **CI Build Status**: GitHub Actions status badges for each test suite

---

## 📚 Additional Resources

- **Test Coverage Matrix**: See `docs/testing/COVERAGE_MATRIX.md` for detailed layer-by-layer analysis
- **Scenario Testing Guide**: See `docs/testing/SCENARIO_TESTING.md` for scenario catalog and patterns
- **MCP Integration Testing**: See `docs/mcp/TESTING.md` for MCP-specific test infrastructure
- **Web Automation Guide**: See `docs/testing/WEB_AUTOMATION.md` for Playwright best practices

---

## 🔄 Continuous Improvement

Test coverage targets are living goals. As the codebase evolves:

1. **Add tests before adding features** (TDD where feasible)
2. **Increase coverage targets** as critical paths are identified
3. **Refactor untested legacy code** with test coverage as you touch it
4. **Document test patterns** for common scenarios (see `tests/README.md`)
5. **Review coverage reports** in every PR review

**Next Steps for Full Production Readiness**:
- 🔴 Increase memory integration test coverage to ≥ 60%
- 🔴 Add scenario tests for all routing policies (allowlist-only, HITL)
- 🔴 Increase observability integration coverage (OTEL export, Prometheus)
- 🟡 Add more MCP fake servers for additional tool categories
- 🟡 Improve orchestrator scenario coverage for nested coordination

## Setup
```bash
uv sync --all-extras --dev
uv run playwright install --with-deps chromium
```

## Pull request quality gates
- **Matrix quality job** (`.github/workflows/ci.yml`): runs ruff lint, mypy, and full pytest coverage (`--cov-fail-under=80`) on Python 3.10–3.12 for every push/PR to `main` and `develop`.
- **Demo & sandbox smoke**: installs Playwright browsers, exercises the LangGraph demo flow (`examples/run_langgraph_demo.py`) and the CLI ingest/query round-trip plus import guardrail checks (`tests/test_cli_end_to_end.py`, `tests/test_tools_import_security.py`). These fast checks catch regressions in the documented sandboxed tool resolution and CLI experience.

## Fast checks
Run the guardrail verifier and linters before opening a pull request:

```bash
python scripts/verify_guardrails.py
uv run ruff check
uv run ruff format --check
```

## Unit and integration tests
Use the bundled test runner to mirror CI behavior. The script runs linters first, then exercises multiple suites.

```bash
# Registry + variables manager + sandbox + E2B lite + selected e2e flows
bash src/scripts/run_tests.sh

# CI-style unit slice
bash src/scripts/run_tests.sh unit_tests
```

To mirror the CI demo smoke locally:

```bash
uv run python examples/run_langgraph_demo.py --goal "demo smoke" --profile demo_power
uv run pytest tests/test_cli_end_to_end.py tests/test_tools_import_security.py
```

CI runs `pytest --cov=src --cov-report=term-missing --cov-fail-under=80` and the stability harness `python src/scripts/run_stability_tests.py` to guard planner/registry/guardrail regressions.

If you need memory-backed tests, enable the memory dependency group before running them (the helper does this automatically for the memory suites it triggers).

## Tips
- Close stray processes on ports 7860, 8000, 8001, 8888, and 9000 when tests spawn local services.
- Use `PYTEST_ADDOPTS="-k <pattern>"` to narrow scope when debugging.
- When changing registry fragments or guardrails, rerun `python scripts/verify_guardrails.py` to ensure routing markers stay in sync.
