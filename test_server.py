"""
Minimal Test Server for AGENTS.md Integration Testing

This server provides only the AGENTS.md integration endpoints
without the full CUGAr backend dependencies.
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

# Import API routes
try:
    from cuga.backend.api.routes.agents import router as agents_router
    agents_loaded = True
except Exception as e:
    logger.warning(f"Could not load agents router: {e}")
    agents_loaded = False

try:
    from cuga.backend.api.websocket.traces import router as traces_router  
    traces_loaded = True
except Exception as e:
    logger.warning(f"Could not load traces router: {e}")
    traces_loaded = False

# Create FastAPI app
app = FastAPI(
    title="AGENTS.md Test Server",
    version="0.1.0",
    description="Minimal server for testing AGENTS.md integration"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
if agents_loaded:
    try:
        app.include_router(agents_router, prefix="")
        logger.info("✅ AGENTS.md coordinator endpoints registered at /api/agents/")
    except Exception as e:
        logger.error(f"❌ Failed to register agents router: {e}")
else:
    logger.warning("⚠️ Agents router not loaded")

if traces_loaded:
    try:
        app.include_router(traces_router, prefix="")
        logger.info("✅ WebSocket trace streaming registered at /ws/traces/{{trace_id}}")
    except Exception as e:
        logger.error(f"❌ Failed to register traces router: {e}")
else:
    logger.warning("⚠️ Traces router not loaded")

@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "AGENTS.md Test Server",
        "endpoints": {
            "health": "/api/agents/health",
            "execute": "/api/agents/execute",
            "approve": "/api/agents/approve",
            "budget": "/api/agents/budget/{profile}",
            "trace": "/api/agents/trace/{trace_id}",
            "websocket": "/ws/traces/{trace_id}"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
