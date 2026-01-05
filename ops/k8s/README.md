# Kubernetes Deployment Guide for CUGAr

This directory contains Kubernetes manifests for deploying CUGAr orchestrator and MCP services in production.

## Prerequisites

- Kubernetes 1.24+ cluster
- `kubectl` configured with cluster access
- Persistent storage provisioner (for PVCs)
- Optional: Sealed Secrets controller for encrypted secrets

## Quick Start

### 1. Create Namespace and RBAC

```bash
kubectl apply -f namespace.yaml
```

### 2. Create ConfigMaps

```bash
kubectl apply -f configmaps.yaml
```

### 3. Create Secrets

**WARNING**: `secrets.yaml` is a template with placeholder values. Create actual secrets from environment files:

```bash
# From env file
kubectl create secret generic cuga-orchestrator-secrets \
  --from-env-file=../env/orchestrator.env \
  --namespace=cugar

# Or from literal values (preferred for CI/CD)
kubectl create secret generic cuga-orchestrator-secrets \
  --from-literal=OPENAI_API_KEY='sk-...' \
  --from-literal=AGENT_TOKEN='token-...' \
  --namespace=cugar
```

### 4. Deploy Orchestrator

```bash
kubectl apply -f orchestrator-deployment.yaml
```

### 5. Deploy MCP Services

```bash
# Deploy all Tier 1 services (filesystem, git, browser-slim)
kubectl apply -f mcp-services-deployment.yaml
```

### 6. Verify Deployment

```bash
# Check pods
kubectl get pods -n cugar

# Check services
kubectl get svc -n cugar

# Check logs
kubectl logs -n cugar -l app=cuga-orchestrator --tail=50 -f

# Check health
kubectl exec -n cugar deploy/cuga-orchestrator -- curl -f http://localhost:8000/health
```

## Architecture

### Orchestrator
- **Replicas**: 2 (with HPA scaling to 10)
- **Resources**: 500m CPU (request) → 2000m CPU (limit), 1Gi RAM → 4Gi RAM
- **Health Checks**: Liveness (30s), Readiness (10s), Startup (60s)
- **Probes**: `/health` endpoint on port 8000
- **Metrics**: `/metrics` Prometheus endpoint on port 8000

### MCP Services (Tier 1)
- **mcp-filesystem**: File operations with read-only workspace
- **mcp-git**: Git operations with read-write repos volume
- **mcp-browser-slim**: Web browsing with node-slim profile

### MCP Services (Tier 2, Disabled by Default)
- **observability-collector**: OpenTelemetry collector (OTLP ingest)
- **vector-db**: Qdrant vector database (StatefulSet with 50Gi storage)
- **ollama**: Local LLM inference (100Gi storage for models)

## Configuration Precedence

Per AGENTS.md § Configuration Policy, configuration sources are resolved in this order:

1. **CLI args** (highest precedence, N/A for K8s)
2. **Environment variables** (from Secrets/ConfigMaps)
3. **ConfigMap data** (TOML/YAML configs)
4. **Hardcoded defaults** (lowest precedence)

### Overriding Configs

```bash
# Override via environment variable in deployment
kubectl set env deployment/cuga-orchestrator -n cugar \
  AGENT_BUDGET_CEILING=200 \
  AGENT_BUDGET_POLICY=block

# Or edit ConfigMap and restart
kubectl edit configmap cuga-orchestrator-config -n cugar
kubectl rollout restart deployment/cuga-orchestrator -n cugar
```

## Health Checks

All services include liveness, readiness, and startup probes:

- **Liveness**: Restarts pod if unhealthy
- **Readiness**: Removes from load balancer if not ready
- **Startup**: Allows slow initialization (60s for orchestrator)

Test manually:
```bash
kubectl exec -n cugar deploy/cuga-orchestrator -- curl http://localhost:8000/health
kubectl exec -n cugar deploy/cuga-orchestrator -- curl http://localhost:8000/metrics
```

## Resource Limits

Per AGENTS.md production readiness requirements:

| Service | CPU Request | CPU Limit | Memory Request | Memory Limit |
|---------|-------------|-----------|----------------|--------------|
| Orchestrator | 500m | 2000m | 1Gi | 4Gi |
| mcp-filesystem | 100m | 500m | 128Mi | 512Mi |
| mcp-git | 100m | 1000m | 256Mi | 1Gi |
| mcp-browser-slim | 200m | 2000m | 512Mi | 2Gi |
| observability | 100m | 1000m | 256Mi | 1Gi |
| vector-db | 500m | 4000m | 2Gi | 8Gi |
| ollama | 2000m | 8000m | 8Gi | 16Gi |

## Scaling

### Horizontal Pod Autoscaler (HPA)

Orchestrator automatically scales based on CPU/memory utilization:

```bash
# Check HPA status
kubectl get hpa -n cugar

# Override min/max replicas
kubectl patch hpa cuga-orchestrator -n cugar -p '{"spec":{"minReplicas":3,"maxReplicas":20}}'
```

### Manual Scaling

```bash
# Scale orchestrator
kubectl scale deployment cuga-orchestrator -n cugar --replicas=5

# Scale MCP services
kubectl scale deployment mcp-filesystem -n cugar --replicas=3
```

## Rollout & Rollback

### Rolling Update (Zero Downtime)

```bash
# Update image (example)
kubectl set image deployment/cuga-orchestrator -n cugar \
  orchestrator=cuga/orchestrator:v0.3.0

# Watch rollout
kubectl rollout status deployment/cuga-orchestrator -n cugar
```

### Rollback

```bash
# Rollback to previous version
kubectl rollout undo deployment/cuga-orchestrator -n cugar

# Rollback to specific revision
kubectl rollout history deployment/cuga-orchestrator -n cugar
kubectl rollout undo deployment/cuga-orchestrator -n cugar --to-revision=2
```

### Canary Deployment

Create separate deployment with new version, split traffic using Service/Ingress:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cuga-orchestrator-canary
spec:
  replicas: 1  # 10% of traffic
  selector:
    matchLabels:
      app: cuga-orchestrator
      version: v0.3.0-canary
```

## Monitoring & Observability

### Prometheus Metrics

Scrape `/metrics` endpoint from orchestrator:

```yaml
# Prometheus ServiceMonitor (if using Prometheus Operator)
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: cuga-orchestrator
  namespace: cugar
spec:
  selector:
    matchLabels:
      app: cuga-orchestrator
  endpoints:
  - port: metrics
    path: /metrics
    interval: 30s
```

### OTEL Integration

Orchestrator sends traces/metrics to observability-collector (Tier 2):

```bash
# Enable observability (deploy Tier 2)
kubectl apply -f mcp-services-deployment.yaml

# Check collector logs
kubectl logs -n cugar deploy/observability-collector -f
```

### Grafana Dashboard

Import dashboard from `observability/grafana_dashboard.json` (see PRODUCTION_READINESS.md).

## Disaster Recovery

### Backup

```bash
# Backup namespace resources
kubectl get all,cm,secret,pvc -n cugar -o yaml > cugar-backup-$(date +%Y%m%d).yaml

# Backup PVCs (using Velero)
velero backup create cugar-pvc --include-namespaces=cugar --include-resources=pvc,pv
```

### Restore

```bash
# Restore from backup
kubectl apply -f cugar-backup-20240101.yaml

# Restore PVCs (using Velero)
velero restore create --from-backup cugar-pvc
```

### Multi-Region DR

Deploy in secondary region with cross-region PVC replication:

```bash
# Primary: us-west-2
kubectl config use-context prod-us-west-2
kubectl apply -f .

# Secondary: us-east-1 (standby)
kubectl config use-context prod-us-east-1
kubectl apply -f .
kubectl scale deployment cuga-orchestrator -n cugar --replicas=0  # Standby mode
```

## Security

### Network Policies

```yaml
# Example: Restrict orchestrator egress to MCP services only
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: orchestrator-egress
  namespace: cugar
spec:
  podSelector:
    matchLabels:
      app: cuga-orchestrator
  policyTypes:
  - Egress
  egress:
  - to:
    - podSelector:
        matchLabels:
          tier: tier1
    ports:
    - protocol: TCP
      port: 8080
```

### Pod Security Standards

Apply baseline/restricted pod security:

```bash
kubectl label namespace cugar \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

### RBAC

ServiceAccount `cuga-orchestrator` has minimal permissions (defined in orchestrator-deployment.yaml).

## Troubleshooting

### Pod Crashes (CrashLoopBackOff)

```bash
# Check logs
kubectl logs -n cugar deploy/cuga-orchestrator --previous

# Check events
kubectl describe pod -n cugar -l app=cuga-orchestrator

# Check secrets
kubectl get secret cuga-orchestrator-secrets -n cugar -o jsonpath='{.data}' | jq 'keys'
```

### Health Check Failures

```bash
# Test health endpoint
kubectl exec -n cugar deploy/cuga-orchestrator -- curl -v http://localhost:8000/health

# Check readiness
kubectl get pods -n cugar -l app=cuga-orchestrator -o wide
```

### Resource Exhaustion

```bash
# Check resource usage
kubectl top pods -n cugar
kubectl top nodes

# Check HPA
kubectl describe hpa cuga-orchestrator -n cugar
```

### Missing Secrets

```bash
# Verify secrets exist
kubectl get secrets -n cugar

# Check secret data (keys only, values redacted)
kubectl describe secret cuga-orchestrator-secrets -n cugar
```

## Cost Optimization

### Right-Sizing Resources

```bash
# Get resource usage over time
kubectl top pods -n cugar --containers

# Adjust requests/limits based on actual usage
kubectl set resources deployment/cuga-orchestrator -n cugar \
  --requests=cpu=300m,memory=800Mi \
  --limits=cpu=1500m,memory=3Gi
```

### Disable Tier 2 Services

```bash
# Scale down observability/vector-db/ollama
kubectl scale deployment observability-collector -n cugar --replicas=0
kubectl scale statefulset vector-db -n cugar --replicas=0
kubectl scale deployment ollama -n cugar --replicas=0
```

### Spot Instances (AWS/GCP)

Add node affinity to run on spot instances:

```yaml
affinity:
  nodeAffinity:
    preferredDuringSchedulingIgnoredDuringExecution:
    - weight: 100
      preference:
        matchExpressions:
        - key: node.kubernetes.io/instance-type
          operator: In
          values:
          - spot
```

## References

- AGENTS.md § Configuration Policy
- AGENTS.md § Registry Hygiene
- PRODUCTION_READINESS.md § Deployment
- docs/observability/OBSERVABILITY_SLOS.md
