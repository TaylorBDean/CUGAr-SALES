/**
 * Capability Status Component
 * Shows adapter health and graceful degradation (AGENTS.md compliant)
 */

import React, { useEffect, useState } from 'react';
import { Circle, RefreshCw, AlertCircle, Info } from 'lucide-react';

interface Capability {
  name: string;
  domain: string;
  status: 'online' | 'degraded' | 'offline';
  adapter?: string;
  mode?: 'mock' | 'live';
  message?: string;
}

interface CapabilityStatusProps {
  autoRefresh?: boolean;
  refreshInterval?: number;
  compact?: boolean;
}

export const CapabilityStatus: React.FC<CapabilityStatusProps> = ({ 
  autoRefresh = true,
  refreshInterval = 30000,
  compact = false
}) => {
  const [capabilities, setCapabilities] = useState<Capability[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchCapabilities = async () => {
    try {
      setLoading(true);
      const response = await fetch('http://localhost:8000/api/capabilities/status');
      if (!response.ok) throw new Error('Failed to fetch capabilities');
      const data = await response.json();
      setCapabilities(data);
      setLastUpdate(new Date());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
      // Set mock data for demo
      setCapabilities([
        { name: 'score_account_fit', domain: 'intelligence', status: 'online', mode: 'mock' },
        { name: 'draft_outbound_message', domain: 'engagement', status: 'online', mode: 'mock' },
        { name: 'qualify_opportunity', domain: 'qualification', status: 'online', mode: 'mock' },
        { name: 'analyze_territory_coverage', domain: 'territory', status: 'online', mode: 'mock' },
        { name: 'retrieve_product_knowledge', domain: 'knowledge', status: 'online', mode: 'mock' }
      ]);
      setLastUpdate(new Date());
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchCapabilities();
    
    if (autoRefresh) {
      const interval = setInterval(fetchCapabilities, refreshInterval);
      return () => clearInterval(interval);
    }
  }, [autoRefresh, refreshInterval]);

  const statusConfig = {
    online: {
      color: '#16a34a',
      label: 'Online',
      icon: Circle
    },
    degraded: {
      color: '#f59e0b',
      label: 'Degraded',
      icon: AlertCircle
    },
    offline: {
      color: '#dc2626',
      label: 'Offline',
      icon: Circle
    }
  };

  const domainColors: Record<string, string> = {
    territory: '#8b5cf6',
    intelligence: '#0f62fe',
    knowledge: '#059669',
    engagement: '#dc2626',
    qualification: '#f59e0b',
    governance: '#64748b'
  };

  const groupedByDomain = capabilities.reduce((acc, cap) => {
    if (!acc[cap.domain]) acc[cap.domain] = [];
    acc[cap.domain].push(cap);
    return acc;
  }, {} as Record<string, Capability[]>);

  if (compact) {
    const onlineCount = capabilities.filter(c => c.status === 'online').length;
    const total = capabilities.length;
    const allOnline = onlineCount === total;

    return (
      <div className="capability-status-compact">
        <Circle 
          size={8} 
          className="status-dot"
          style={{ color: allOnline ? '#16a34a' : '#f59e0b', fill: 'currentColor' }}
        />
        <span className="status-text">
          {onlineCount}/{total} capabilities
        </span>
        {!allOnline && <AlertCircle size={12} style={{ color: '#f59e0b' }} />}

        <style jsx>{`
          .capability-status-compact {
            display: flex;
            align-items: center;
            gap: 0.375rem;
            font-size: 0.75rem;
            color: #64748b;
          }

          .status-dot {
            flex-shrink: 0;
          }

          .status-text {
            font-weight: 500;
          }
        `}</style>
      </div>
    );
  }

  return (
    <div className="capability-status">
      <div className="capability-header">
        <h3 className="capability-title">Capability Health</h3>
        <button 
          onClick={fetchCapabilities} 
          className="refresh-btn"
          disabled={loading}
          title="Refresh status"
        >
          <RefreshCw size={14} className={loading ? 'spinning' : ''} />
        </button>
      </div>

      {lastUpdate && (
        <div className="last-update">
          Last updated: {lastUpdate.toLocaleTimeString()}
        </div>
      )}

      {error && (
        <div className="error-banner">
          <AlertCircle size={14} />
          <span>Using mock data (backend unavailable)</span>
        </div>
      )}

      <div className="capability-body">
        {Object.entries(groupedByDomain).map(([domain, caps]) => (
          <div key={domain} className="domain-group">
            <div 
              className="domain-label"
              style={{ borderLeftColor: domainColors[domain] || '#64748b' }}
            >
              {domain}
            </div>
            <div className="capability-list">
              {caps.map((cap, idx) => {
                const config = statusConfig[cap.status];
                const StatusIcon = config.icon;

                return (
                  <div key={idx} className="capability-item">
                    <div className="capability-item-left">
                      <StatusIcon 
                        size={10} 
                        style={{ color: config.color, fill: 'currentColor' }}
                      />
                      <span className="capability-name">{cap.name}</span>
                    </div>
                    <div className="capability-item-right">
                      {cap.mode && (
                        <span className={`mode-badge ${cap.mode}`}>
                          {cap.mode}
                        </span>
                      )}
                      <span 
                        className="status-badge"
                        style={{ color: config.color }}
                      >
                        {config.label}
                      </span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        ))}
      </div>

      {capabilities.length === 0 && !loading && (
        <div className="empty-state">
          <Info size={24} className="empty-icon" />
          <p>No capabilities registered</p>
        </div>
      )}

      <style jsx>{`
        .capability-status {
          background: white;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
          overflow: hidden;
        }

        .capability-header {
          padding: 0.75rem 1rem;
          border-bottom: 1px solid #e5e7eb;
          display: flex;
          justify-content: space-between;
          align-items: center;
          background: #f8fafc;
        }

        .capability-title {
          font-size: 0.875rem;
          font-weight: 600;
          color: #1e293b;
          margin: 0;
        }

        .refresh-btn {
          background: transparent;
          border: none;
          color: #64748b;
          cursor: pointer;
          padding: 0.25rem;
          border-radius: 4px;
          display: flex;
          align-items: center;
        }

        .refresh-btn:hover:not(:disabled) {
          background: #e2e8f0;
          color: #1e293b;
        }

        .refresh-btn:disabled {
          opacity: 0.5;
          cursor: not-allowed;
        }

        .spinning {
          animation: spin 1s linear infinite;
        }

        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }

        .last-update {
          padding: 0.5rem 1rem;
          font-size: 0.75rem;
          color: #94a3b8;
          background: #fafafa;
          border-bottom: 1px solid #e5e7eb;
        }

        .error-banner {
          padding: 0.625rem 1rem;
          background: #fef3c7;
          color: #92400e;
          font-size: 0.75rem;
          display: flex;
          align-items: center;
          gap: 0.5rem;
          border-bottom: 1px solid #fde68a;
        }

        .capability-body {
          padding: 0.75rem;
          max-height: 400px;
          overflow-y: auto;
        }

        .domain-group {
          margin-bottom: 1rem;
        }

        .domain-group:last-child {
          margin-bottom: 0;
        }

        .domain-label {
          font-size: 0.75rem;
          font-weight: 600;
          color: #475569;
          text-transform: uppercase;
          padding-left: 0.5rem;
          border-left: 3px solid;
          margin-bottom: 0.5rem;
        }

        .capability-list {
          display: flex;
          flex-direction: column;
          gap: 0.375rem;
        }

        .capability-item {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding: 0.5rem 0.75rem;
          background: #f8fafc;
          border-radius: 4px;
          font-size: 0.75rem;
        }

        .capability-item-left {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          min-width: 0;
        }

        .capability-name {
          color: #334155;
          overflow: hidden;
          text-overflow: ellipsis;
          white-space: nowrap;
        }

        .capability-item-right {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          flex-shrink: 0;
        }

        .mode-badge {
          padding: 0.125rem 0.5rem;
          border-radius: 9999px;
          font-size: 0.65rem;
          font-weight: 600;
          text-transform: uppercase;
        }

        .mode-badge.mock {
          background: #dbeafe;
          color: #1e40af;
        }

        .mode-badge.live {
          background: #d1fae5;
          color: #065f46;
        }

        .status-badge {
          font-weight: 500;
          font-size: 0.7rem;
        }

        .empty-state {
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 2rem 1rem;
          color: #94a3b8;
          text-align: center;
        }

        .empty-icon {
          margin-bottom: 0.75rem;
          opacity: 0.5;
        }
      `}</style>
    </div>
  );
};

export default CapabilityStatus;
