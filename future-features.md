# Future Features and Enhancements

## Planner and Execution Engine
- **Adaptive planning modes**: Toggle between LangGraph-first execution and long-horizon semantic-kernel style planning, with dynamic step ceilings derived from workload metadata.
- **Constraint-aware scheduling**: Integrate budget/timebox constraints directly into planning, surfacing soft vs hard limits in traces and UI.
- **Tool routing intelligence**: Introduce learned/heuristic scoring for tool selection that blends description similarity, historical success, and latency budgets.
- **Resumable workflows**: Add checkpointing for interrupted plans with idempotent step replay and trace stitching.

## Memory, RAG, and Knowledge Ops
- **Pluggable vector backends**: Ship connectors for popular self-hosted stores with async batching, retention tiers, and deterministic local fallback search.
- **Profile-aware context**: Enforce per-profile isolation across ingestion, search, and caching; surface profile provenance in every trace and response.
- **Offline embeddings**: Provide multiple deterministic embedding strategies (hashing, TF-IDF, SIF) with benchmark harnesses and guardrails against remote inference.
- **Document lifecycle hooks**: Add ingestion/expiry hooks for governance (redaction, PII scrubbing, retention enforcement) plus audit logs.

## Registry, Sandbox, and Security
- **Registry hot-swap automation**: CLI and CI jobs that validate registry edits, regenerate docs, and roll forward/back with deterministic sorting.
- **Policy packs**: Bundled prompts and adapters for prompt-injection defenses, egress controls, and red-team scenarios with kill switches.
- **Sandbox profiles**: Granular py/node slim/full profiles with mount templates, read-only defaults, and exec caps; per-tool overrides documented in registry fragments.
- **Access budgets**: Built-in budget enforcers (`warn|block`) with per-profile quotas, rolling counters, and alerting hooks.

## Observability & Operations
- **Unified telemetry**: Out-of-the-box dashboards for Langfuse/OpenInference/Traceloop spanning registry discovery, planning, execution, and memory connectors.
- **Trace lineage**: Cross-component `trace_id` propagation visualized in UI with drill-downs for tool invocations, retries, and budget events.
- **Health & chaos**: Synthetic probes and chaos toggles for registries, sandboxes, and memory backends with SLO-aligned alerts.

## Integrations and Surfaces
- **CrewAI/AutoGen adapters**: First-class adapters that respect coordinator/worker semantics, shared memory, and deterministic tool import guards.
- **LangServe-ready APIs**: FastAPI deployment profile with streaming responses, auth/budget middleware, and rollback-safe config toggles.
- **Workspace UX**: Dashboard panels for registry status, budgets, and trace timelines; sandbox diagnostics and tool discovery search.
- **SDK ergonomics**: Typed interfaces for planner/worker/coordinator clients, including Python/TypeScript SDKs with generated schemas.

## Testing, Tooling, and Release
- **Evaluation harness**: Self-play and MCP registry conformance suites with reproducible seeds and coverage gating.
- **Guardrail verifiers**: Automated checks for AGENTS.md anchors, registry determinism, and tool import restrictions in CI.
- **Release automation**: Tagging pipelines aligned to `VERSION.txt`, changelog templating, and backport automation for critical fixes.
