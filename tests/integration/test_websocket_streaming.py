"""
Tests for WebSocket trace streaming functionality.

Validates:
- WebSocket connection lifecycle
- Event emission and reception
- Ping/pong health checks
- Graceful disconnection
- Multiple concurrent connections
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
import json

from cuga.backend.server.main import app
from cuga.backend.api.websocket import (
    emit_trace_event,
    broadcast_trace_events,
    is_trace_streaming,
    get_active_trace_streams,
)


@pytest.fixture
def client():
    """FastAPI test client."""
    return TestClient(app)


def test_websocket_health_endpoint(client):
    """Test WebSocket health check endpoint."""
    response = client.get("/ws/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert data["service"] == "trace-streaming"
    assert "active_connections" in data
    assert "active_traces" in data


def test_websocket_connection_lifecycle():
    """Test WebSocket connection and disconnection."""
    client = TestClient(app)
    trace_id = "test-trace-123"
    
    with client.websocket_connect(f"/ws/traces/{trace_id}") as websocket:
        # Receive connection success message
        data = websocket.receive_json()
        assert data["event"] == "connected"
        assert data["trace_id"] == trace_id
        assert data["status"] == "success"
        
        # Verify connection is registered
        assert is_trace_streaming(trace_id)
        
        # Test ping/pong
        websocket.send_text("ping")
        response = websocket.receive_text()
        assert response == "pong"
    
    # After context exit, connection should be cleaned up
    assert not is_trace_streaming(trace_id)


@pytest.mark.asyncio
async def test_emit_trace_event():
    """Test emitting trace events to connected WebSocket."""
    client = TestClient(app)
    trace_id = "test-trace-emit"
    
    with client.websocket_connect(f"/ws/traces/{trace_id}") as websocket:
        # Skip connection message
        websocket.receive_json()
        
        # Emit a canonical trace event
        event = {
            "event": "tool_call_start",
            "trace_id": trace_id,
            "timestamp": "2026-01-05T12:00:00Z",
            "details": {"tool": "test_tool"},
            "status": "pending"
        }
        
        # Emit event (this would normally be called from orchestrator)
        success = await emit_trace_event(trace_id, event)
        assert success
        
        # Verify event was received
        received = websocket.receive_json()
        assert received["event"] == "tool_call_start"
        assert received["trace_id"] == trace_id


@pytest.mark.asyncio
async def test_broadcast_multiple_events():
    """Test broadcasting multiple events at once."""
    client = TestClient(app)
    trace_id = "test-trace-broadcast"
    
    with client.websocket_connect(f"/ws/traces/{trace_id}") as websocket:
        # Skip connection message
        websocket.receive_json()
        
        # Broadcast multiple events
        events = [
            {
                "event": "plan_created",
                "trace_id": trace_id,
                "timestamp": "2026-01-05T12:00:00Z",
                "details": {"steps": 3},
                "status": "success"
            },
            {
                "event": "tool_call_start",
                "trace_id": trace_id,
                "timestamp": "2026-01-05T12:00:01Z",
                "details": {"tool": "test_tool"},
                "status": "pending"
            }
        ]
        
        await broadcast_trace_events(trace_id, events)
        
        # Verify both events received
        event1 = websocket.receive_json()
        assert event1["event"] == "plan_created"
        
        event2 = websocket.receive_json()
        assert event2["event"] == "tool_call_start"


def test_multiple_concurrent_connections():
    """Test multiple traces streaming simultaneously."""
    client = TestClient(app)
    trace_ids = ["trace-1", "trace-2", "trace-3"]
    
    # Open multiple WebSocket connections
    websockets = []
    for trace_id in trace_ids:
        ws = client.websocket_connect(f"/ws/traces/{trace_id}")
        websockets.append(ws.__enter__())
    
    try:
        # Verify all connections registered
        active_traces = get_active_trace_streams()
        for trace_id in trace_ids:
            assert trace_id in active_traces
        
        assert len(active_traces) >= len(trace_ids)
        
        # Test ping on all connections
        for ws in websockets:
            # Skip connection message
            ws.receive_json()
            ws.send_text("ping")
            assert ws.receive_text() == "pong"
    
    finally:
        # Clean up all connections
        for ws in websockets:
            ws.__exit__(None, None, None)


def test_graceful_close():
    """Test graceful connection close."""
    client = TestClient(app)
    trace_id = "test-trace-close"
    
    with client.websocket_connect(f"/ws/traces/{trace_id}") as websocket:
        # Skip connection message
        websocket.receive_json()
        
        # Request graceful close
        websocket.send_text("close")
        
        # Connection should close cleanly
        # (WebSocket will raise exception on next receive)


def test_emit_to_nonexistent_trace():
    """Test emitting to a trace without active connection."""
    
    async def test():
        trace_id = "nonexistent-trace"
        event = {"event": "test", "trace_id": trace_id}
        
        # Should return False (no connection)
        success = await emit_trace_event(trace_id, event)
        assert not success
    
    asyncio.run(test())


def test_websocket_connection_error_handling(client):
    """Test WebSocket handles invalid messages gracefully."""
    trace_id = "test-trace-error"
    
    with client.websocket_connect(f"/ws/traces/{trace_id}") as websocket:
        # Skip connection message
        websocket.receive_json()
        
        # Send invalid message (should be handled without crash)
        websocket.send_text("invalid_command")
        
        # Connection should still work
        websocket.send_text("ping")
        assert websocket.receive_text() == "pong"


@pytest.mark.integration
def test_integration_with_trace_emitter():
    """
    Integration test: TraceEmitter events → WebSocket streaming.
    
    This tests the full flow from orchestrator trace emission
    to frontend WebSocket reception.
    """
    from cuga.orchestrator import TraceEmitter
    
    client = TestClient(app)
    
    # Create trace emitter
    emitter = TraceEmitter()
    trace_id = emitter.trace_id
    
    with client.websocket_connect(f"/ws/traces/{trace_id}") as websocket:
        # Skip connection message
        websocket.receive_json()
        
        # Emit canonical event via TraceEmitter
        emitter.emit(
            "plan_created",
            {"goal": "test goal", "steps": 3}
        )
        
        # Get the emitted event
        events = emitter.get_trace()
        assert len(events) == 1
        
        # Simulate broadcasting to WebSocket
        # (In production, orchestrator would call emit_trace_event)
        async def send_event():
            await emit_trace_event(trace_id, events[0])
        
        asyncio.run(send_event())
        
        # Verify frontend receives it
        received = websocket.receive_json()
        assert received["event"] == "plan_created"
        assert received["trace_id"] == trace_id
