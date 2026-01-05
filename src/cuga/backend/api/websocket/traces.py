"""WebSocket endpoint for real-time trace streaming."""

from typing import Dict, List, Set
from fastapi import WebSocket, WebSocketDisconnect, APIRouter
from loguru import logger

router = APIRouter()

# Global connection manager for trace streaming
class TraceConnectionManager:
    """Manages WebSocket connections for trace streaming."""
    
    def __init__(self):
        # Map trace_id -> list of connected WebSockets
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, trace_id: str):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        
        if trace_id not in self.active_connections:
            self.active_connections[trace_id] = []
        
        self.active_connections[trace_id].append(websocket)
        logger.info(f"[WebSocket] Client connected to trace {trace_id}")
    
    def disconnect(self, websocket: WebSocket, trace_id: str):
        """Remove a WebSocket connection."""
        if trace_id in self.active_connections:
            try:
                self.active_connections[trace_id].remove(websocket)
                if not self.active_connections[trace_id]:
                    del self.active_connections[trace_id]
                logger.info(f"[WebSocket] Client disconnected from trace {trace_id}")
            except ValueError:
                pass
    
    async def broadcast(self, trace_id: str, message: dict):
        """Broadcast a message to all connections for a trace."""
        if trace_id in self.active_connections:
            disconnected = []
            
            for connection in self.active_connections[trace_id]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"[WebSocket] Failed to send to client: {e}")
                    disconnected.append(connection)
            
            # Clean up disconnected clients
            for connection in disconnected:
                self.disconnect(connection, trace_id)
    
    def get_connection_count(self, trace_id: str) -> int:
        """Get number of active connections for a trace."""
        return len(self.active_connections.get(trace_id, []))


# Global manager instance
manager = TraceConnectionManager()


@router.websocket("/ws/traces/{trace_id}")
async def trace_websocket(websocket: WebSocket, trace_id: str):
    """
    WebSocket endpoint for real-time trace event streaming.
    
    Clients connect to receive live updates as trace events are emitted
    by the AGENTSCoordinator during plan execution.
    
    Message format:
    {
        "event": "tool_call_start",
        "timestamp": "2026-01-04T18:00:00Z",
        "metadata": {...},
        "status": "success"
    }
    
    Canonical events:
    - plan_created
    - tool_call_start
    - tool_call_complete
    - tool_call_error
    - budget_warning
    - budget_exceeded
    - approval_requested
    - approval_received
    - approval_timeout
    """
    await manager.connect(websocket, trace_id)
    
    try:
        # Keep connection alive and handle any incoming messages
        # (though this is primarily a one-way stream from server to client)
        while True:
            # Wait for any message from client (e.g., ping/pong)
            data = await websocket.receive_text()
            
            # Echo back as heartbeat
            if data == "ping":
                await websocket.send_text("pong")
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, trace_id)
        logger.info(f"[WebSocket] Client cleanly disconnected from trace {trace_id}")
    
    except Exception as e:
        logger.error(f"[WebSocket] Error in trace stream: {e}")
        manager.disconnect(websocket, trace_id)


def get_trace_manager() -> TraceConnectionManager:
    """Get the global trace connection manager."""
    return manager
