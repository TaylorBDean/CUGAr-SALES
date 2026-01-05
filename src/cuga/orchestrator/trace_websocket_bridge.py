"""
Integration layer between TraceEmitter and WebSocket streaming.

Provides automatic WebSocket broadcasting when trace events are emitted,
ensuring real-time updates to connected frontend clients.
"""

from typing import Optional, Callable, Awaitable, Dict, Any
from loguru import logger


# Global hook for WebSocket emission (set by WebSocket module)
_websocket_emit_hook: Optional[Callable[[str, Dict[str, Any]], Awaitable[bool]]] = None


def set_websocket_emit_hook(
    hook: Callable[[str, Dict[str, Any]], Awaitable[bool]]
) -> None:
    """
    Set the global WebSocket emission hook.
    
    Called by websocket.py on module import to register the
    emit_trace_event function for automatic streaming.
    
    Args:
        hook: Async function (trace_id, event) -> bool
    """
    global _websocket_emit_hook
    _websocket_emit_hook = hook
    logger.info("WebSocket trace streaming hook registered")


async def emit_to_websocket(trace_id: str, event: Dict[str, Any]) -> bool:
    """
    Emit a trace event to WebSocket if hook is registered.
    
    This is called automatically by TraceEmitter after storing
    an event locally, ensuring frontend receives real-time updates.
    
    Args:
        trace_id: Trace identifier
        event: Canonical trace event dict
    
    Returns:
        True if emitted successfully, False if no hook or emission failed
    """
    if _websocket_emit_hook is None:
        return False
    
    try:
        return await _websocket_emit_hook(trace_id, event)
    except Exception as e:
        logger.warning(
            f"Failed to emit trace event to WebSocket: {e}",
            extra={"trace_id": trace_id}
        )
        return False


def is_websocket_streaming_available() -> bool:
    """
    Check if WebSocket streaming is available.
    
    Returns:
        True if WebSocket hook is registered
    """
    return _websocket_emit_hook is not None
