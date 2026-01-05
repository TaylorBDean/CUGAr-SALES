# CUGAr-SALES Deployment Modes

## Overview
CUGAr-SALES supports multiple deployment modes optimized for different use cases.

---

## Port Architecture

| Port | Service | Purpose | Started By |
|------|---------|---------|------------|
| 8000 | Backend API | Main orchestration, agents, WebSocket | `start-dev.sh` |
| 3000 | Frontend UI | Modern React SPA | `start-dev.sh` |
| 7860 | Demo UI | Langflow/Gradio interface (optional) | `cuga start demo` |
| 8001 | MCP Registry | Tool registry service | `cuga start demo` |

---

## Deployment Modes

### 1. Development Mode (Default) ✅

**Use Case:** UI/UX development, backend API development, daily work

**Command:**
```bash
./scripts/start-dev.sh
```

**Services Started:**
- ✅ Port 8000: Backend API (FastAPI + Uvicorn)
- ✅ Port 3000: Frontend UI (Vite + React)

**Features:**
- Hot reload for both frontend and backend
- WebSocket trace streaming
- Modern React UI with real-time updates
- Full agent orchestration capabilities

**Access:**
- Frontend: http://localhost:3000
- Backend API: http://127.0.0.1:8000
- API Docs: http://127.0.0.1:8000/docs
- WebSocket: ws://localhost:8000/ws/traces/{traceId}

---

### 2. Demo Mode (Langflow UI)

**Use Case:** Visual workflow demos, Langflow component testing, presentations

**Command:**
```bash
cuga start demo
```

**Services Started:**
- ✅ Port 7860: Langflow/Gradio Demo UI
- ✅ Port 8001: MCP Registry

**Features:**
- Visual workflow design with Langflow
- Gradio-based interactive UI
- Component testing and debugging

**Access:**
- Demo UI: http://localhost:7860
- Registry: http://localhost:8001

**Note:** This mode does NOT start the main backend (8000) or React frontend (3000).

---

### 3. Full Stack Mode (All Services)

**Use Case:** Complete integration testing, extension development, full feature demonstrations

**Commands:**
```bash
# Terminal 1: Start Langflow + Registry
cuga start demo

# Terminal 2: Start Backend + Frontend
./scripts/start-dev.sh
```

**Services Started:**
- ✅ Port 8000: Backend API
- ✅ Port 3000: Frontend UI  
- ✅ Port 7860: Demo UI (Langflow)
- ✅ Port 8001: MCP Registry

**Access All UIs:**
- Primary UI: http://localhost:3000 (React)
- Demo UI: http://localhost:7860 (Langflow)
- Backend API: http://127.0.0.1:8000
- Registry: http://localhost:8001

---

### 4. CRM Demo Mode

**Use Case:** Testing CRM integration, email workflows, MCP server demos

**Command:**
```bash
cuga start demo_crm
```

**Services Started:**
- ✅ CRM API Server
- ✅ Email MCP Server (optional with `--no-email` flag)
- ✅ Mail Sink Server
- ✅ MCP Registry
- ✅ Demo Backend

**Features:**
- Full CRM operations (contacts, accounts, leads)
- Email sending/receiving simulation
- Read-only mode available (`--read-only`)
- Sample data generation (`--sample-memory-data`)

**Access:**
- Demo UI: http://localhost:7860
- CRM API: Check console output for port

---

## Frontend Connection Configuration

### Default Behavior (After Refactoring)

The React frontend [constants.ts](../src/frontend_workspaces/agentic_chat/src/constants.ts) now defaults to:

```typescript
// Development: http://localhost:8000 (main backend)
// Production: window.location.origin (HF Spaces, etc.)
```

**Old behavior (before fix):** Frontend defaulted to `http://localhost:7860` (Langflow), which required Langflow to be running.

**New behavior (after fix):** Frontend defaults to `http://localhost:8000` (main backend), which works with `start-dev.sh` out of the box.

### Override API URL

Set environment variable to override default:

```bash
# .env file
REACT_APP_API_URL=http://localhost:7860  # Use Langflow instead

# Or at build time
REACT_APP_API_URL=http://custom-host:8080 pnpm run build
```

---

## Choosing the Right Mode

| If you want to... | Use this mode | Command |
|-------------------|---------------|---------|
| Develop React UI | Development Mode | `./scripts/start-dev.sh` |
| Develop backend APIs | Development Mode | `./scripts/start-dev.sh` |
| Test agents end-to-end | Development Mode | `./scripts/start-dev.sh` |
| Create visual workflows | Demo Mode | `cuga start demo` |
| Test Langflow components | Demo Mode | `cuga start demo` |
| Demo in presentations | Demo Mode | `cuga start demo` |
| Test CRM integration | CRM Demo Mode | `cuga start demo_crm` |
| Test all integrations | Full Stack Mode | Both commands (2 terminals) |
| Test extension | Full Stack Mode | Both commands + extension |

---

## Integration Notes

### Frontend ↔ Backend

**Default Connection:** Frontend (3000) → Backend (8000)

The React frontend connects to the main FastAPI backend for:
- Agent orchestration
- Tool execution
- WebSocket trace streaming
- File operations
- Memory management

### Langflow ↔ Backend

**Optional Integration:** Langflow (7860) can orchestrate agents independently

Langflow components in [src/cuga/langflow_components/](../src/cuga/langflow_components/):
- `planner_component.py` - Planning integration
- `executor_component.py` - Execution with registry
- `guard_orchestrator.py` - Safety guardrails
- `watsonx_llm_component.py` - Watsonx LLM integration

### Chrome Extension ↔ Backend

**Connection:** Extension can connect to either:
- Port 8000 (main backend) - Recommended
- Port 7860 (Langflow demo) - Legacy

Extension configuration in [background.js](../src/frontend_workspaces/extension/releases/chrome-mv3/background.js) may need updating to point to port 8000.

---

## Troubleshooting

### Port Already in Use

```bash
# Check what's using a port
lsof -nP -iTCP:8000 -sTCP:LISTEN

# Kill specific port
lsof -ti:8000 | xargs kill -9

# Clean development ports only
lsof -ti:8000,3000 | xargs kill -9

# Clean all CUGAr ports
lsof -ti:8000,3000,7860,8001 | xargs kill -9
```

### Frontend Can't Connect to Backend

1. **Check backend is running:**
   ```bash
   curl http://127.0.0.1:8000/health
   ```

2. **Check frontend API URL:**
   - Should be `http://localhost:8000` (after refactoring)
   - Check [constants.ts](../src/frontend_workspaces/agentic_chat/src/constants.ts)

3. **Verify CORS configuration:**
   - Backend should allow `localhost:3000` origin
   - Check [main.py CORS settings](../src/cuga/backend/server/main.py)

### Langflow Won't Start

```bash
# Check registry is available first
curl http://localhost:8001/health

# Try starting with sandbox mode
cuga start demo --sandbox

# Check logs
tail -f logs/demo.log
```

### Services Keep Restarting

Check for port conflicts:
```bash
# See what's listening on all CUGAr ports
lsof -nP -iTCP:8000,3000,7860,8001 -sTCP:LISTEN
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    Development Mode                         │
│                 (./scripts/start-dev.sh)                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────┐         HTTP/WS          ┌───────────┐  │
│   │   Frontend   │ ◄─────────────────────► │  Backend  │  │
│   │ localhost:   │                          │ 127.0.0.1:│  │
│   │    3000      │                          │    8000   │  │
│   │  (React/Vite)│                          │ (FastAPI) │  │
│   └──────────────┘                          └───────────┘  │
│         ▲                                         │         │
│         │                                         ▼         │
│         │                                   ┌───────────┐  │
│         │                                   │  Agents   │  │
│         │                                   │Orchestrator│ │
│         │                                   └───────────┘  │
│         │                                         │         │
│         │                                         ▼         │
│    User Browser                            ┌───────────┐  │
│                                            │   Tools   │  │
│                                            │  Registry │  │
│                                            └───────────┘  │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Demo Mode                            │
│                    (cuga start demo)                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   ┌──────────────┐                          ┌───────────┐  │
│   │   Langflow   │ ◄─────────────────────► │  Registry │  │
│   │   Demo UI    │         HTTP            │ localhost:│  │
│   │ localhost:   │                          │    8001   │  │
│   │    7860      │                          │   (MCP)   │  │
│   │ (Gradio)     │                          └───────────┘  │
│   └──────────────┘                                │         │
│         ▲                                         ▼         │
│         │                                   ┌───────────┐  │
│         │                                   │   Tools   │  │
│         │                                   │   & MCPs  │  │
│    User Browser                            └───────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## Production Deployment

For production deployments (e.g., Hugging Face Spaces):

1. **Environment Detection:**
   - Frontend auto-detects and uses `window.location.origin`
   - No hardcoded localhost URLs in production builds

2. **Single Domain:**
   - Backend and frontend served from same origin
   - No CORS issues

3. **Port Configuration:**
   - Backend typically runs on port 7860 (HF Spaces default)
   - Frontend serves static build from same port

4. **Environment Variables:**
   - Set `REACT_APP_API_URL` if backend is on different domain
   - Configure CORS origins appropriately

See [PRODUCTION_READINESS.md](../PRODUCTION_READINESS.md) for complete production deployment guide.

---

## Related Documentation

- [QUICK_START.md](../QUICK_START.md) - Getting started guide
- [AGENTS.md](../AGENTS.md) - Canonical guardrails and architecture
- [INTEGRATION_HARDENING_PLAN.md](../INTEGRATION_HARDENING_PLAN.md) - Integration analysis
- [PORT_7860_ISSUE.md](../PORT_7860_ISSUE.md) - Port 7860 clarification
- [docs/architecture/010-agent-orchestration.md](architecture/010-agent-orchestration.md) - Langflow integration details

---

**Last Updated:** January 5, 2026  
**Status:** ✅ All deployment modes verified and documented
