# Port 7860 Clarification - Understanding Langflow Integration

## Overview
Port 7860 is the **intentional Demo UI** (Langflow/Gradio interface) that is part of CUGAr-SALES architecture.

## Correct Understanding
**Port 7860 is NOT an error** - it's the Langflow-based demo interface started with `cuga start demo`.

This is an **optional alternative UI** to the main React frontend (port 3000) for demonstrations and visual workflow design.

## Evidence from Configuration

**[src/cuga/settings.toml](src/cuga/settings.toml#L44):**
```toml
[server_ports]
registry = 8001
demo = 7860  # ← Langflow Demo UI port
apis_url = 9000
environment_url = 8000
```

**[docs/architecture/010-agent-orchestration.md](docs/architecture/010-agent-orchestration.md):**
- Title: "Agent Orchestration (Langflow + ALTK)"
- Langflow is a first-class architectural component

**[src/cuga/cli.py](src/cuga/cli.py#L535):**
```python
# demo: Starts both registry and demo agent directly
# (registry on port 8001, demo on port 7860)
```

## CUGAr-SALES Complete Architecture

```
┌──────────────────────────────────────────────────┐
│  CUGAr-SALES Full Stack                          │
├──────────────────────────────────────────────────┤
│  Port 8000: Backend API (FastAPI)               │ ← Main orchestration
│  Port 3000: Frontend UI (Vite/React)            │ ← Modern SPA (default)
│  Port 7860: Demo UI (Langflow/Gradio)           │ ← Alternative demo interface
│  Port 8001: MCP Registry                         │ ← Tool registry service
└──────────────────────────────────────────────────┘
```

## When to Use Which

### Development Mode (Default)
```bash
./scripts/start-dev.sh
# Starts: Port 8000 (backend) + Port 3000 (React frontend)
# Use: UI/UX development, backend API development
```

### Demo Mode (Langflow UI)
```bash
cuga start demo
# Starts: Port 7860 (Langflow) + Port 8001 (registry)
# Use: Visual workflow demos, Langflow component testing
```

### Full Stack (All Services)
```bash
cuga start demo &  # Start Langflow + registry
./scripts/start-dev.sh  # Start backend + frontend
# Use: Complete integration testing, extension development
```

## Integration Notes

### Frontend Connection
The React frontend (port 3000) now connects to **port 8000** (main backend) by default.

Port 7860 (Langflow demo) is **optional** and only needed for:
- Visual workflow design
- Demo presentations using Langflow UI
- Testing Langflow components

### Starting Langflow
```bash
# Start Langflow demo UI (port 7860)
cuga start demo

# Check if Langflow is running
lsof -nP -iTCP:7860 -sTCP:LISTEN

# Stop Langflow if needed
lsof -ti:7860 | xargs kill -9
```

### Port Cleanup
`start-dev.sh` intentionally **does NOT kill port 7860** to preserve any running Langflow instance.

To clean all ports:
```bash
# Clean development ports only (8000, 3000)
lsof -ti:8000,3000 | xargs kill -9

# Clean all CUGAr ports including Langflow (7860, 8001)
lsof -ti:7860,8000,3000,8001 | xargs kill -9
```

## Related Files
- [`src/cuga/settings.toml`](src/cuga/settings.toml#L44) - Port configuration
- [`src/cuga/cli.py`](src/cuga/cli.py#L535) - Demo startup command
- [`docs/architecture/010-agent-orchestration.md`](docs/architecture/010-agent-orchestration.md) - Langflow integration
- [`src/frontend_workspaces/agentic_chat/src/constants.ts`](src/frontend_workspaces/agentic_chat/src/constants.ts) - Frontend API URL (now port 8000)
- [`scripts/start-dev.sh`](scripts/start-dev.sh#L18) - Development startup (ports 8000, 3000)
- [`INTEGRATION_HARDENING_PLAN.md`](INTEGRATION_HARDENING_PLAN.md) - Complete integration analysis

---

**Status:** ✅ **CLARIFIED**  
**Date:** January 5, 2026  
**Impact:** Frontend now connects to port 8000 (main backend) by default. Port 7860 (Langflow) is optional.
