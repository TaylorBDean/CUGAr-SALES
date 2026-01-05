# CUGAR Agent Repository - Complete Explanation for Beginners

Last Updated: 2025-12-31

This document explains the entire CUGAR repository from the ground up, assuming you're new to agent systems.

---

## 🎯 What Is This Repository?

**CUGAR** (Conversational Universal Generative Agent Runtime) is a **local-first AI agent orchestration system**. Think of it like a "smart task manager" that:

1. Takes a complex request from you (e.g., "analyze these files and generate a report")
2. Breaks it down into smaller steps (planning)
3. Decides which tools or agents should handle each step (routing)
4. Executes those steps safely in sandboxes (execution)
5. Combines the results into a final answer (aggregation)

**Key Philosophy**: Run everything locally, keep data private, make decisions deterministic and auditable.

---

## 📂 Repository Structure (Top-Down)

### **Root Level Files** (Configuration & Documentation)

```
cugar-agent/
├── README.md                    # Project overview, quick start guide
├── AGENTS.md                    # 🔴 CRITICAL: Security & design rules (read this first!)
├── ARCHITECTURE.md              # High-level system design explanation
├── CHANGELOG.md                 # Version history and what changed
├── HOW.md                       # This file - complete explanation for beginners
├── todo1.md                     # Development task tracker
├── pyproject.toml               # Python dependencies (managed by uv/pip)
├── settings.toml                # LLM backend settings (which model, temperature, etc.)
├── registry.yaml                # Tool catalog (what tools are allowed, what they do)
├── .env.example                 # Template for environment variables
└── .env.mcp                     # MCP-specific environment overrides
```

**What You Need to Know**:
- **`AGENTS.md`** = The "constitution" of this repo. All code must follow these rules.
- **`registry.yaml`** = The "app store" for tools. If a tool isn't registered here, agents can't use it.
- **`settings.toml`** = Tells the system which AI model to use (defaults to Granite 4.0).

---

## 🏗️ Core Architecture

### **1. `src/cuga` - Core Source Code**

This is where all the real code lives. Let's break it down by responsibility:

#### **A. Orchestration Layer** (The "Brain")

```
src/cuga/orchestrator/
├── protocol.py          # OrchestratorProtocol (the interface all orchestrators follow)
├── failures.py          # FailureMode taxonomy (how to categorize errors)
├── routing.py           # RoutingAuthority (decides which agent/tool handles a task)
└── __init__.py          # Package exports
```

**What This Does**:
- **Orchestrator**: The "conductor" that coordinates everything. It doesn't execute tasks itself—it plans and delegates.
- **Protocol**: Defines lifecycle stages (initialize → plan → route → execute → aggregate → complete).
- **Failures**: Categorizes errors (is it retryable? terminal? whose fault?).
- **Routing**: Decides "who should handle this task?" based on capabilities.

**Analogy**: Imagine a restaurant kitchen. The orchestrator is the head chef who:
- Plans the meal (menu)
- Routes tasks (soup to station 1, steak to station 2)
- Monitors execution (is the soup ready?)
- Aggregates results (plates the final dish)

#### **B. Agent Layer** (The "Workers")

```
src/cuga/agents/
├── lifecycle.py         # AgentLifecycleProtocol (startup/shutdown contracts)
├── contracts.py         # AgentProtocol (input/output standardization)
├── executor.py          # Agent execution wrappers
└── __init__.py
```

**What This Does**:
- **Agents**: Specialized workers that handle specific types of tasks.
  - **PlannerAgent**: Breaks down complex requests into steps.
  - **WorkerAgent**: Executes individual steps using tools.
  - **CoordinatorAgent**: Manages multiple workers in parallel.

**Analogy**: Think of agents as specialized employees:
- Planner = Project manager (creates the task list)
- Worker = Individual contributor (does the actual work)
- Coordinator = Team lead (manages multiple workers)

#### **C. Modular Components** (The "Toolkit")

```
src/cuga/modular/
├── agents.py            # PlannerAgent, CoordinatorAgent, WorkerAgent implementations
├── tools/               # Individual tool implementations
│   ├── calculator.py    # Math operations
│   ├── file_reader.py   # Read files
│   └── ...
└── __init__.py
```

**What This Does**:
- **Tools**: Individual capabilities (like apps on your phone).
  - Each tool has a strict signature: `(inputs: dict, context: dict) -> result`
  - Tools can't do anything malicious (no network, no `eval()`, sandboxed).

**Analogy**: Tools are like physical tools in a workshop:
- Calculator = Adding machine
- File Reader = Magnifying glass
- Code Executor = Workbench with safety guards

#### **D. Configuration Layer** (The "Settings")

```
src/cuga/config/
├── resolver.py          # ConfigResolver (unified config precedence)
├── validators.py        # Environment mode validation
└── __init__.py

src/cuga/config.py       # Dynaconf settings loader (legacy)
```

**What This Does**:
- **ConfigResolver**: Enforces strict precedence for where config values come from:
  ```
  CLI args > env vars > .env files > YAML > TOML > defaults > hardcoded
  ```
- **Validators**: Checks if required environment variables are set before running.

**Analogy**: Like the settings menu in an app, but with strict rules about what overrides what.

#### **E. Providers Layer** (The "AI Backends")

```
src/cuga/providers/
├── watsonx_provider.py  # IBM watsonx Granite integration (DEFAULT)
├── openai_provider.py   # OpenAI integration (optional)
├── anthropic_provider.py # Anthropic integration (optional)
├── ollama_provider.py   # Ollama local models (optional)
└── ...
```

**What This Does**:
- **Providers**: Adapters for different AI models.
  - Each provider translates between CUGAR's standard format and the specific API of an LLM.
  - Default: Granite 4.0 (IBM watsonx).
  - Local option: Ollama (fully offline).

**Analogy**: Like printer drivers—they all do the same job (print), but speak different languages to different printers.

#### **F. Backend Layer** (The "API Server")

```
src/cuga/backend/
├── server/
│   ├── main.py          # FastAPI application (HTTP endpoints)
│   ├── routes/          # API route handlers
│   └── config.py        # Backend configuration
├── llm/
│   └── models.py        # LLMManager (model selection logic)
└── cuga_graph/
    ├── nodes/           # LangGraph agent nodes
    └── state/           # State machine definitions
```

**What This Does**:
- **FastAPI Server**: Web API that lets you interact with CUGAR via HTTP.
  - `POST /api/plan` - Generate a plan
  - `POST /api/execute` - Execute a plan
  - `GET /api/models/{provider}` - List available models
  - `POST /api/config/model` - Save model configuration
- **LangGraph**: Integration with LangChain's graph-based workflow system.

**Analogy**: The backend is like a restaurant's front desk:
- You place an order (HTTP request)
- They relay it to the kitchen (orchestrator)
- You get your meal (HTTP response)

#### **G. MCP Layer** (The "Tool Protocol")

```
src/cuga/mcp/
├── server.py            # MCP protocol server
├── lifecycle.py         # MCP server lifecycle management
└── ...

src/cuga/mcp_v2/
└── registry/            # MCP v2 registry integration
```

**What This Does**:
- **MCP** (Model Context Protocol): A standard for tools to communicate with AI systems.
- CUGAR can act as an MCP server, exposing its tools to other systems.
- Think of it as an API for tools.

**Analogy**: MCP is like USB-C—a universal connector for tools.

---

### **2. `configs` - Agent Configurations**

```
configs/
├── agent.demo.yaml      # Demo agent configuration
├── memory.yaml          # Memory system settings
├── rag.yaml             # RAG (retrieval) settings
└── observability.yaml   # Logging/tracing settings
```

**What This Does**:
- YAML files that define how agents behave.
- Example: `agent.demo.yaml` might say "use Granite 4.0, temperature=0.0, max_tokens=8192".

**Analogy**: Like preference files for each agent (think `.vimrc` or `.bashrc`).

---

### **3. `configurations` - System Configurations**

```
configurations/
├── models/
│   ├── settings.watsonx.toml    # Granite 4.0 model settings (DEFAULT)
│   ├── settings.openai.toml     # OpenAI model settings
│   ├── settings.anthropic.toml  # Anthropic model settings
│   └── ...
├── policies/                    # Sandbox security policies
│   ├── default_input.yaml       # Input validation rules
│   ├── default_output.yaml      # Output sanitization rules
│   └── default_tool.yaml        # Tool execution constraints
├── profiles/                    # Profile-specific settings
└── _shared/                     # Default configuration files
```

**What This Does**:
- **Model Settings**: Which specific model to use per provider.
- **Policies**: Security rules (what can tools access?).
- **Profiles**: User-specific or environment-specific overrides.

**Analogy**: Like security settings in your OS (firewall rules, app permissions).

---

### **4. `docs` - Documentation**

```
docs/
├── orchestrator/
│   ├── ORCHESTRATOR_CONTRACT.md  # How orchestrators must behave
│   ├── FAILURE_MODES.md          # Error categorization
│   ├── ROUTING_AUTHORITY.md      # Routing decisions
│   └── EXECUTION_CONTEXT.md      # Context propagation
├── agents/
│   ├── AGENT_LIFECYCLE.md        # Startup/shutdown contracts
│   ├── AGENT_IO_CONTRACT.md      # Input/output standardization
│   └── STATE_OWNERSHIP.md        # Who owns what state
├── configuration/
│   ├── CONFIG_RESOLUTION.md      # Configuration precedence (Phase 3 implementation)
│   └── ENVIRONMENT_MODES.md      # Required env vars per mode
├── testing/
│   ├── COVERAGE_MATRIX.md        # Test coverage analysis
│   └── SCENARIO_TESTING.md       # End-to-end test patterns
├── examples/
│   └── ENTERPRISE_WORKFLOWS.md   # Real-world usage examples
├── observability/
│   └── OBSERVABILITY_GUIDE.md    # Logging/tracing guide
└── DEVELOPER_ONBOARDING.md       # New developer guide
```

**What This Does**:
- **Contracts**: Formal specifications ("if you build an orchestrator, it must do X, Y, Z").
- **Guides**: How to use the system, how to extend it, how to debug it.

**Analogy**: Like the manual that comes with a car—explains how everything works.

---

### **5. `tests` - Test Suite**

```
tests/
├── unit/
│   ├── config/                          # Config resolver tests (83 tests)
│   │   ├── test_config_resolution.py    # Precedence, deep merge, provenance
│   │   └── test_env_validation.py       # Environment mode validation
│   ├── test_orchestrator_protocol.py    # Orchestrator tests (35+ tests)
│   ├── test_agent_lifecycle.py          # Agent lifecycle tests (30+ tests)
│   └── ...
├── integration/
│   └── test_ui_backend_alignment.py     # UI/backend tests (56 tests)
└── scenario/
    ├── test_agent_composition.py        # Multi-agent workflow tests
    └── test_stateful_agent.py           # Conversation persistence tests
```

**What This Does**:
- **Unit Tests**: Test individual components in isolation.
- **Integration Tests**: Test components working together (e.g., frontend ↔ backend).
- **Scenario Tests**: Test real-world workflows end-to-end.

**Test Statistics**:
- Total: 139+ tests
- Unit tests: 83 (config resolution + validation)
- Integration tests: 56 (UI/backend alignment)
- Scenario tests: Various (multi-agent, stateful conversations)

**Analogy**: Like quality assurance testing—make sure everything works before shipping.

---

### **6. `examples` - Example Code**

```
examples/
├── granite_function_calling.py  # How to use Granite 4.0
├── multi_agent_dispatch.py      # Coordinator managing workers
├── rag_query.py                 # RAG-augmented queries
└── workflows/                   # (Documented, not implemented yet)
```

**What This Does**:
- Working code samples showing how to use CUGAR.
- Copy-paste starting points for common tasks.

**Analogy**: Like "getting started" tutorials.

---

### **7. `scripts` - Utility Scripts**

```
scripts/
├── verify_guardrails.py         # Check code follows AGENTS.md rules
├── validate_env.py              # Check required env vars are set
└── registry_generator.py        # Generate registry documentation
```

**What This Does**:
- Helper scripts for maintenance and validation.
- Run before committing to ensure code quality.

**Analogy**: Like build tools or linters.

---

### **8. `src/frontend_workspaces` - User Interface**

```
src/frontend_workspaces/
└── agentic_chat/
    └── src/
        ├── ModelConfig.tsx      # Model selection UI
        ├── App.tsx              # Main application
        └── ...
```

**What This Does**:
- React frontend for interacting with CUGAR via a web UI.
- Features:
  - Dropdown to select provider/model
  - Text box to enter requests
  - Configuration save/load
  - Error handling with user-friendly messages

**Analogy**: Like a GUI for a command-line tool.

---

## 🧠 How Everything Fits Together (Data Flow)

Let me trace what happens when you make a request:

```
1. USER REQUEST
   ↓
   "Analyze these Python files and create a summary"

2. ENTRY POINT (CLI or HTTP)
   ↓
   src/cuga/cli.py OR src/cuga/backend/server/main.py
   ↓
   Validates input, creates ExecutionContext (trace_id, user_id, etc.)

3. ORCHESTRATOR (The Brain)
   ↓
   src/cuga/orchestrator/protocol.py
   ↓
   Stage 1: INITIALIZE (set up context)
   Stage 2: PLAN (call PlannerAgent)

4. PLANNER AGENT (Task Breakdown)
   ↓
   src/cuga/modular/agents.py → PlannerAgent
   ↓
   Uses Granite 4.0 to create steps:
   [
     {step: 1, action: "list_files", tool: "file_reader"},
     {step: 2, action: "analyze_code", tool: "code_analyzer"},
     {step: 3, action: "generate_summary", tool: "summarizer"}
   ]

5. ORCHESTRATOR (Routing)
   ↓
   Stage 3: ROUTE (call RoutingAuthority)
   ↓
   src/cuga/orchestrator/routing.py
   ↓
   Decides which WorkerAgent handles each step

6. WORKER AGENTS (Execution)
   ↓
   src/cuga/modular/agents.py → WorkerAgent
   ↓
   For each step:
     - Loads tool from registry (src/cuga/modular/tools/)
     - Executes in sandbox (enforces security policies)
     - Returns result or error

7. ORCHESTRATOR (Aggregation)
   ↓
   Stage 5: AGGREGATE (combine results)
   ↓
   Merges all step results into final answer

8. RESPONSE
   ↓
   Returns structured JSON:
   {
     "status": "success",
     "result": "Summary of Python files...",
     "trace_id": "abc-123",
     "metadata": {...}
   }
```

---

## 🔒 Key Security Concepts

### **1. Sandboxing**
- Tools run in **isolated sandboxes** (separate processes/containers).
- Default: read-only filesystem, no network access.
- Defined in `registry.yaml` per tool.
- Sandbox profiles: `py_slim`, `py_full`, `node_slim`, `node_full`, `orchestrator`

### **2. Allowlists/Denylists**
- Only tools under `cuga.modular.tools.*` can be imported.
- No `eval()`, `exec()`, or arbitrary code execution.
- Enforced by `AGENTS.md` rules.
- Dynamic imports restricted to allowlisted namespaces.

### **3. Budget Enforcement**
- `AGENT_BUDGET_CEILING=100` limits token usage.
- Prevents runaway costs or infinite loops.
- Budget policy: `warn` (log warning) or `block` (reject request).

### **4. Profile Isolation**
- Different "profiles" (user contexts) keep data separate.
- Example: User A's memory never leaks into User B's.
- Enforced at memory layer and sandbox level.

### **5. PII Redaction**
- Automatic redaction of secrets, tokens, passwords in logs.
- Keys matching `secret`, `token`, `password` are scrubbed.
- Configured in observability settings.

---

## 🎨 Key Design Patterns

### **1. Adapter Pattern (Providers)**
```python
# All providers implement the same interface
class WatsonxProvider:
    def generate(self, prompt: str, **kwargs) -> dict:
        # Translate to watsonx API
        ...

class OpenAIProvider:
    def generate(self, prompt: str, **kwargs) -> dict:
        # Translate to OpenAI API
        ...

class OllamaProvider:
    def generate(self, prompt: str, **kwargs) -> dict:
        # Translate to Ollama API (fully local)
        ...
```

### **2. Protocol Pattern (Contracts)**
```python
# All orchestrators must implement this
class OrchestratorProtocol(Protocol):
    def orchestrate(self, request: AgentRequest) -> Iterator[LifecycleEvent]:
        """
        Lifecycle stages:
        1. Initialize - Set up context
        2. Plan - Generate execution plan
        3. Route - Decide which agents handle tasks
        4. Execute - Run tasks
        5. Aggregate - Combine results
        6. Complete - Finalize and return
        """
        ...
```

### **3. Registry Pattern (Tools)**
```yaml
# registry.yaml
tools:
  calculator:
    module: cuga.modular.tools.calculator
    description: "Performs arithmetic operations"
    sandbox_profile: "py_slim"
    parameters:
      - name: expression
        type: string
        required: true
```

### **4. Precedence Pattern (Configuration)**
```python
# ConfigResolver enforces explicit precedence
ConfigLayer.CLI (7)        # Highest precedence
  > ConfigLayer.ENV (6)
  > ConfigLayer.DOTENV (5)
  > ConfigLayer.YAML (4)
  > ConfigLayer.TOML (3)
  > ConfigLayer.DEFAULT (2)
  > ConfigLayer.HARDCODED (1)  # Lowest precedence
```

---

## 🚀 How to Actually Use This

### **Scenario 1: Run Locally (CLI)**
```bash
# 1. Set up environment
cp .env.example .env
# Edit .env: Add WATSONX_API_KEY, WATSONX_PROJECT_ID

# 2. Install dependencies
uv sync  # or pip install -e .

# 3. Run a request
cuga plan "Calculate 42 * 7"
# Output: JSON plan with steps

cuga execute --trace-id <trace_id_from_plan>
# Output: Execution results
```

### **Scenario 2: Run as Service (HTTP)**
```bash
# 1. Set environment variables
export AGENT_TOKEN=$(openssl rand -hex 32)
export AGENT_BUDGET_CEILING=100
export WATSONX_API_KEY=your-api-key
export WATSONX_PROJECT_ID=your-project-id

# 2. Start the server
uvicorn cuga.backend.server.main:app --host 0.0.0.0 --port 8000

# 3. Make requests via HTTP
curl -X POST http://localhost:8000/api/plan \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $AGENT_TOKEN" \
  -d '{"goal": "Calculate 42 * 7"}'

# 4. List available models
curl http://localhost:8000/api/models/watsonx
```

### **Scenario 3: Use the UI**
```bash
# 1. Start backend
uvicorn cuga.backend.server.main:app --port 8000

# 2. Start frontend (in another terminal)
cd src/frontend_workspaces/agentic_chat
npm install
npm start

# 3. Open browser to http://localhost:3000
# - Select provider (watsonx, openai, anthropic, ollama)
# - Select model (granite-4-h-small, granite-4-h-micro, granite-4-h-tiny)
# - Adjust temperature (0.0 = deterministic, 2.0 = creative)
# - Enter request
```

### **Scenario 4: Run 100% Offline with Ollama**
```bash
# 1. Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Download a model
ollama pull granite-code:3b  # or any other model

# 3. Configure CUGAR to use Ollama
# Edit .env:
# MODEL_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# MODEL_NAME=granite-code:3b

# 4. Run without internet
cuga plan "Explain recursion" --offline
```

---

## 🔧 Configuration Details

### **Environment Variables (Required per Mode)**

#### **LOCAL Mode** (CLI development)
```bash
# Required: At least one provider
WATSONX_API_KEY=your-key
WATSONX_PROJECT_ID=your-project

# OR
OPENAI_API_KEY=your-key

# OR
ANTHROPIC_API_KEY=your-key

# Optional
MODEL_NAME=granite-4-h-small
PROFILE=default
CUGA_VECTOR_BACKEND=chroma
```

#### **SERVICE Mode** (FastAPI backend)
```bash
# Required
AGENT_TOKEN=your-secret-token
AGENT_BUDGET_CEILING=100
# Plus one provider (watsonx/openai/anthropic)

# Optional
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
LANGFUSE_PUBLIC_KEY=pk-xxx
LANGFUSE_SECRET_KEY=sk-xxx
```

#### **MCP Mode** (MCP orchestration)
```bash
# Required
MCP_SERVERS_FILE=./configurations/mcp_servers.yaml
CUGA_PROFILE_SANDBOX=docker
# Plus one provider

# Optional
MODEL_NAME=granite-4-h-small
```

#### **TEST Mode** (CI/test)
```bash
# No env vars required (uses defaults/mocks)
PYTEST_TIMEOUT=300  # Optional
CUGA_TEST_PROFILE=ci  # Optional
```

### **Model Selection**

**Granite 4.0 Variants** (IBM watsonx - DEFAULT):
- `granite-4-h-small`: Balanced performance, 8192 tokens (default)
- `granite-4-h-micro`: Lightweight, fast inference, 8192 tokens
- `granite-4-h-tiny`: Minimal resource usage, 8192 tokens

**OpenAI Models**:
- `gpt-4o`: Most capable, 128k tokens (default)
- `gpt-4o-mini`: Fast and affordable, 128k tokens
- `gpt-4-turbo`: Previous generation, 128k tokens

**Anthropic Models**:
- `claude-3-5-sonnet-20241022`: Best balance, 200k tokens (default)
- `claude-3-opus-20240229`: Most capable, 200k tokens
- `claude-3-haiku-20240307`: Fastest, 200k tokens

**Local Models** (Ollama):
- Any model available via `ollama list`
- Examples: `llama3:8b`, `mistral:7b`, `granite-code:3b`

---

## 📊 Recent Development (Phases 1-4)

### **Phase 1: Analysis & Confirmation** ✅
- Audited existing Granite 3.x integration
- Identified configuration fragmentation and UI/backend mismatches
- Documented upgrade path to Granite 4.0

### **Phase 2: Granite 4.0 Hardening** ✅
- Upgraded to Granite 4.0 models (small, micro, tiny)
- Set deterministic defaults (temperature=0.0)
- Created backend model catalog API (`GET /api/models/{provider}`)
- Updated frontend to dynamic model dropdown
- Aligned provider defaults across all layers

**Files Modified** (10):
- `src/cuga/providers/watsonx_provider.py`
- `src/cuga/configurations/models/settings.watsonx.toml`
- `src/cuga/backend/llm/models.py`
- `src/cuga/backend/server/main.py`
- `src/frontend_workspaces/agentic_chat/src/ModelConfig.tsx`
- `examples/granite_function_calling.py`
- `.env.example`
- `README.md`
- `docs/configuration/ENVIRONMENT_MODES.md`
- `CHANGELOG.md`

### **Phase 3: Configuration Resolver** ✅
- Implemented unified config resolution with explicit precedence (CLI > ENV > DOTENV > YAML > TOML > DEFAULT > HARDCODED)
- Added provenance tracking for observability (every value knows its source)
- Created environment mode validation (local/service/mcp/test)
- Wrote 83 unit tests for config resolution and validation

**Files Created** (6):
- `src/cuga/config/__init__.py`
- `src/cuga/config/resolver.py` (680 lines)
- `src/cuga/config/validators.py` (380 lines)
- `tests/unit/config/__init__.py`
- `tests/unit/config/test_config_resolution.py` (59 tests)
- `tests/unit/config/test_env_validation.py` (24 tests)

### **Phase 4: UI/Backend Alignment** ✅
- Created 56 integration tests validating end-to-end flow
- Enhanced frontend error handling with user-friendly messages (401/403/404/422/500)
- Verified provider switching and configuration persistence
- Validated Granite 4.0 specific functionality

**Files Created** (2):
- `tests/integration/__init__.py`
- `tests/integration/test_ui_backend_alignment.py` (56 tests, 540 lines)

**Files Modified** (1):
- `src/frontend_workspaces/agentic_chat/src/ModelConfig.tsx` (added error handling and banner UI)

### **Total Deliverables**
- **Files Created**: 13
- **Files Modified**: 11
- **Tests Written**: 139 (83 unit + 56 integration)
- **Documentation Updated**: 5 major docs

---

## 📚 Where to Go from Here

### **If you want to...**

#### **Understand the architecture**
1. Read `ARCHITECTURE.md` (high-level design)
2. Read `docs/orchestrator/ORCHESTRATOR_CONTRACT.md` (orchestration details)
3. Read `docs/agents/AGENT_LIFECYCLE.md` (agent behavior)

#### **Write a custom tool**
1. Read `docs/DEVELOPER_ONBOARDING.md` Part 3 (tool development guide)
2. Look at `src/cuga/modular/tools/calculator.py` (example tool)
3. Add entry to `registry.yaml`
4. Write tests in `tests/unit/test_my_tool.py`

#### **Write a custom agent**
1. Read `docs/DEVELOPER_ONBOARDING.md` Part 4 (agent development guide)
2. Study `src/cuga/modular/agents.py` (PlannerAgent, WorkerAgent, CoordinatorAgent)
3. Implement `AgentProtocol` interface
4. Write scenario tests in `tests/scenario/test_my_agent.py`

#### **Deploy to production**
1. Read `docs/configuration/ENVIRONMENT_MODES.md` (environment requirements)
2. Read `PRODUCTION_READINESS.md` (deployment checklist)
3. Set up observability (OTEL, LangFuse, or LangSmith)
4. Configure budget enforcement (`AGENT_BUDGET_CEILING`)

#### **Add tests**
1. Read `docs/testing/SCENARIO_TESTING.md` (end-to-end test patterns)
2. Read `docs/testing/COVERAGE_MATRIX.md` (coverage analysis)
3. Look at `tests/integration/test_ui_backend_alignment.py` (integration test example)
4. Look at `tests/unit/config/test_config_resolution.py` (unit test example)

#### **Debug issues**
1. Read `docs/observability/OBSERVABILITY_GUIDE.md` (logging/tracing)
2. Check `trace_id` in logs (follows request through entire system)
3. Use `ConfigResolver.dump()` to see where config values come from
4. Enable debug logging: `export LOG_LEVEL=DEBUG`

---

## 🔑 Key Files to Read (in order)

1. **`AGENTS.md`** - The rules (security, design patterns, guardrails)
2. **`ARCHITECTURE.md`** - The system design (components, data flow)
3. **`docs/DEVELOPER_ONBOARDING.md`** - Hands-on guide (tools, agents, workflows)
4. **`docs/orchestrator/ORCHESTRATOR_CONTRACT.md`** - How orchestration works
5. **`docs/configuration/CONFIG_RESOLUTION.md`** - How configuration works (Phase 3 implementation)
6. **`docs/agents/AGENT_IO_CONTRACT.md`** - Agent input/output standardization

---

## ❓ Common Questions

### **Q: Why is everything so strict (protocols, contracts, guardrails)?**
**A:** Security and reliability. When AI agents execute code, you need strong boundaries to prevent accidents or attacks. The protocols ensure predictable behavior and auditability.

### **Q: Can I use this without Granite 4.0?**
**A:** Yes! Change `MODEL_PROVIDER` in `.env` to `openai`, `anthropic`, `ollama`, etc. The frontend dropdown supports all providers, and the backend API dynamically lists available models.

### **Q: Can I run this 100% offline?**
**A:** Almost. Steps:
1. Download model weights first (e.g., via Ollama: `ollama pull granite-code:3b`)
2. Set `MODEL_PROVIDER=ollama` in `.env`
3. CUGAR can now run without internet
4. Note: Initial setup (downloading dependencies) requires internet

### **Q: What's the difference between an Agent and a Tool?**
**A:** 
- **Tools** = Individual functions (calculator, file reader, code executor)
- **Agents** = Decision-makers that use tools (planner, worker, coordinator)
- Tools are passive (wait to be called), agents are active (make decisions)

### **Q: Why are there so many config files?**
**A:** Different layers of the system need different settings:
- `settings.toml` = LLM backend settings
- `configs/*.yaml` = Agent behavior settings
- `configurations/models/*.toml` = Provider-specific model settings
- `configurations/policies/*.yaml` = Security policies
- `registry.yaml` = Tool catalog
- ConfigResolver merges them all with explicit precedence

### **Q: What's the "orchestrator" vs "coordinator"?**
**A:** 
- **Orchestrator** = Top-level brain (lifecycle manager, follows OrchestratorProtocol)
- **Coordinator** = Specific agent type that manages parallel workers
- Orchestrator is an interface, Coordinator is an implementation

### **Q: How do I add a new model provider?**
**A:**
1. Create `src/cuga/providers/my_provider.py` implementing the provider interface
2. Add provider config to `configurations/models/settings.my_provider.toml`
3. Add provider entry to backend model catalog in `src/cuga/backend/server/main.py`
4. Update frontend dropdown in `src/frontend_workspaces/agentic_chat/src/ModelConfig.tsx`
5. Add integration tests in `tests/integration/test_ui_backend_alignment.py`

### **Q: What's the difference between `configs/` and `configurations/`?**
**A:**
- `configs/` = Agent-level configs (how agents behave)
- `configurations/` = System-level configs (model settings, policies, profiles)
- Think: `configs/` = application layer, `configurations/` = infrastructure layer

### **Q: How does error handling work?**
**A:** Three-tier error handling:
1. **FailureMode categorization**: AGENT/SYSTEM/RESOURCE/POLICY/USER errors
2. **RetryPolicy**: Exponential backoff, linear, or no retry based on failure mode
3. **Frontend display**: User-friendly messages with actionable guidance

### **Q: What's trace_id and why is it everywhere?**
**A:** `trace_id` is a unique identifier that follows a request through the entire system:
- Created at entry point (CLI or HTTP)
- Propagated through all agents, tools, and workers
- Logged with every operation
- Used for debugging and observability
- Enables correlation across distributed logs

### **Q: How do I contribute?**
**A:**
1. Read `CONTRIBUTING.md` (contribution guidelines)
2. Read `AGENTS.md` (design rules)
3. Create a branch: `git checkout -b feature/my-feature`
4. Write tests (we require 80%+ coverage)
5. Run `python scripts/verify_guardrails.py` before committing
6. Submit PR with clear description and updated docs

---

## 🎯 Quick Start Cheat Sheet

```bash
# Install dependencies
uv sync

# Set up environment (choose one provider)
cp .env.example .env
# Edit .env: Add WATSONX_API_KEY + WATSONX_PROJECT_ID
# OR add OPENAI_API_KEY
# OR set MODEL_PROVIDER=ollama (fully local)

# Run tests
pytest tests/unit/ -v              # Unit tests
pytest tests/integration/ -v       # Integration tests
pytest tests/scenario/ -v          # Scenario tests

# Run CLI
cuga plan "Your request here"
cuga execute --trace-id abc-123

# Run backend
export AGENT_TOKEN=$(openssl rand -hex 32)
uvicorn cuga.backend.server.main:app --reload

# Run frontend
cd src/frontend_workspaces/agentic_chat
npm install && npm start

# Verify configuration
python -c "from cuga.config import validate_environment_mode, EnvironmentMode; print(validate_environment_mode(EnvironmentMode.LOCAL))"

# Check guardrails
python scripts/verify_guardrails.py --base main

# Generate registry docs
python build/gen_tiers_table.py
```

---

## 📞 Getting Help

- **Issues**: https://github.com/TylrDn/cugar-agent/issues
- **Discussions**: https://github.com/TylrDn/cugar-agent/discussions
- **Documentation**: Check `docs/` directory
- **Examples**: Check `examples/` directory
- **Logs**: Check `logging/traces/` for trace data

---

**Last Updated**: 2025-12-31  
**Version**: Phase 4 Complete (Granite 4.0 Integration Hardening)  
**Status**: Production Ready ✅
