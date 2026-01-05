# Integration Hardening Plan

## Critical Discovery: Langflow Integration

Port 7860 is **NOT** a stray process - it's the **intentional Demo UI** (Langflow) that integrates with CUGAr-SALES.

### Evidence
1. **[src/cuga/settings.toml](src/cuga/settings.toml#L44)**: `demo = 7860`
2. **[docs/architecture/010-agent-orchestration.md](docs/architecture/010-agent-orchestration.md)**: "Agent Orchestration (Langflow + ALTK)"
3. **[Frontend constants.ts](src/frontend_workspaces/agentic_chat/src/constants.ts)**: Defaults to `http://localhost:7860`
4. **[Extension background.js](src/frontend_workspaces/extension/releases/chrome-mv3/background.js)**: Connects to `http://localhost:7860`
5. **[src/cuga/langflow_components/](src/cuga/langflow_components/)**: Integration components exist

---

## Architecture: Three-Service Stack

```
┌─────────────────────────────────────────┐
│  CUGAr-SALES Full Stack                 │
├─────────────────────────────────────────┤
│  Port 8000: Backend API (FastAPI)      │ ← Main orchestration
│  Port 3000: Frontend UI (Vite/React)   │ ← Modern SPA
│  Port 7860: Demo UI (Langflow/Gradio)  │ ← Alternative demo interface
└─────────────────────────────────────────┘
```

---

## Issues to Fix

### 1. **start-dev.sh Kills Port 7860** ❌
**Current behavior:**
```bash
# Line 18 in start-dev.sh
lsof -ti:7860 | xargs kill -9  # WRONG - kills Langflow!
```

**Problem:** Frontend expects `localhost:7860` to be available, but we kill it.

**Fix:** Remove port 7860 from kill list OR add logic to start Langflow if needed.

---

### 2. **Langflow Startup Not Integrated** ⚠️
**Current state:** `start-dev.sh` starts ports 8000 and 3000 only.

**Missing:** No logic to start port 7860 (Demo UI).

**Options:**
- **Option A:** User starts Langflow manually: `cuga start demo`
- **Option B:** Integrate Langflow startup into `start-dev.sh`
- **Option C:** Document two deployment modes (dev vs demo)

---

### 3. **Frontend Connection Expectations** 🔌
**[constants.ts](src/frontend_workspaces/agentic_chat/src/constants.ts) (lines 22-41):**
```typescript
// In development, use localhost with port 7860 (default port)
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 
  (import.meta.env.DEV 
    ? 'http://localhost:7860'  // ← Frontend expects this
    : window.location.origin);
```

**Issue:** If port 7860 is not running, frontend may fail to connect.

**Fix:** Either:
- Start Langflow in `start-dev.sh`
- Change frontend default to `http://localhost:8000` (main backend)
- Add connection fallback logic in frontend

---

### 4. **Extension Integration** 📱
**[background.js](src/frontend_workspaces/extension/releases/chrome-mv3/background.js):**
```javascript
const K="http://localhost:7860"  // Hardcoded to Langflow
```

**Issue:** Extension expects command streaming from port 7860.

**Fix:** Verify if extension should connect to 7860 (Langflow) or 8000 (main backend).

---

### 5. **Documentation Misalignment** 📝
**Files to update:**
- [PORT_7860_ISSUE.md](PORT_7860_ISSUE.md) - Currently incorrect
- [QUICK_START.md](QUICK_START.md) - Mentions "stray Gradio" (wrong)
- [QUICK_REFERENCE.md](QUICK_REFERENCE.md) - May need Langflow startup steps

**Fix:** Update all docs to reflect correct three-service architecture.

---

## Recommended Integration Approach

### Two Deployment Modes

#### **Mode 1: Development (React + Backend)**
```bash
./scripts/start-dev.sh
# Starts: 8000 (backend) + 3000 (frontend)
# Use case: UI/UX development, backend API development
```

#### **Mode 2: Full Stack (+ Langflow Demo)**
```bash
cuga start demo &          # Port 7860 + 8001 (registry)
./scripts/start-dev.sh      # Port 8000 + 3000
# Starts: 7860 (demo) + 8001 (registry) + 8000 (backend) + 3000 (frontend)
# Use case: Full feature testing, demos, extension development
```

---

## Action Items

### Immediate Fixes (Critical)
1. **Remove port 7860 from kill list** in [start-dev.sh](scripts/start-dev.sh#L18)
   - Change: `for port in 8000 3000; do` (remove 7860)
   
2. **Update PORT_7860_ISSUE.md** with correct analysis
   - Clarify: Port 7860 is intentional, not an error
   
3. **Update QUICK_START.md**
   - Document two deployment modes
   - Clarify when to use `cuga start demo` vs `start-dev.sh`

### Integration Testing (High Priority)
4. **Test frontend with/without port 7860**
   - Verify: Does frontend work when 7860 is down?
   - Fix: Add connection fallback if needed
   
5. **Verify extension integration**
   - Test: Does extension need port 7860 running?
   - Document: Extension requirements
   
6. **Langflow component testing**
   - Test: `cuga start demo` launches correctly
   - Verify: Port 7860 serves Langflow UI
   - Test: Langflow components integrate with backend

### Documentation (Medium Priority)
7. **Create LANGFLOW_INTEGRATION.md**
   - Architecture overview
   - When to use Langflow vs React frontend
   - Startup commands and port mapping
   
8. **Update ARCHITECTURE.md**
   - Add three-service architecture diagram
   - Clarify Langflow's role
   - Document port allocation

### Optional Enhancements (Low Priority)
9. **Add Langflow health check** to `validate_startup.py`
   - Optional check: Is port 7860 responsive?
   - Skip if user doesn't need Langflow
   
10. **Create unified startup script**
    - `scripts/start-full-stack.sh` - Launches all three services
    - Includes Langflow, backend, and frontend

---

## Questions to Answer

1. **Should Langflow be required or optional?**
   - If required: Integrate into `start-dev.sh`
   - If optional: Document as separate deployment mode

2. **Does the React frontend (port 3000) need Langflow (port 7860)?**
   - Test: Can frontend work with only port 8000 (backend)?
   - If yes: Change default API URL in constants.ts
   - If no: Add Langflow startup to `start-dev.sh`

3. **Is Langflow the "demo UI" or "primary UI"?**
   - Demo UI: Keep separate, document as alternative
   - Primary UI: Integrate into main startup flow

4. **What does `cuga start demo` actually launch?**
   - Need to verify: Does it start port 7860?
   - Need to verify: Does it start port 8001 (registry)?
   - Need to test: Full command output and health checks

---

## Current State Summary

| Service | Port | Status | Startup Command |
|---------|------|--------|----------------|
| Backend API | 8000 | ✅ Working | `start-dev.sh` |
| Frontend UI | 3000 | ✅ Working | `start-dev.sh` |
| Demo UI (Langflow) | 7860 | ⚠️ Not integrated | `cuga start demo` |
| MCP Registry | 8001 | ❓ Unknown | `cuga start demo`? |

**Risk:** Frontend expects port 7860, but it's not guaranteed to be running.

**Impact:** Integration may be broken or incomplete.

---

## Next Steps

1. **Remove port 7860 from kill list** (2 min)
2. **Test `cuga start demo`** to verify Langflow startup (10 min)
3. **Test frontend with/without port 7860** (15 min)
4. **Update documentation** with correct architecture (30 min)
5. **Create integration test** for three-service stack (1 hour)

---

## Conclusion

The initial diagnosis was **incorrect**. Langflow is **intentional**, not a bug. 

Current `start-dev.sh` **breaks integration** by killing port 7860.

**Recommended fix:** Document two deployment modes and remove 7860 from kill list.

**Further investigation needed:** Test if frontend requires Langflow to function properly.
