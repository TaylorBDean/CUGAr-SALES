# CUGAR Agent Stable Local Launch Guide

This guide summarizes the minimal steps needed to reach a stable, deterministic local bring-up with registry-driven plugins (OpenAPI + MCP), sandbox defaults, and Langflow readiness. Follow the order below to avoid mixing concerns or introducing instability.

## 1. Baseline sanity check
1. Install dependencies and verify the CLI wiring:
   ```bash
   uv sync
   cuga start demo
   ```
2. Fix any dependency or CLI issues before enabling extra providers or plugins.

## 2. Lock the execution model (single provider)
Use one provider per profile for deterministic behavior (no automatic fallback). Example `.env` for an OpenAI-compatible local proxy (e.g., LiteLLM → Ollama):
```env
AGENT_SETTING_CONFIG=settings.openai.toml
OPENAI_BASE_URL=http://localhost:4000/v1
OPENAI_API_KEY=local
```
If you switch to WatsonX/Granite, mirror the same pattern: set the provider-specific base URL and key, and ensure other providers are unset.

**Provider-specific notes**
- **IBM Granite 4.x / WatsonX**: keep `AGENT_SETTING_CONFIG` pointed at the WatsonX settings file, set `WATSONX_APIKEY` and `WATSONX_ENDPOINT` (or LiteLLM proxy URL), and leave OpenAI keys blank. Disable fallback routing so plans stay deterministic.
- **LiteLLM → Ollama (offline)**: run `OPENAI_BASE_URL=http://localhost:4000/v1`, provide the LiteLLM key, and pin models to the local Granite/Llama variant you have pulled. Keep temperature/range within the validated bounds (`MODEL_TEMPERATURE` 0..2) to satisfy the env parsing guardrails described in `AGENTS.md`.
- **Langflow**: when testing flows, reuse the same single-provider profile; do not introduce a separate provider inside Langflow nodes.

**Isolation guardrails**
- Keep only one provider section populated in `.env`/`AGENT_SETTING_CONFIG`; leave competing provider keys blank to avoid implicit fallback chains.
- Reuse the README/USAGE quickstart pattern when swapping providers (only change the provider URL/key) so planning/execution stays deterministic across profiles.

## 3. Start the registry (tool discovery)
Launch the registry with the canonical MCP servers file:
```bash
export MCP_SERVERS_FILE=src/cuga/backend/tools_env/registry/config/mcp_servers.yaml
cuga registry start
```
Verify discovery at http://127.0.0.1:8001/applications and confirm both `services` (OpenAPI) and `mcpServers` entries are present. New plugins should be added via `registry.yaml` or registry fragments, not hard-coded.

**Registry-driven workflow**
- Declare new tools in `registry.yaml` or fragments only; let Hydra composition enforce YAML validity and detect name collisions.
- Gate new entries with `_env_enabled` or `enabled: false` so you can stage rollout per profile without code edits.
- Keep OpenAPI specs and MCP commands free of secrets; inject env via registry metadata/env blocks instead of inline strings for auditability.

**Minimal OpenAPI registry fragment (example)**
```yaml
services:
  - name: weather__get_forecast
    enabled: true
    openapi: configs/openapi/weather.yaml
    timeouts:
      request_ms: 5000
      overall_ms: 15000
    retry:
      max_attempts: 2
    metadata:
      sandbox: py-slim
      notes: "Read-only; idempotent"
```

**Minimal MCP server entry (example)**
```yaml
mcpServers:
  - name: files__list_logs
    enabled: true
    transport: stdio
    command: ["python", "-m", "mcp_foundation.servers.files", "--root", "/workdir/logs"]
    timeouts:
      start_ms: 5000
      request_ms: 8000
    on_failure: "tool unavailable"
    metadata:
      sandbox: py-slim
      workdir: /workdir
```
Keep names descriptive (`<domain>__<action>`), mark side effects in `notes`, and avoid embedding secrets. If you need envs, pass them via the registry entry, not inline code.

**MCP transport and resiliency tips**
- Prefer `stdio` transport locally to avoid HTTP/SSE instability; specify explicit `command` arrays and allowed command prefixes.
- Set `start_ms`/`request_ms` timeouts, `retry` counts, and `on_failure` messages so repeated failures surface as “tool unavailable” instead of crashes.
- Pair registry timeouts with circuit breakers (Section 5) and use the lifecycle manager to pool/clean child processes; emit structured logs for start/stop/error to aid postmortems.

## 4. Plugin quality bars
- **OpenAPI tools:** Provide a valid spec, avoid embedded secrets, and set explicit timeouts/retries (e.g., request 5000ms, overall 15000ms, retries ≤ 2). Prefer idempotent mutations.
- **MCP servers:** Prefer `stdio` transport locally, set timeouts and failure messages that degrade gracefully ("tool unavailable" instead of crashes), and isolate working directories intentionally.

**Lifecycle guidance**
- Add new tools behind `_env_enabled` or `enabled: false` flags first, then turn them on per profile after smoke tests.
- Keep execution sandboxes pinned via registry metadata (`sandbox: py-slim` / `workdir: /workdir`) so tools cannot write outside expected paths.
- For MCP processes, set `on_failure` text to guide graceful degradation; pair with circuit breakers (below) to avoid thrash.

**Tool naming and Langflow visibility**
- Use `<domain>__<action>` names and human-readable `label`/`description` fields so Langflow nodes surface cleanly.
- Annotate side effects in `notes` (e.g., “writes file”, “mutates DB”) and expose `dry_run`/read-only variants where possible.
- Keep registry metadata consistent across MCP/OpenAPI entries so Langflow templating can reuse the same naming and sandbox hints.

## 5. Graceful failure and budgeting
Use bounded retries and circuit breakers to prevent UI hangs or Langflow freezes. Minimal TOML pattern:
```toml
[circuit_breakers.<tool_name>]
failure_threshold = 5
reset_timeout_seconds = 120
```
The default budget/redaction guardrails (see `AGENTS.md`) should remain enabled; adjust via registry entries rather than inline code changes.

**Incremental rollout pattern**
1. Enable the tool in the registry with conservative timeouts/retries.
2. Set the circuit breaker to skip the tool after repeated failures.
3. Run the stability smoke suite (Section 8).
4. Only after passing, expose the tool to Langflow users via the agent API; do not wire tools directly inside Langflow nodes.

## 6. Sandbox defaults
Run tools in sandboxed profiles by default to block unsafe code execution.
```toml
[sandbox]
enabled = true
engine = "docker"
```
For browser automation, use a dedicated Chrome profile (e.g., `MAC_USER_DATA_PATH=~/Library/Application Support/Google/Chrome/AgentS`) to avoid personal cookies and improve determinism.

**Filesystem hygiene**
- Mount only the paths a tool needs (logs, cache, or a dedicated `/workdir`), keep mounts read-only unless a write is required, and document any write paths in the registry notes.
- Disallow network egress unless a tool explicitly requires it; prefer local fixtures during stability testing.

**Compliance posture**
- Keep sandboxing enabled by default, enforce env-only secrets, and restrict dynamic imports to vetted namespaces (see `AGENTS.md`).
- Ensure registry metadata records sandbox profile, mounts, and notes for any write paths to support ISO/IEC 42001 evidence.
- Run with network egress disabled unless explicitly allowed per tool and document those exceptions for audits.

## 7. Logging and traceability
Ensure structured logs carry `trace_id`, planned steps, executed steps, tool outcomes, and redacted fields. You should be able to answer "what happened?" from logs alone without inspecting runtime state.

**What to look for**
- Planner decisions include ordered tool selections and why other tools were skipped.
- Worker execution logs include the registry entry used, sandbox info, timeouts, retries, and circuit-breaker status.
- Redaction applied to values matching `secret|token|password` keys per `AGENTS.md` guidance.

## 8. Stability tests
Run the stability harness before wiring Langflow:
```bash
python run_stability_tests.py --suite basic_openapi,mcp_smoke --retries 2
```
Add OpenAPI timeout tests, MCP process-kill tests, and UI selector failure tests as needed; failures must be clear and non-hanging.

## 9. Langflow readiness (after stability)
Expose the agent over HTTP and let Langflow call the agent API (not tools directly). Provide a sample flow JSON and keep secrets server-side; avoid storing secrets in Langflow nodes. Use the registry to surface tools so Langflow can recognize MCP/OpenAPI nodes without code edits.

**Langflow templating pattern**
- Publish flows via registry-backed templates (e.g., `langflow_<project>` entries) rather than wiring tools directly inside Langflow components.
- Keep secrets/config on the agent side; Langflow should invoke the agent endpoint with profile selection, not individual tools.
- When adding new MCP/OpenAPI tools, rely on registry naming/labels so Langflow nodes stay aligned without front-end refactors.

## 10. Go/no-go checklist
- `cuga start demo` succeeds without prompts or crashes.
- Registry lists OpenAPI + MCP tools and they respond.
- Tool failures degrade gracefully (bounded retries + circuit breakers).
- Sandbox blocks unsafe code by default; network egress is explicit.
- Logs explain decisions and tool outcomes.
- Stability tests pass twice in a row.
- Langflow can call the agent API without embedding secrets.

Keeping these steps in order prevents overlapping failure modes and makes plugin additions safer and more auditable.
