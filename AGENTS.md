# AGENTS.md (Single Source of Truth)

> Canonical instructions now live in `docs/AGENTS.md`. This file mirrors the same guardrails for convenience; consult `docs/AGENTS.md` for the definitive, kept-in-sync version.

---

## Guardrail Hierarchy
- `docs/AGENTS.md` remains the canonical source; this root file mirrors it.
- Any nested `AGENTS.md` may only **tighten** these guardrails and must explicitly inherit from this hierarchy.
- No nested guardrail may relax or override canonical rules.

---

## Design Tenets
- Security-first, offline-first defaults with strict allowlists/denylists and deterministic behavior.
- Registry-driven control planes only; tool swaps, sandbox changes, or vendor bindings MUST land as `registry.yaml` diffs with deterministic ordering and audit traces.
- Agents orchestrate intent; **tools execute capabilities**; adapters bind vendors.
- Human authority is preserved for all irreversible actions.

---

## Capability-First Architecture (Canonical)

CUGAr systems MUST be designed **capability-first**, not vendor-first.

### Core Principle
> Agents do not integrate with vendors.  
> Agents orchestrate **capabilities**.  
> Vendors satisfy capabilities via optional adapters.

This enables:
- Enterprise data sovereignty
- Late-binding of vendors
- Stability under procurement, security, or vendor churn
- Offline-first development and deterministic testing

### Architectural Layers
```

Agents     → Orchestrate intent across domains
Tools      → Implement vendor-agnostic capabilities
Adapters   → Bind capabilities to vendor APIs (optional, swappable)

```

### Prohibited Patterns
- ❌ Vendor-specific tool names (e.g. `send_outlook_email`)
- ❌ Agents referencing adapters directly
- ❌ Tool logic that assumes a specific SaaS provider

All tools MUST express **sales or operational intent**, not infrastructure.

---

## Canonical Core Domains (Authoritative)

All sales-oriented systems built on CUGAr MUST align to the following **non-overlapping Core Domains**.  
Domains are **orthogonal** and **independently governable**.

### The Canonical Domains
1. Territory & Capacity Planning
2. Account & Prospect Intelligence
3. Product & Knowledge Enablement
4. Outreach & Engagement
5. Qualification & Deal Progression
6. Analytics, Learning & Governance

### Domain Invariants
Each domain:
- Answers a distinct sales or operational question
- Can be used independently
- Does not assume availability of other domains
- Is implemented via **tools**, never via agents
- Is governed via profiles and registry rules

No domain may bypass another domain’s guardrails.

---

## Agent Roles & Interfaces

### PlannerAgent
- Accepts `(goal: str, metadata: dict)`
- Produces ordered steps with streaming-friendly traces
- MUST rank tools by similarity/metadata (no blind enumeration)
- MUST attach a `ToolBudget` to every plan

### WorkerAgent
- Executes ordered steps against allowlisted tools
- Enforces schemas, budgets, retry policies, and sandbox rules
- Supports partial-result recovery

### CoordinatorAgent
- Preserves trace ordering
- Delegates routing exclusively to `RoutingAuthority`
- Thread-safe, deterministic dispatch

---

## Canonical Protocols (Non-Negotiable)

### OrchestratorProtocol
All orchestration logic MUST implement `cuga.orchestrator.OrchestratorProtocol`:
- Lifecycle stages: initialize → plan → route → execute → aggregate → complete
- Immutable `ExecutionContext` with `trace_id` continuity
- Explicit routing decisions
- Structured error propagation with failure modes

See `docs/orchestrator/ORCHESTRATOR_CONTRACT.md`.

---

### AgentLifecycleProtocol
All agents MUST implement `cuga.agents.lifecycle.AgentLifecycleProtocol`:
- Idempotent startup
- Timeout-bounded shutdown
- Explicit resource ownership
- No leaked state

See `docs/agents/AGENT_LIFECYCLE.md`.

---

### AgentProtocol (I/O Contract)
All agents MUST implement:
```

process(AgentRequest) → AgentResponse

```

Standardizes:
- Inputs: goal, task, metadata, constraints, context
- Outputs: status, result/error, trace, metadata

Eliminates special-casing in orchestration.

---

### Failure Modes (Canonical)
All failures MUST be classified as:
- AGENT
- SYSTEM
- RESOURCE
- POLICY
- USER

Retry semantics MUST be delegated to `RetryPolicy`.  
Partial success MUST be preserved and recoverable.

See `docs/orchestrator/FAILURE_MODES.md`.

---

## Capability Contracts (Canonical)

All tools under `cuga.modular.tools.*` MUST implement a **Capability Contract**.

### Capability Contract Requirements
Each capability MUST declare:
- Purpose (sales or operational intent)
- Inputs (structured, deterministic)
- Outputs (structured, explainable)
- Guardrails (what it MUST NOT do)
- Side-effect class:
  - `read-only`
  - `propose`
  - `execute` (rare, gated)

### Canonical Capability Examples
- `draft_outbound_message`
- `retrieve_product_knowledge`
- `schedule_engagement_touchpoint`
- `simulate_territory_change`
- `explain_recommendation`

### Hard Rules
- Capabilities MUST work without adapters
- Capabilities MUST be testable offline
- Capabilities MUST NOT mutate CRM or external systems unless explicitly approved

---

## Adapter Model (Deferred Vendor Binding)

Adapters bind vendors to capabilities and are OPTIONAL.

### Adapter Rules
- Live under `cuga.adapters.*`
- MUST NOT be referenced by agents
- MUST implement one or more capability contracts
- MUST use SafeClient and Secrets enforcement
- MUST be hot-swappable or disableable

### Adapter Failure Semantics
If an adapter is unavailable:
- Capability remains callable
- System degrades gracefully
- User is informed of reduced execution scope

Capabilities MUST NOT fail solely due to missing adapters.

---

## Sales Capability Domains Mapping

```

cuga.modular.tools.sales
├── territory        # ownership, capacity, simulation
├── intelligence     # signals, normalization, confidence
├── knowledge        # docs, summaries, relevance
├── engagement       # drafts, sequencing, scheduling
├── qualification    # BANT/MEDDICC, risk
└── governance       # explainability, audit, replay

```

### Domain Guardrails
- Territory: simulation-only, no ownership mutation
- Intelligence: advisory only, no blind overwrite
- Knowledge: read-only, no pricing or legal claims
- Engagement: draft/propose only, human approval required
- Qualification: conservative bias, surface unknowns
- Governance: append-only, immutable history

---

## Over-Automation Prohibitions (Canonical)

The following are FORBIDDEN unless explicitly approved by policy and profile:

- ❌ Auto-sending emails or messages
- ❌ Auto-assigning territories or accounts
- ❌ Auto-closing deals or forecasting outcomes
- ❌ Auto-modifying pricing, contracts, or legal terms

Systems MUST:
- Propose actions
- Explain reasoning
- Simulate outcomes
- Require human approval for irreversible changes

---

## Tool Contract

- Tools live under `cuga.modular.tools.*` only
- Signature: `(inputs: Dict[str, Any], context: Dict[str, Any]) -> Any`
- No `eval`/`exec`
- No network unless profile allows
- Parameters and IO MUST be declared

### HTTP Client (Canonical)
All HTTP MUST use `cuga.security.http_client.SafeClient`:
- 10s read / 5s connect timeouts
- Exponential backoff (4 attempts)
- URL redaction in logs
- No raw httpx/requests/urllib

---

### Secrets Management (Canonical)
- Env-only secrets
- No hardcoded credentials
- CI enforces `.env.example` parity
- Automatic redaction via `redact_dict()`

---

## Memory & RAG
- Deterministic/local embeddings by default
- Metadata MUST include `profile` and `path`
- No cross-profile leakage

---

## Observability & Tracing
- Structured, PII-safe logs
- Mandatory `trace_id` propagation
- Canonical events:
  `plan_created`, `route_decision`, `tool_call_start`, `tool_call_complete`,
  `tool_call_error`, `budget_warning`, `budget_exceeded`,
  `approval_requested`, `approval_received`, `approval_timeout`

- Golden Signals:
  success_rate, latency (P50/P95/P99), tool_error_rate,
  mean_steps_per_task, approval_wait_time, budget_utilization

---

## Testing Invariants
- >80% coverage required
- Critical orchestration paths MUST have integration tests
- Import guardrails enforced
- Planner MUST NOT return all tools blindly
- Round-robin routing verified under concurrency

---

## Change Management
- Edit `AGENTS.md` first for guardrail changes
- Update `CHANGELOG.md`, `README.md`, `PRODUCTION_READINESS.md`, `todo1.md`
- Registry diffs require synced documentation and tests
- Run `scripts/verify_guardrails.py --base <ref>` before merge

---

## Enterprise Uncertainty Principle (Canonical)

CUGAr systems MUST assume:
- Vendors may change
- Access may be revoked
- Security reviews may delay integration

Systems MUST remain:
- Useful without vendors
- Deterministic offline
- Explainable and auditable
- Stable under partial capability loss

This principle overrides convenience and novelty.

---

## Contributor Checklist (TL;DR)
- Read this file first
- Design capabilities, not integrations
- Preserve determinism and explainability
- Never bypass registry, budgets, or guardrails
- Favor boring, reliable systems over clever ones

---

**If in doubt, choose the path that maximizes trust, auditability, and reversibility.**
