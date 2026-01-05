/**
 * Hook for WebSocket trace streaming
 * Provides real-time trace event updates from backend
 */

import { useState, useEffect, useRef, useCallback } from 'react';

export interface TraceEvent {
  event: string;
  timestamp: string;
  metadata?: Record<string, any>;
  status?: string;
  trace_id?: string;
}

export interface UseTraceStreamOptions {
  autoConnect?: boolean;
  reconnectAttempts?: number;
  reconnectDelay?: number;
}

const DEFAULT_OPTIONS: UseTraceStreamOptions = {
  autoConnect: true,
  reconnectAttempts: 3,
  reconnectDelay: 1000,
};

export function useTraceStream(
  traceId: string | null,
  options: UseTraceStreamOptions = {}
) {
  const opts = { ...DEFAULT_OPTIONS, ...options };
  
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCount = useRef(0);
  const reconnectTimeout = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (!traceId) {
      setError('No trace ID provided');
      return;
    }

    try {
      // Close existing connection
      if (wsRef.current) {
        wsRef.current.close();
      }

      // Create WebSocket connection
      const ws = new WebSocket(`ws://localhost:8000/ws/traces/${traceId}`);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log(`[TraceStream] Connected to trace ${traceId}`);
        setIsConnected(true);
        setError(null);
        reconnectCount.current = 0;

        // Send initial ping
        ws.send('ping');
      };

      ws.onmessage = (event) => {
        try {
          // Handle pong response
          if (event.data === 'pong') {
            return;
          }

          // Parse and add trace event
          const traceEvent: TraceEvent = JSON.parse(event.data);
          setEvents((prev) => [...prev, traceEvent]);
          
          console.log(`[TraceStream] Event: ${traceEvent.event}`, traceEvent);
        } catch (err) {
          console.error('[TraceStream] Failed to parse event:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('[TraceStream] WebSocket error:', error);
        setError('WebSocket connection error');
      };

      ws.onclose = () => {
        console.log('[TraceStream] Disconnected');
        setIsConnected(false);

        // Attempt reconnection
        if (reconnectCount.current < opts.reconnectAttempts!) {
          reconnectCount.current += 1;
          console.log(
            `[TraceStream] Reconnecting... (${reconnectCount.current}/${opts.reconnectAttempts})`
          );
          
          reconnectTimeout.current = setTimeout(() => {
            connect();
          }, opts.reconnectDelay);
        } else {
          setError('Connection lost. Max reconnect attempts reached.');
        }
      };
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to connect');
    }
  }, [traceId, opts.reconnectAttempts, opts.reconnectDelay]);

  const disconnect = useCallback(() => {
    if (reconnectTimeout.current) {
      clearTimeout(reconnectTimeout.current);
      reconnectTimeout.current = null;
    }
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    
    setIsConnected(false);
  }, []);

  const clearEvents = useCallback(() => {
    setEvents([]);
  }, []);

  const sendPing = useCallback(() => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send('ping');
    }
  }, []);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (opts.autoConnect && traceId) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [traceId, opts.autoConnect, connect, disconnect]);

  // Heartbeat ping every 30 seconds
  useEffect(() => {
    if (!isConnected) return;

    const interval = setInterval(() => {
      sendPing();
    }, 30000);

    return () => clearInterval(interval);
  }, [isConnected, sendPing]);

  return {
    events,
    isConnected,
    error,
    connect,
    disconnect,
    clearEvents,
    sendPing,
  };
}
