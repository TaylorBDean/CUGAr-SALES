# Deployment

> **FastAPI's Role**: FastAPI is a **transport layer only** (HTTP/SSE endpoints, auth, budget enforcement). It delegates all orchestration to Planner/Coordinator/Workers. See [`docs/architecture/FASTAPI_ROLE.md`](architecture/FASTAPI_ROLE.md) for architectural boundaries.

- FastAPI surface at `src/cuga/backend/app.py` exposes `/health`, `/plan`, `/execute` (streaming SSE).
- Auth: `X-Token` header compared to `AGENT_TOKEN` env; budgets enforced via `AGENT_BUDGET_CEILING` and `X-Budget-Spent`.
- Configure via `configs/deploy/fastapi.yaml`; run with `uvicorn cuga.backend.app:app`.

## Architectural Boundaries

**FastAPI Responsibilities** (Transport Layer):
- ✅ Parse HTTP requests (JSON, headers, query params)
- ✅ Authenticate X-Token header
- ✅ Enforce AGENT_BUDGET_CEILING (middleware)
- ✅ Propagate trace_id to observability context
- ✅ Serialize responses (JSON / SSE streaming)
- ✅ Delegate to orchestration components

**Orchestration Responsibilities** (Planner/Coordinator/Workers):
- ✅ Tool ranking and plan creation (PlannerAgent)
- ✅ Worker selection and dispatch (CoordinatorAgent)
- ✅ Tool execution with sandboxing (WorkerAgent)
- ✅ Memory search and persistence (VectorMemory)
- ✅ Profile isolation and security boundaries

**Golden Rule**: If it's not about HTTP transport, auth, or budget enforcement, it doesn't belong in FastAPI.

## Deployment Modes
