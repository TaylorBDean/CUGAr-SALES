# Port 7860 Clarification - UPDATED ⚠️

## ❌ Previous Misunderstanding (CORRECTED)

**I initially thought** port 7860 was a "stray Langflow process" unrelated to CUGAr-SALES.

**This was WRONG.** Port 7860 is **intentionally part of the CUGAr-SALES stack.**

## ✅ Correct Understanding

Port 7860 is the **CUGAr Demo Agent UI** (Gradio/FastAPI interface).

### Evidence from Configuration

**[`src/cuga/settings.toml`](src/cuga/settings.toml#L44):**
```toml
[server_ports]
registry = 8001
demo = 7860  # ← Demo Agent UI port
apis_url = 9000
environment_url = 8000
```

**[`src/cuga/cli.py`](src/cuga/cli.py#L535):**
```python
# demo: Starts both registry and demo agent directly 
# (registry on port 8001, demo on port 7860)
```

## 🏗️ Complete CUGAr-SALES Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  CUGAr-SALES Full Stack                                     │
├─────────────────────────────────────────────────────────────┤
│  Port 8000: Backend API (FastAPI/uvicorn)                   │
│  • Main orchestration API                                   │
│  • WebSocket trace streaming                                │
│  • REST endpoints for agents                                │
├─────────────────────────────────────────────────────────────┤
│  Port 3000: Frontend UI (Vite/React)                        │
│  • Modern React SPA                                         │
│  • Real-time WebSocket connections                          │
│  • UI/UX for agent interactions                             │
├─────────────────────────────────────────────────────────────┤
│  Port 7860: Demo Agent UI (Gradio/FastAPI) ← IMPORTANT!    │
│  • Alternative demo interface                               │
│  • Started with: `cuga start demo`                          │
│  • Uses Langflow components integration                     │
├─────────────────────────────────────────────────────────────┤
│  Port 8001: MCP Registry                                    │
│  • Tool registry service                                    │
│  • Started with: `cuga start demo` or `cuga start registry` │
└─────────────────────────────────────────────────────────────┘
```

## 🎯 Two Ways to Run CUGAr-SALES

### Option 1: Full Demo Stack (with port 7860)
```bash
cuga start demo

# Starts:
# - Port 8001: MCP Registry
# - Port 7860: Demo Agent UI (Gradio interface)
```

### Option 2: Development Stack (without port 7860)
```bash
./scripts/start-dev.sh

# Starts:
# - Port 8000: Backend API
# - Port 3000: Frontend UI (React)
```

## 🔧 Fixes Applied

1. **Removed port 7860 from kill list** in [`scripts/start-dev.sh`](scripts/start-dev.sh)
2. **Added clarifying comment** explaining port 7860's purpose
3. **Updated documentation** to explain both deployment options

## 🤔 When to Use Which?

| Use Case | Command | Ports Used |
|----------|---------|------------|
| **Office demos** | `cuga start demo` | 7860 (Gradio UI) + 8001 (Registry) |
| **UI/UX development** | `./scripts/start-dev.sh` | 8000 (API) + 3000 (React) |
| **Full stack dev** | Both! | All 4 ports (3000, 7860, 8000, 8001) |

## 📝 Integration with Langflow

The Demo UI (port 7860) uses Langflow components found in:
- [`src/cuga/langflow_components/`](src/cuga/langflow_components/)
  - `guard_input.py`
  - `guard_tool.py`
  - `guard_output.py`
  - `guard_orchestrator.py`
  - `planner_component.py`
  - `executor_component.py`
  - `watsonx_llm_component.py`

These provide Langflow-compatible wrappers for CUGAr's agent components.

## ✅ Correct Behavior

**Port 7860 should remain running** if you started it with `cuga start demo`.

The startup script (`./scripts/start-dev.sh`) no longer kills port 7860, allowing both UIs to coexist:
- **Port 3000**: Modern React frontend
- **Port 7860**: Gradio demo interface

---

**Status:** ✅ **CORRECTED**  
**Date:** January 5, 2026  
**Impact:** Port 7860 will no longer be killed by startup scripts. Both UIs can run simultaneously.
