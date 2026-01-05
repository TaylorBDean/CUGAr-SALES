<div align="center">
  <img src="docs/image/CUGAr.png" alt="CUGAr Logo" width="400"/>
</div>

# ✅ Production Readiness Checklist – v1.0.0

**Current Status**: **98% Production Ready** (updated 2026-01-04)

**Latest Achievement**: ✅ **100% AGENTS.md Compliance** - All backend orchestrator components implemented, tested, and validated (10/10 tests passing, zero warnings).

This checklist ensures the CUGAR Agent system is hardened, documented, and version-controlled for production release.

---

## � Python Version Support

- **Supported Python Versions**: `>=3.10, <3.14`
- **Tested Versions**: 3.10, 3.11, 3.12, 3.13
- **Recommended for Production**: Python 3.11 or 3.12
- **Version Enforcement**: Defined in `pyproject.toml` `requires-python` field
- **CI Matrix**: GitHub Actions tests across Python 3.10–3.12 on every push/PR

### Version-Specific Notes
- **Python 3.10**: Minimum supported version (union types, match statements)
- **Python 3.11**: Recommended (performance improvements, better error messages)
- **Python 3.12**: Fully supported (improved typing, faster execution)
- **Python 3.13**: Supported with latest dependencies
- **Python 3.14+**: Not yet supported (dependency constraints)

---

## 🏗️ Minimum Infrastructure Requirements

### Container Orchestration
- **Kubernetes**: v1.24+ (required for production deployments)
  - Minimum 3 worker nodes
  - Resource quotas per namespace
  - Pod security policies enforced
  - Network policies for service isolation
  - Persistent volume claims for stateful components

### Required Services
- **PostgreSQL**: v14+ for persistent storage
  - Minimum 2 cores, 4GB RAM
  - Replication enabled (primary + 1 replica minimum)
  - Regular backups configured (see Disaster Recovery)
  
- **Redis**: v7.0+ for caching and session management
  - Minimum 1 core, 2GB RAM
  - Persistence enabled (AOF + RDB)
  - Replication for high availability
  
- **Message Queue** (optional but recommended): RabbitMQ or Kafka
  - For async task processing
  - Minimum 2 cores, 4GB RAM

### Browser Automation Infrastructure
- **Headless Chromium**: Required for web automation tasks
  - Installed via Playwright: `uv run playwright install --with-deps chromium`
  - Container image: `mcr.microsoft.com/playwright:v1.49.0-jammy`
  - Minimum 2 cores, 4GB RAM per browser instance
  - Sandboxed execution environment
  
- **Playwright**: v1.49.0 (pinned in `pyproject.toml`)
  - System dependencies automatically installed
  - Supports headless and headed modes
  - Screenshot and PDF generation capabilities
  - Network interception and request mocking

### Resource Recommendations (per agent instance)
- **CPU**: Minimum 2 cores, Recommended 4 cores
- **Memory**: Minimum 4GB, Recommended 8GB
- **Disk**: Minimum 20GB, Recommended 50GB (includes model cache, logs, temp files)
- **Network**: Low latency to model APIs (<100ms recommended)

### Scalability Considerations
- Horizontal scaling supported via replica count
- Load balancer required for multi-instance deployments
- Shared storage for tool registry cache and embeddings
- Session affinity recommended for stateful workflows

---

## 💰 Default Budgets, Quotas & Approval Gates

### Budget Configuration
- **`AGENT_BUDGET_CEILING`**: Default `100` cost units per task
  - Tracks cumulative tool execution costs
  - Enforced before tool execution begins
  - Configurable per profile/tenant in `configurations/profiles/`

- **`AGENT_ESCALATION_MAX`**: Default `2` escalations allowed
  - Escalations triggered when budget warnings occur
  - Each escalation requires approval (if HITL enabled)
  - After max escalations, tasks are blocked or require admin approval

- **`AGENT_BUDGET_POLICY`**: Default `warn` (options: `warn`, `block`)
  - `warn`: Log budget exceedance and emit observability event, allow continuation
  - `block`: Hard stop execution when budget ceiling is reached

### Tool Cost Examples
| Tool Category | Cost per Call | Latency Weight |
|--------------|---------------|----------------|
| Filesystem Read | 1.0 | 1.0 |
| Web Search | 5.0 | 2.5 |
| Code Execution | 3.0 | 1.5 |
| LLM Call (small) | 10.0 | 3.0 |
| LLM Call (large) | 50.0 | 5.0 |
| Database Query | 2.0 | 1.2 |

### Approval Gate Mechanisms

#### Human-in-the-Loop (HITL) Approval
- **Trigger Conditions**:
  - High-impact operations (write, delete, modify)
  - Budget escalations beyond threshold
  - Access to sensitive scopes (exec, db, finance)
  - Tool combinations flagged as risky

- **Approval Flow**:
  1. Agent emits `approval_requested` event with operation details
  2. Notification sent to configured approvers (Slack, email, webhook)
  3. Approver reviews operation context and trace_id
  4. Approval decision recorded in audit trail
  5. Agent proceeds or rejects based on decision

- **Approval Timeout**:
  - Default: 5 minutes for operations, 10 minutes for budget escalations
  - Fallback action: `reject` (configurable to `allow` in dev profiles)

- **Approver Roles** (defined in `routing/guards.yaml`):
  - `operator`: Day-to-day operations
  - `admin`: System-level changes
  - `finance_admin`: Budget escalations
  - `platform_admin`: Infrastructure changes

#### Human-in-the-Oven (HITO) Time Delays
- **Purpose**: Automatic delay before high-risk operations execute
- **Default Delay**: 30 seconds for budget warnings
- **Use Case**: Allows monitoring systems to raise alerts before action completes
- **Auto-Approval**: Configurable (default: `false`, requires explicit approval)

### Quota Enforcement
- **Request Rate Limiting**: 100 requests/minute per user (default)
- **Concurrent Executions**: Max 5 concurrent tasks per agent instance
- **Token Limits**: Model-specific (e.g., GPT-4: 128k context, output capped at 4k)
- **Disk Quota**: 1GB per user workspace
- **Memory Quota**: 512MB per tool execution sandbox

### Budget Observability
- **Golden Signals**:
  - `budget_utilization`: % of ceiling used per task
  - `budget_warnings_total`: Count of warnings emitted
  - `budget_exceeded_total`: Count of hard blocks
  - `approval_wait_time`: P50/P95/P99 latency for human approvals

- **Prometheus Metrics**:
  ```
  cuga_budget_warnings_total{profile="production",policy="allowlist_hitl"}
  cuga_budget_exceeded_total{profile="production",policy="allowlist_only"}
  cuga_approval_requests_total{approver_role="operator",status="approved"}
  cuga_approval_wait_ms{percentile="p95"}
  ```

- **Alerts** (example Prometheus rules):
  ```yaml
  - alert: HighBudgetUtilization
    expr: cuga_budget_utilization > 0.9
    for: 5m
    annotations:
      summary: "Budget utilization above 90% for {{ $labels.profile }}"
  
  - alert: ApprovalQueueBacklog
    expr: cuga_approval_requests_total{status="pending"} > 10
    for: 2m
    annotations:
      summary: "Approval queue has {{ $value }} pending requests"
  ```

---

## 🔄 Disaster Recovery

### Backup Strategy

#### PostgreSQL (Persistent State)
- **What to Back Up**:
  - User conversation history
  - Memory embeddings metadata
  - Audit trail logs
  - Agent configuration snapshots

- **Backup Frequency**:
  - Full backup: Daily at 02:00 UTC
  - Incremental backup: Every 6 hours
  - Transaction logs: Continuous (WAL archiving)

- **Backup Procedure**:
  ```bash
  # Full backup with pg_dump
  pg_dump -h $POSTGRES_HOST -U $POSTGRES_USER -F c -f backup_$(date +%Y%m%d).dump cuga_db
  
  # Incremental with WAL archiving
  # Configure in postgresql.conf:
  # wal_level = replica
  # archive_mode = on
  # archive_command = 'cp %p /backup/wal_archive/%f'
  ```

- **Retention Policy**:
  - Daily backups: 30 days
  - Weekly backups: 90 days
  - Monthly backups: 1 year

#### Redis (Cache & Session State)
- **What to Back Up**:
  - Session tokens and state
  - Tool registry cache
  - Rate limiting counters
  - Temporary computation results

- **Backup Frequency**:
  - RDB snapshots: Every hour
  - AOF persistence: Enabled with `everysec` fsync policy

- **Backup Procedure**:
  ```bash
  # Trigger manual RDB snapshot
  redis-cli -h $REDIS_HOST BGSAVE
  
  # Copy RDB and AOF files
  cp /var/lib/redis/dump.rdb /backup/redis/dump_$(date +%Y%m%d_%H%M).rdb
  cp /var/lib/redis/appendonly.aof /backup/redis/appendonly_$(date +%Y%m%d_%H%M).aof
  ```

- **Retention Policy**:
  - Hourly snapshots: 48 hours
  - Daily snapshots: 7 days
  - No long-term retention (cache is ephemeral)

#### Tool Registry Cache
- **What to Back Up**:
  - `docs/mcp/registry.yaml` (canonical source)
  - Compiled registry indexes
  - Tool capability metadata
  - Sandbox policy configurations

- **Backup Frequency**:
  - On every registry update (version controlled)
  - Automated snapshots: Daily

- **Backup Procedure**:
  ```bash
  # Version-controlled backup (primary method)
  git commit -m "registry: update tool definitions" docs/mcp/registry.yaml
  git push origin main
  
  # Filesystem backup (secondary)
  tar -czf registry_backup_$(date +%Y%m%d).tar.gz docs/mcp/registry.yaml config/ configurations/
  ```

#### Embeddings and Vector Stores
- **What to Back Up**:
  - Memory embeddings (Milvus/FAISS/Chroma collections)
  - User conversation vectors
  - RAG knowledge base indexes

- **Backup Frequency**:
  - Incremental: Every 12 hours
  - Full snapshot: Weekly

- **Backup Procedure** (example for Milvus):
  ```bash
  # Milvus backup via API
  curl -X POST "http://milvus:9091/api/v1/backup/create" \
    -d '{"collection_name":"user_memory","backup_name":"mem_$(date +%Y%m%d)"}'
  ```

### Restore Procedures

#### PostgreSQL Restore
```bash
# Stop dependent services
kubectl scale deployment cuga-agent --replicas=0

# Restore from backup
pg_restore -h $POSTGRES_HOST -U $POSTGRES_USER -d cuga_db -c backup_20260101.dump

# Verify data integrity
psql -h $POSTGRES_HOST -U $POSTGRES_USER -d cuga_db -c "SELECT COUNT(*) FROM conversations;"

# Restart services
kubectl scale deployment cuga-agent --replicas=3
```

#### Redis Restore
```bash
# Stop Redis
kubectl scale statefulset redis --replicas=0

# Replace RDB/AOF files
kubectl cp dump_20260101_0200.rdb redis-0:/data/dump.rdb
kubectl cp appendonly_20260101_0200.aof redis-0:/data/appendonly.aof

# Restart Redis
kubectl scale statefulset redis --replicas=1

# Verify cache
redis-cli -h redis PING
```

#### Tool Registry Restore
```bash
# Restore from git (preferred)
git checkout v1.0.0  # or specific commit
git pull origin main

# Or restore from filesystem backup
tar -xzf registry_backup_20260101.tar.gz -C /

# Reload registry in running agents (if hot-reload supported)
curl -X POST http://cuga-agent:8000/api/v1/registry/reload
```

### Recovery Time Objectives (RTO) & Recovery Point Objectives (RPO)

| Component | RTO | RPO | Priority |
|-----------|-----|-----|----------|
| PostgreSQL | < 1 hour | < 6 hours | Critical |
| Redis | < 15 minutes | < 1 hour | High |
| Tool Registry | < 5 minutes | 0 (version controlled) | Critical |
| Embeddings | < 2 hours | < 12 hours | Medium |
| Application Pods | < 10 minutes | 0 (stateless) | High |

### Disaster Scenarios & Runbooks

#### Scenario 1: Database Corruption
1. Stop all agent instances
2. Restore PostgreSQL from most recent clean backup
3. Replay WAL logs up to corruption point
4. Run integrity checks (`pg_verify`)
5. Restart agents and verify operation

#### Scenario 2: Registry Desync
1. Identify discrepancy via `scripts/verify_guardrails.py`
2. Restore canonical registry from git history
3. Regenerate `docs/mcp/tiers.md` via `build/gen_tiers_table.py`
4. Hot-reload registry in agents (or rolling restart)
5. Verify tool resolution via test queries

#### Scenario 3: Complete Cluster Failure
1. Provision new K8s cluster
2. Restore PostgreSQL from off-site backup
3. Restore Redis snapshots (optional, can rebuild cache)
4. Deploy agent manifests via Helm/Kustomize
5. Restore tool registry from git
6. Verify all health checks pass
7. Resume traffic via DNS/load balancer update

### Monitoring & Alerting for DR
- **Backup Health Checks**:
  - `backup_success_total` metric per component
  - Alert if no successful backup in 25 hours (daily + margin)

- **Replication Lag**:
  - PostgreSQL: `pg_stat_replication.replay_lag < 1 minute`
  - Redis: `info replication | grep lag` < 5 seconds

- **Backup Size Anomalies**:
  - Alert if backup size deviates >20% from 7-day average
  - May indicate data corruption or schema changes

---

## �📁 Repository Structure

- [x] `/src/` has modular structure (`agents`, `mcp`, `tools`, `config`)
- [x] `/docs/` contains architecture, security, integration, and tooling references
- [x] `/config/` stores Hydra-composed registry defaults and fragment overrides with inheritance markers
- [x] `/tests/` directory exists with core coverage
- [x] `/examples/` directory demonstrates agent usage

---

## 🔐 Security & Secrets

- [x] `.env.example` included and redacted
- [x] `USE_EMBEDDED_ASSETS` feature flag documented
- [x] Watsonx Granite provider validates env-based credentials (`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`) with deterministic defaults and audit logging.
- [x] No hardcoded keys or tokens
- [x] Secrets validated before use (`assert key`)
- [x] `detect-secrets` baseline committed
- [x] `SECURITY.md` defines CI & runtime rules
- [x] **HTTP Client Hardening**: All HTTP requests use `SafeClient` wrapper with enforced timeouts (10.0s), automatic retry (4 attempts, exponential backoff), and URL redaction in logs. No raw httpx/requests/urllib usage.
- [x] **Secrets Management**: Env-only credential enforcement via `cuga.security.secrets` module. `.env.example` parity validated in CI (no missing keys). `SECRET_SCANNER=on` runs trufflehog + gitleaks on every push/PR. Hardcoded API keys/tokens/passwords trigger CI failure.
- [x] **Mode-Specific Validation**: Startup validation enforces required env vars per mode: LOCAL (model API key), SERVICE (AGENT_TOKEN + budget + model key), MCP (servers file + profile + model key), TEST (no requirements).

---

## 📦 Build & Distribution

- [x] `Makefile` and `Dockerfile` tested
- [x] `uv` workflows for stability & asset builds
- [x] Embedded asset pipeline (`build_embedded.py`) verified
- [x] Compression ratios documented

---

## 🔍 Documentation Map

- [x] `AGENTS.md` – entrypoint for all contributors
- [x] `AGENT-CORE.md` – agent lifecycle, pipeline
- [x] `TOOLS.md` – structure, schema, usage
- [x] `MCP_INTEGRATION.md` – tool bus and lifecycle
- [x] `REGISTRY_MERGE.md` – Hydra-based registry fragment handling and enablement rules
- [x] `SECURITY.md` – production secret handling
- [x] `EMBEDDED_ASSETS.md` – compression and distribution

---

## 🛡️ Guardrails & Registry

- [x] Registry entries declare sandbox profile (`py/node slim|full`, `orchestrator`) with `/workdir` pinning for exec scopes and read-only defaults.
- [x] Budget and observability env keys (`AGENT_*`, `OTEL_*`, `LANGFUSE_*`, `OPENINFERENCE_*`, `TRACELOOP_*`) wired with default `warn` budget policy and ceiling/escalation caps.
- [x] `docs/mcp/registry.yaml` kept in sync with generated `docs/mcp/tiers.md`; hot-swap reload path tested and deterministic ordering verified.
- [x] Guardrail updates accompanied by README/CHANGELOG/todo1 updates and `scripts/verify_guardrails.py --base <ref>` runs.

---

## 🧪 Tests & Stability

- [x] Core modules tested (`controller`, `planner`, `executor`)
- [x] `run_stability_tests.py` executed cleanly
- [ ] Functional test coverage ≥ 80% orchestrator & routing, ≥ 60% tools/memory (📍 target, see TESTING.md)
- [x] Lint passes (`ruff`, `pre-commit`, CI)
- [x] Legacy agent versions isolated or removed

---

## 🏷️ Versioning

- [x] `VERSION.txt` present → `1.0.0`
- [x] `CHANGELOG.md` documents all v1.0.0 features
- [x] Git tag proposed:
  ```bash
  git tag -a v1.0.0 -m "Initial production release"
  git push origin v1.0.0
  ```

- [x] `/src/` has modular structure (`agents`, `mcp`, `tools`, `config`)
- [x] `/docs/` contains architecture, security, integration, and tooling references
- [x] `/config/` stores Hydra-composed registry defaults and fragment overrides with inheritance markers
- [x] `/tests/` directory exists with core coverage
- [x] `/examples/` directory demonstrates agent usage

---

## 🚀 Deployment & Rollback Procedures

### Container Image Pinning Policy

Per AGENTS.md § Registry Hygiene: **No `:latest` tags in production**.

- **Enforcement**: CI checks block `:latest` tags in `ops/docker-compose.proposed.yaml`
- **Pinning Strategy**: 
  - Use semantic versioning tags (e.g., `v0.2.0`, `v1.0.0`)
  - Pin to specific digests after validation: `image@sha256:abc123...`
- **Current Pinned Versions**:
  - `cuga/orchestrator:v0.2.0`
  - `fastmcp/filesystem:v1.0.0`
  - `fastmcp/git:v2.0.0`
  - `fastmcp/browser:v1.0.0`
  - `otel/opentelemetry-collector:0.91.0`
  - `qdrant/qdrant:v1.7.0`
  - `ollama/ollama:0.1.17`

### Kubernetes Deployment

All K8s manifests located in `ops/k8s/`:
- `namespace.yaml`: Namespace, quotas, resource limits, PVCs
- `orchestrator-deployment.yaml`: Orchestrator with health checks, HPA, resource limits
- `mcp-services-deployment.yaml`: MCP Tier 1 & Tier 2 services
- `configmaps.yaml`: Config data (settings, registry, OTEL collector config)
- `secrets.yaml`: Secret templates (DO NOT commit actual secrets)
- `README.md`: Complete deployment guide

**Quick Deploy**:
```bash
cd ops/k8s/
kubectl apply -f namespace.yaml
kubectl apply -f configmaps.yaml
kubectl create secret generic cuga-orchestrator-secrets \
  --from-env-file=../env/orchestrator.env --namespace=cugar
kubectl apply -f orchestrator-deployment.yaml
kubectl apply -f mcp-services-deployment.yaml
```

### Rolling Update (Zero Downtime)

Orchestrator deployment uses `RollingUpdate` strategy with `maxUnavailable: 0`:

```bash
# Update to new version
kubectl set image deployment/cuga-orchestrator -n cugar \
  orchestrator=cuga/orchestrator:v0.3.0

# Watch rollout progress
kubectl rollout status deployment/cuga-orchestrator -n cugar

# Monitor health during rollout
watch kubectl get pods -n cugar -l app=cuga-orchestrator
```

**Health Check Gates**:
- **Startup Probe**: 60s grace period for initialization
- **Readiness Probe**: Pod must pass `/health` check before receiving traffic
- **Liveness Probe**: Pod restarted if `/health` fails after 3 attempts (30s interval)

### Rollback Procedures

#### Kubernetes Rollback

**Fast Rollback (Automated)**:
```bash
# Rollback to previous version (takes ~30s)
kubectl rollout undo deployment/cuga-orchestrator -n cugar

# Verify rollback
kubectl rollout status deployment/cuga-orchestrator -n cugar
kubectl get pods -n cugar -l app=cuga-orchestrator -o wide
```

**Rollback to Specific Revision**:
```bash
# View deployment history
kubectl rollout history deployment/cuga-orchestrator -n cugar

# Rollback to revision N
kubectl rollout undo deployment/cuga-orchestrator -n cugar --to-revision=3
```

**Rollback Verification**:
```bash
# Check logs for errors
kubectl logs -n cugar deploy/cuga-orchestrator --tail=50

# Test health endpoint
kubectl exec -n cugar deploy/cuga-orchestrator -- curl http://localhost:8000/health

# Check metrics
kubectl exec -n cugar deploy/cuga-orchestrator -- curl http://localhost:8000/metrics | grep cuga_requests_total
```

#### Docker Compose Rollback

**Fast Rollback**:
```bash
cd ops/
# Revert docker-compose.proposed.yaml to previous version
git checkout HEAD~1 -- docker-compose.proposed.yaml

# Restart services
docker-compose -f docker-compose.proposed.yaml down
docker-compose -f docker-compose.proposed.yaml up -d

# Verify health
docker-compose -f docker-compose.proposed.yaml ps
curl -f http://localhost:8000/health
```

### Config Rollback

**Registry Changes** (tool additions/removals):
```bash
# Rollback registry.yaml
git checkout HEAD~1 -- docs/mcp/registry.yaml

# Reload registry without restart (if hot-reload enabled)
curl -X POST http://localhost:8000/admin/registry/reload \
  -H "Authorization: Bearer ${AGENT_TOKEN}"

# Or restart orchestrator to pick up changes
kubectl rollout restart deployment/cuga-orchestrator -n cugar
```

**ConfigMap Changes**:
```bash
# Rollback ConfigMap
kubectl rollout undo configmap/cuga-orchestrator-config -n cugar

# Restart pods to pick up new config
kubectl rollout restart deployment/cuga-orchestrator -n cugar
```

### Disaster Recovery Failover

**Multi-Region Failover** (if secondary region deployed):
```bash
# Switch DNS/load balancer to secondary region
# (Implementation depends on infrastructure: Route53, CloudFlare, etc.)

# Verify secondary is healthy
kubectl config use-context prod-us-east-1
kubectl get pods -n cugar -l app=cuga-orchestrator
kubectl logs -n cugar deploy/cuga-orchestrator --tail=20

# Scale up secondary (if in standby mode)
kubectl scale deployment cuga-orchestrator -n cugar --replicas=2
```

**Database Failover** (PostgreSQL):
```bash
# Promote replica to primary
pg_ctl promote -D /var/lib/postgresql/data

# Update app config to point to new primary
kubectl set env deployment/cuga-orchestrator -n cugar \
  POSTGRES_HOST=new-primary-host

# Restart pods
kubectl rollout restart deployment/cuga-orchestrator -n cugar
```

### Rollback Decision Matrix

| Failure Type | Rollback Method | Time to Recover | Data Loss Risk |
|--------------|-----------------|-----------------|----------------|
| Bad container image | K8s rollback | ~30s | None (stateless) |
| Registry config error | Git revert + reload | ~10s | None |
| Database migration failure | Restore from backup | ~5min | Depends on backup age |
| Network policy change | Revert YAML + kubectl apply | ~15s | None |
| Secret rotation issue | Restore old secret | ~30s | None |
| Multi-service failure | Full environment restore | ~10min | Depends on backup |

### Rollback Testing

**Pre-Deploy Validation**:
```bash
# Test in staging environment first
kubectl config use-context staging
kubectl apply -f ops/k8s/

# Run smoke tests
./tests/smoke/test_deployment.sh

# If passing, deploy to production
kubectl config use-context production
kubectl apply -f ops/k8s/
```

**Rollback Drills** (monthly):
```bash
# Deploy canary version
kubectl apply -f ops/k8s/orchestrator-canary.yaml

# Simulate failure and rollback
kubectl rollout undo deployment/cuga-orchestrator-canary -n cugar

# Document rollback time and issues
```

### Post-Rollback Actions

1. **Root Cause Analysis**: Document what went wrong in incident report
2. **Audit Trail Review**: Check observability events for failure patterns
3. **Update Tests**: Add regression tests to prevent recurrence
4. **Update Runbook**: Document new rollback scenarios
5. **Notify Stakeholders**: Send incident summary with resolution

### Rollout/Rollback Observability

**Golden Signals to Monitor**:
- `cuga_requests_total`: Should remain steady during rollout
- `cuga_success_rate`: Should not drop below 99% during rollout
- `cuga_latency_ms`: P95 should not spike >10% during rollout
- `cuga_tool_error_rate`: Should remain <1% during rollout

**Prometheus Alerts** (example):
```yaml
- alert: RolloutDegradedPerformance
  expr: cuga_success_rate < 0.99
  for: 2m
  annotations:
    summary: "Rollout causing degraded performance (success rate {{ $value }})"
    action: "Consider rollback: kubectl rollout undo deployment/cuga-orchestrator -n cugar"

- alert: RolloutLatencySpike
  expr: cuga_latency_ms{percentile="p95"} > 1.1 * cuga_latency_ms{percentile="p95"} offset 10m
  for: 3m
  annotations:
    summary: "Rollout causing P95 latency spike"
```

**Grafana Dashboard**: Import `observability/grafana_dashboard.json` for real-time rollout monitoring.

---

## 🔐 Security & Secrets

- [x] `.env.example` included and redacted
- [x] `USE_EMBEDDED_ASSETS` feature flag documented
- [x] Watsonx Granite provider validates env-based credentials (`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`) with deterministic defaults and audit logging.
- [x] No hardcoded keys or tokens
- [x] Secrets validated before use (`assert key`)
- [x] `detect-secrets` baseline committed
- [x] `SECURITY.md` defines CI & runtime rules
- [x] **HTTP Client Hardening**: All HTTP requests use `SafeClient` wrapper with enforced timeouts (10.0s), automatic retry (4 attempts, exponential backoff), and URL redaction in logs. No raw httpx/requests/urllib usage.
- [x] **Secrets Management**: Env-only credential enforcement via `cuga.security.secrets` module. `.env.example` parity validated in CI (no missing keys). `SECRET_SCANNER=on` runs trufflehog + gitleaks on every push/PR. Hardcoded API keys/tokens/passwords trigger CI failure.
- [x] **Mode-Specific Validation**: Startup validation enforces required env vars per mode: LOCAL (model API key), SERVICE (AGENT_TOKEN + budget + model key), MCP (servers file + profile + model key), TEST (no requirements).

---

## 📦 Build & Distribution

- [x] `Makefile` and `Dockerfile` tested
- [x] `uv` workflows for stability & asset builds
- [x] Embedded asset pipeline (`build_embedded.py`) verified
- [x] Compression ratios documented

---

## 🔍 Documentation Map

- [x] `AGENTS.md` – entrypoint for all contributors
- [x] `AGENT-CORE.md` – agent lifecycle, pipeline
- [x] `TOOLS.md` – structure, schema, usage
- [x] `MCP_INTEGRATION.md` – tool bus and lifecycle
- [x] `REGISTRY_MERGE.md` – Hydra-based registry fragment handling and enablement rules
- [x] `SECURITY.md` – production secret handling
- [x] `EMBEDDED_ASSETS.md` – compression and distribution

---

## 🛡️ Guardrails & Registry

- [x] Registry entries declare sandbox profile (`py/node slim|full`, `orchestrator`) with `/workdir` pinning for exec scopes and read-only defaults.
- [x] Budget and observability env keys (`AGENT_*`, `OTEL_*`, `LANGFUSE_*`, `OPENINFERENCE_*`, `TRACELOOP_*`) wired with default `warn` budget policy and ceiling/escalation caps.
- [x] `docs/mcp/registry.yaml` kept in sync with generated `docs/mcp/tiers.md`; hot-swap reload path tested and deterministic ordering verified.
- [x] Guardrail updates accompanied by README/CHANGELOG/todo1 updates and `scripts/verify_guardrails.py --base <ref>` runs.

---

## 🧪 Tests & Stability

- [x] Core modules tested (`controller`, `planner`, `executor`)
- [x] `run_stability_tests.py` executed cleanly
- [ ] Functional test coverage ≥ 80% (📍 target)
- [x] Lint passes (`ruff`, `pre-commit`, CI)
- [x] Legacy agent versions isolated or removed

---

## 🏷️ Versioning

- [x] `VERSION.txt` present → `1.0.0`
- [x] `CHANGELOG.md` documents all v1.0.0 features
- [x] Git tag proposed:
  ```bash
  git tag -a v1.0.0 -m "Initial production release"
  git push origin v1.0.0
