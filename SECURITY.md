# Security Policy

CUGAR Agent is sandbox-first. Examples and demos are not production hardened; keep secrets and customer data out of the repository and demos.

## Reporting a Vulnerability
- Email: [security@cuga.dev](mailto:security@cuga.dev)
- Include repro steps, impact, affected version/commit, and any mitigations you tested.
- Do not include credentials or PII. If sensitive artifacts are required, request a secure channel first.
- We aim to acknowledge reports within 72 hours and provide a fix or mitigation timeline within 7 business days.

## Supported Versions
- Active development targets `main`.
- Released tags receive fixes on a best-effort basis; note the tag in your report so we can triage impact.

## Safe Handling Guidelines
- Run agents/MCP servers in sandboxed environments with locked-down network egress by default.
- Configure secrets through environment variables or `.env.mcp`, never in code or committed files.
- Use `python scripts/verify_guardrails.py` and CI workflows to validate routing markers, registry hygiene, and audit/trace settings before shipping.
- Enable observability with redaction when using Langfuse/OpenInference; avoid exporting raw prompts containing sensitive data.
- Restrict dynamic imports to vetted namespaces (`cuga.modular.tools.*`) and ensure VectorMemory metadata carries `profile` for isolation.

## Security Model

### 1. Sandbox Deny-by-Default
All tool execution runs in isolated sandboxes with deny-by-default policies:
- **Filesystem**: Tools cannot write outside `/workdir` (pinned per execution scope); read-only mounts by default
- **Network**: Deny external network access unless explicitly allowed by profile; localhost/private networks blocked
- **Process**: No spawning daemons, no `eval`/`exec` (routed through AST-based `safe_eval_expression()` and `SafeCodeExecutor`)
- **Imports**: Restrict dynamic imports to `cuga.modular.tools.*` allowlist; deny relative/absolute paths outside namespace
- **Resource**: Memory/CPU limits enforced per tool execution; timeout enforcement (10s default, configurable)

**Enforcement**: Registry entries MUST declare sandbox profile (`py/node slim|full`, `orchestrator`) with explicit mount declarations. See `registry.yaml` and `docs/mcp/registry.yaml`.

### 2. Parameter Schema Validation
All tool parameters validated against Pydantic schemas before execution:
- **Type Checking**: String/integer/float/boolean/enum validation with explicit type coercion
- **Range Validation**: Min/max for numeric types, min_length/max_length for strings, pattern regex for strings
- **Required Fields**: Explicit `required: true|false` per parameter; reject unknown fields in strict mode
- **Enum Validation**: Allowlist valid values (e.g., `mode: ["overwrite", "append"]`)
- **Nested Schemas**: Support nested objects with recursive validation

**Example** (from `src/cuga/backend/guardrails/policy.py`):
```yaml
parameter_schemas:
  filesystem_write:
    path:
      type: string
      required: true
      pattern: "^[a-zA-Z0-9/_\\-\\.]+$"  # No path traversal
    content:
      type: string
      required: true
      max_length: 1048576  # 1MB limit
```

### 3. Network Egress Allowlist
Network I/O restricted to explicit allowlist per profile:
- **Allowed Domains**: Exact match or wildcard subdomain (e.g., `api.openai.com`, `*.github.com`)
- **Blocked Localhost**: Reject `127.0.0.1`, `localhost`, `::1` (prevent SSRF)
- **Blocked Private Networks**: Reject RFC1918 ranges (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- **IP Ranges**: Optional CIDR allowlist for specific services (e.g., `8.8.8.8/32` for DNS health checks)
- **HTTP Client**: All HTTP requests routed through `SafeClient` with enforced timeouts (10s read, 5s connect), automatic retry (4 attempts, exponential backoff), URL redaction in logs

**Enforcement**: Tools MUST use `cuga.security.http_client.SafeClient` for HTTP requests. Raw `httpx`/`requests` calls rejected by CI.

### 4. PII Redaction in Events/Logs
Sensitive data automatically redacted before emission:
- **Redacted Keys**: `secret`, `token`, `password`, `api_key`, `credential`, `auth`, `authorization`, `bearer`
- **Recursive Redaction**: Applies to nested dicts in event attributes, metadata, error messages
- **Structured Events**: All observability events (`StructuredEvent`, `ToolCallEvent`, `BudgetEvent`, `ApprovalEvent`) auto-redact before export
- **Log Sanitization**: Structured logs redact secrets via `cuga.security.secrets.redact_dict()` before emission
- **URL Redaction**: Query params and credentials stripped from URLs in HTTP client logs

**Example**:
```python
# Before redaction
event = {"api_key": "sk-abc123", "user": "alice"}
# After redaction
event = {"api_key": "***REDACTED***", "user": "alice"}
```

### 5. Approval Workflows (Human-in-the-Loop)
High-risk operations require explicit approval before execution:
- **Approval Gates**: WRITE/DELETE/FINANCIAL/EXTERNAL actions trigger approval requests
- **Timeout-Bounded**: Approval requests expire after 120s-600s (configurable per action type)
- **Fallback Action**: Reject by default on timeout (configurable to allow in dev profiles)
- **Approval Lifecycle**: PENDING → APPROVED/REJECTED/EXPIRED with atomic state transitions
- **Audit Trail**: All approval decisions recorded with reasoning, alternatives, timestamp

**Trigger Conditions**:
- High-impact operations (write, delete, modify)
- Budget escalations beyond threshold
- Access to sensitive scopes (exec, db, finance)
- Tool combinations flagged as risky

**Implementation**: See `src/cuga/backend/guardrails/policy.py` (`request_approval()`) and `src/cuga/security/governance.py` (`GovernanceEngine.request_approval()`).

### 6. Secret Management
Credentials loaded from environment only; no hardcoded secrets:
- **Env-Only**: All secrets MUST be loaded from environment variables (e.g., `OPENAI_API_KEY`, `LANGFUSE_SECRET`)
- **No Hardcoding**: CI fails on hardcoded API keys/tokens/passwords (trufflehog + gitleaks scan)
- **`.env.example` Parity**: CI validates `.env.example` lists all required keys (no missing vars)
- **Per-Mode Validation**: Secrets validated per execution mode (local/service/mcp/test) with helpful error messages
- **Redaction on Load**: Secret values redacted in logs/errors immediately after loading via `cuga.security.secrets.redact_dict()`

**Enforcement**: 
- CI workflow `SECRET_SCANNER=on` runs trufflehog + gitleaks on every push/PR
- `.env.example` parity check fails CI if required keys missing
- See `src/cuga/security/secrets.py` for env validation and redaction
