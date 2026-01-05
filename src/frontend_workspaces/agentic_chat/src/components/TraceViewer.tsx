/**
 * Trace Viewer Component
 * Displays execution trace for observability (AGENTS.md compliant)
 */

import React, { useState } from 'react';
import { 
  ChevronRight, 
  ChevronDown,
  Clock, 
  CheckCircle, 
  XCircle, 
  AlertTriangle,
  Activity,
  Zap,
  X
} from 'lucide-react';

export interface TraceEvent {
  event: string;
  timestamp: string;
  details: Record<string, any>;
  status?: 'success' | 'error' | 'pending' | 'running';
  duration_ms?: number;
  tool_name?: string;
  trace_id?: string;
}

interface TraceViewerProps {
  trace: TraceEvent[];
  isOpen: boolean;
  onClose: () => void;
  threadId?: string;
}

export const TraceViewer: React.FC<TraceViewerProps> = ({ 
  trace, 
  isOpen, 
  onClose,
  threadId 
}) => {
  const [expandedEvents, setExpandedEvents] = useState<Set<number>>(new Set());

  if (!isOpen) return null;

  const toggleExpanded = (index: number) => {
    const newExpanded = new Set(expandedEvents);
    if (newExpanded.has(index)) {
      newExpanded.delete(index);
    } else {
      newExpanded.add(index);
    }
    setExpandedEvents(newExpanded);
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="status-icon success" size={16} />;
      case 'error':
        return <XCircle className="status-icon error" size={16} />;
      case 'pending':
        return <Clock className="status-icon pending" size={16} />;
      case 'running':
        return <Activity className="status-icon running" size={16} />;
      default:
        return <ChevronRight className="status-icon default" size={16} />;
    }
  };

  const getEventIcon = (eventName: string) => {
    if (eventName.includes('tool_call')) return <Zap size={14} />;
    if (eventName.includes('plan')) return <Activity size={14} />;
    if (eventName.includes('route')) return <ChevronRight size={14} />;
    return null;
  };

  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString('en-US', { 
        hour12: false, 
        hour: '2-digit', 
        minute: '2-digit', 
        second: '2-digit',
        fractionalSecondDigits: 3
      });
    } catch {
      return timestamp;
    }
  };

  const formatDuration = (ms?: number) => {
    if (!ms) return null;
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(2)}s`;
  };

  return (
    <>
      <div className="trace-overlay" onClick={onClose} />
      <div className="trace-viewer">
        <div className="trace-header">
          <div className="trace-header-content">
            <Activity size={20} className="trace-header-icon" />
            <div>
              <h2 className="trace-title">Execution Trace</h2>
              {threadId && (
                <p className="trace-subtitle">Thread: {threadId.slice(0, 8)}</p>
              )}
            </div>
          </div>
          <button onClick={onClose} className="trace-close">
            <X size={20} />
          </button>
        </div>

        <div className="trace-stats">
          <div className="stat-item">
            <span className="stat-label">Events</span>
            <span className="stat-value">{trace.length}</span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Success</span>
            <span className="stat-value success">
              {trace.filter(e => e.status === 'success').length}
            </span>
          </div>
          <div className="stat-item">
            <span className="stat-label">Errors</span>
            <span className="stat-value error">
              {trace.filter(e => e.status === 'error').length}
            </span>
          </div>
        </div>

        <div className="trace-body">
          {trace.length === 0 ? (
            <div className="trace-empty">
              <Activity size={32} className="empty-icon" />
              <p>No trace events yet</p>
              <p className="empty-subtitle">Events will appear as actions are executed</p>
            </div>
          ) : (
            <div className="trace-timeline">
              {trace.map((event, idx) => {
                const isExpanded = expandedEvents.has(idx);
                const hasDetails = Object.keys(event.details || {}).length > 0;
                
                return (
                  <div key={idx} className={`trace-event ${event.status || ''}`}>
                    <div className="event-line" />
                    
                    <div className="event-content">
                      <div 
                        className="event-header"
                        onClick={() => hasDetails && toggleExpanded(idx)}
                        style={{ cursor: hasDetails ? 'pointer' : 'default' }}
                      >
                        <div className="event-header-left">
                          {getStatusIcon(event.status)}
                          {getEventIcon(event.event) && (
                            <span className="event-type-icon">
                              {getEventIcon(event.event)}
                            </span>
                          )}
                          <span className="event-name">{event.event}</span>
                          {event.tool_name && (
                            <code className="event-tool">{event.tool_name}</code>
                          )}
                        </div>
                        
                        <div className="event-header-right">
                          {event.duration_ms && (
                            <span className="event-duration">
                              {formatDuration(event.duration_ms)}
                            </span>
                          )}
                          <span className="event-timestamp">
                            {formatTimestamp(event.timestamp)}
                          </span>
                          {hasDetails && (
                            <span className="event-expand">
                              {isExpanded ? (
                                <ChevronDown size={14} />
                              ) : (
                                <ChevronRight size={14} />
                              )}
                            </span>
                          )}
                        </div>
                      </div>

                      {isExpanded && hasDetails && (
                        <div className="event-details">
                          <pre className="details-pre">
                            {JSON.stringify(event.details, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      <style jsx>{`
        .trace-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.3);
          z-index: 1000;
        }

        .trace-viewer {
          position: fixed;
          right: 0;
          top: 0;
          height: 100vh;
          width: 450px;
          background: white;
          box-shadow: -4px 0 16px rgba(0, 0, 0, 0.1);
          z-index: 1001;
          display: flex;
          flex-direction: column;
          animation: slideIn 0.3s ease;
        }

        @keyframes slideIn {
          from {
            transform: translateX(100%);
          }
          to {
            transform: translateX(0);
          }
        }

        .trace-header {
          padding: 1.25rem;
          border-bottom: 1px solid #e5e7eb;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          background: #f8fafc;
        }

        .trace-header-content {
          display: flex;
          gap: 0.75rem;
          align-items: flex-start;
        }

        .trace-header-icon {
          color: #0f62fe;
          flex-shrink: 0;
        }

        .trace-title {
          font-size: 1.125rem;
          font-weight: 600;
          color: #1e293b;
          margin: 0;
        }

        .trace-subtitle {
          font-size: 0.75rem;
          color: #64748b;
          margin: 0.25rem 0 0 0;
          font-family: 'Monaco', 'Courier New', monospace;
        }

        .trace-close {
          background: transparent;
          border: none;
          color: #64748b;
          cursor: pointer;
          padding: 0.25rem;
          border-radius: 4px;
          display: flex;
          align-items: center;
        }

        .trace-close:hover {
          background: #e2e8f0;
          color: #1e293b;
        }

        .trace-stats {
          display: flex;
          gap: 1rem;
          padding: 1rem 1.25rem;
          border-bottom: 1px solid #e5e7eb;
          background: white;
        }

        .stat-item {
          display: flex;
          flex-direction: column;
          gap: 0.25rem;
        }

        .stat-label {
          font-size: 0.75rem;
          color: #64748b;
          text-transform: uppercase;
          font-weight: 500;
        }

        .stat-value {
          font-size: 1.25rem;
          font-weight: 600;
          color: #1e293b;
        }

        .stat-value.success {
          color: #16a34a;
        }

        .stat-value.error {
          color: #dc2626;
        }

        .trace-body {
          flex: 1;
          overflow-y: auto;
          padding: 1rem;
        }

        .trace-empty {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 3rem 1rem;
          text-align: center;
          color: #94a3b8;
        }

        .empty-icon {
          margin-bottom: 1rem;
          opacity: 0.5;
        }

        .empty-subtitle {
          font-size: 0.875rem;
          margin-top: 0.5rem;
        }

        .trace-timeline {
          position: relative;
        }

        .trace-event {
          position: relative;
          padding-left: 2rem;
          margin-bottom: 0.75rem;
        }

        .event-line {
          position: absolute;
          left: 8px;
          top: 24px;
          bottom: -12px;
          width: 2px;
          background: #e5e7eb;
        }

        .trace-event:last-child .event-line {
          display: none;
        }

        .event-content {
          background: #f8fafc;
          border: 1px solid #e2e8f0;
          border-radius: 6px;
          overflow: hidden;
        }

        .trace-event.success .event-content {
          border-left: 3px solid #16a34a;
        }

        .trace-event.error .event-content {
          border-left: 3px solid #dc2626;
        }

        .trace-event.running .event-content {
          border-left: 3px solid #0f62fe;
        }

        .event-header {
          padding: 0.75rem;
          display: flex;
          justify-content: space-between;
          align-items: center;
          gap: 0.75rem;
        }

        .event-header-left {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          flex: 1;
          min-width: 0;
        }

        .event-header-right {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          flex-shrink: 0;
        }

        .status-icon {
          flex-shrink: 0;
        }

        .status-icon.success {
          color: #16a34a;
        }

        .status-icon.error {
          color: #dc2626;
        }

        .status-icon.pending {
          color: #f59e0b;
        }

        .status-icon.running {
          color: #0f62fe;
          animation: pulse 1.5s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }

        .status-icon.default {
          color: #94a3b8;
        }

        .event-type-icon {
          color: #64748b;
          display: flex;
          align-items: center;
        }

        .event-name {
          font-size: 0.875rem;
          font-weight: 500;
          color: #1e293b;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .event-tool {
          background: #dbeafe;
          color: #1e40af;
          padding: 0.125rem 0.5rem;
          border-radius: 4px;
          font-size: 0.75rem;
          font-family: 'Monaco', 'Courier New', monospace;
        }

        .event-duration {
          font-size: 0.75rem;
          color: #0f62fe;
          font-weight: 500;
        }

        .event-timestamp {
          font-size: 0.75rem;
          color: #94a3b8;
          font-family: 'Monaco', 'Courier New', monospace;
        }

        .event-expand {
          color: #64748b;
          display: flex;
          align-items: center;
        }

        .event-details {
          border-top: 1px solid #e2e8f0;
          padding: 0.75rem;
          background: white;
        }

        .details-pre {
          margin: 0;
          font-size: 0.75rem;
          font-family: 'Monaco', 'Courier New', monospace;
          color: #334155;
          overflow-x: auto;
          white-space: pre-wrap;
          word-break: break-all;
        }

        @media (max-width: 768px) {
          .trace-viewer {
            width: 100%;
          }
        }
      `}</style>
    </>
  );
};

export default TraceViewer;
