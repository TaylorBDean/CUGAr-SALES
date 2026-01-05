"""
WebSocket routes for real-time trace streaming.

Provides WebSocket endpoints for streaming canonical trace events
to frontend components per AGENTS.md observability requirements.

Features:
- Real-time trace event streaming
- Automatic connection lifecycle management
- Thread-safe connection registry
- Graceful disconnection handling
- PII-safe event emission
"""

import asyncio
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from loguru import logger
import json

from cuga.orchestrator import TraceEmitter

# Import bridge and register WebSocket hook
try:
    from cuga.orchestrator.trace_websocket_bridge import set_websocket_emit_hook
    # Hook will be registered after emit_trace_event is defined
except ImportError:
    logger.warning("TraceEmitter WebSocket bridge not available")
    set_websocket_emit_hook = None


router = APIRouter()


class TraceStreamManager:
    """
    Manages WebSocket connections for trace streaming.
    
    Per AGENTS.md:
    - Thread-safe connection management
    - Automatic cleanup on disconnect
    - Canonical event emission only
    - PII-safe logging
    """
    
    def __init__(self):
        """Initialize connection registry."""
        self._connections: Dict[str, WebSocket] = {}
        self._lock = asyncio.Lock()
    
    async def connect(self, trace_id: str, websocket: WebSocket) -> None:
        """
        Register a new WebSocket connection for a trace.
        
        Args:
            trace_id: Trace identifier
            websocket: FastAPI WebSocket connection
        """
        async with self._lock:
            await websocket.accept()
            self._connections[trace_id] = websocket
            logger.info(f"WebSocket connected for trace {trace_id}")
    
    async def disconnect(self, trace_id: str) -> None:
        """
        Remove WebSocket connection from registry.
        
        Args:
            trace_id: Trace identifier
        """
        async with self._lock:
            if trace_id in self._connections:
                del self._connections[trace_id]
                logger.info(f"WebSocket disconnected for trace {trace_id}")
    
    async def emit_event(
        self,
        trace_id: str,
        event: Dict[str, Any]
    ) -> bool:
        """
        Emit trace event to connected WebSocket.
        
        Args:
            trace_id: Trace identifier
            event: Canonical trace event (from TraceEmitter)
        
        Returns:
            True if event was sent successfully, False otherwise
        """
        if trace_id not in self._connections:
            return False
        
        websocket = self._connections[trace_id]
        try:
            await websocket.send_json(event)
            return True
        except Exception as e:
            logger.warning(
                f"Failed to emit trace event to WebSocket: {e}",
                extra={"trace_id": trace_id, "event": event.get("event")}
            )
            # Remove dead connection
            await self.disconnect(trace_id)
            return False
    
    async def broadcast_to_trace(
        self,
        trace_id: str,
        events: list[Dict[str, Any]]
    ) -> None:
        """
        Send multiple events to a trace connection.
        
        Args:
            trace_id: Trace identifier
            events: List of canonical trace events
        """
        for event in events:
            await self.emit_event(trace_id, event)
    
    def is_connected(self, trace_id: str) -> bool:
        """Check if a trace has an active WebSocket connection."""
        return trace_id in self._connections
    
    def get_active_traces(self) -> list[str]:
        """Get list of trace IDs with active connections."""
        return list(self._connections.keys())


# Global trace stream manager instance
_trace_manager = TraceStreamManager()


@router.websocket("/ws/traces/{trace_id}")
async def trace_stream(websocket: WebSocket, trace_id: str):
    """
    WebSocket endpoint for real-time trace event streaming.
    
    Client connects with trace_id and receives:
    - Real-time canonical trace events (per AGENTS.md)
    - Connection status (pong responses to ping)
    - Automatic reconnection on error
    
    Protocol:
    - Client sends 'ping' → Server responds 'pong'
    - Server sends JSON trace events as they occur
    - Connection closes on completion or error
    
    Args:
        websocket: FastAPI WebSocket connection
        trace_id: Trace identifier from orchestrator
    
    Example frontend usage:
        const ws = new WebSocket(`ws://localhost:8000/ws/traces/${traceId}`);
        ws.onmessage = (event) => {
          const traceEvent = JSON.parse(event.data);
          console.log('Trace event:', traceEvent);
        };
    """
    await _trace_manager.connect(trace_id, websocket)
    
    try:
        # Send initial connection success message
        await websocket.send_json({
            "event": "connected",
            "trace_id": trace_id,
            "status": "success",
            "message": "WebSocket trace streaming active"
        })
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (ping/disconnect)
                data = await websocket.receive_text()
                
                # Handle ping/pong for connection health
                if data == "ping":
                    await websocket.send_text("pong")
                    logger.debug(f"Ping received for trace {trace_id}")
                
                # Handle graceful close request
                elif data == "close":
                    logger.info(f"Client requested close for trace {trace_id}")
                    break
                    
            except WebSocketDisconnect:
                logger.info(f"WebSocket disconnected for trace {trace_id}")
                break
            except Exception as e:
                logger.error(
                    f"Error in WebSocket receive loop: {e}",
                    extra={"trace_id": trace_id}
                )
                break
                
    finally:
        # Clean up connection on exit
        await _trace_manager.disconnect(trace_id)


async def emit_trace_event(trace_id: str, event: Dict[str, Any]) -> bool:
    """
    Emit a canonical trace event to connected WebSocket clients.
    
    This function is called by the orchestrator/trace emitter
    when events occur during plan execution.
    
    Args:
        trace_id: Trace identifier
        event: Canonical trace event dict with:
            - event: Event name (from TraceEmitter.CANONICAL_EVENTS)
            - trace_id: Trace identifier
            - timestamp: ISO timestamp
            - details: Event-specific details
            - status: Event status (pending/success/error)
    
    Returns:
        True if event was successfully sent, False otherwise
    
    Example usage in orchestrator:
        from cuga.backend.api.websocket import emit_trace_event
        
        # After TraceEmitter.emit()
        await emit_trace_event(trace_id, event_data)
    """
    return await _trace_manager.emit_event(trace_id, event)


async def broadcast_trace_events(
    trace_id: str,
    events: list[Dict[str, Any]]
) -> None:
    """
    Broadcast multiple trace events to a connected client.
    
    Useful for sending historical events when a client first connects,
    or batching multiple events for efficiency.
    
    Args:
        trace_id: Trace identifier
        events: List of canonical trace events
    """
    await _trace_manager.broadcast_to_trace(trace_id, events)


def is_trace_streaming(trace_id: str) -> bool:
    """
    Check if a trace has an active WebSocket connection.
    
    Args:
        trace_id: Trace identifier
    
    Returns:
        True if trace is actively streaming via WebSocket
    """
    return _trace_manager.is_connected(trace_id)


def get_active_trace_streams() -> list[str]:
    """
    Get list of all trace IDs with active WebSocket connections.
    
    Returns:
        List of trace_id strings
    """
    return _trace_manager.get_active_traces()


# Health check endpoint for WebSocket service
@router.get("/ws/health")
async def websocket_health():
    """
    WebSocket service health check.
    
    Returns:
        Status and active connection count
    """
    active_traces = get_active_trace_streams()
    return {
        "status": "healthy",
        "service": "trace-streaming",
        "active_connections": len(active_traces),
        "active_traces": active_traces[:10]  # Limit for privacy
    }


# Export router for main.py inclusion
traces_router = router


# Register WebSocket hook with TraceEmitter bridge on module load
if set_websocket_emit_hook is not None:
    set_websocket_emit_hook(emit_trace_event)
    logger.info("TraceEmitter → WebSocket streaming bridge activated")
