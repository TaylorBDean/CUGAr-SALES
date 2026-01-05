/**
 * Backend Status Component
 * Displays connection status to Python backend
 */

import React, { useState, useEffect } from 'react';
import { Activity, AlertCircle, CheckCircle } from 'lucide-react';

interface BackendStatus {
  running: boolean;
  port: number;
}

export const BackendStatusIndicator: React.FC = () => {
  const [status, setStatus] = useState<BackendStatus | null>(null);
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    checkBackendStatus();
    const interval = setInterval(checkBackendStatus, 10000); // Check every 10s
    return () => clearInterval(interval);
  }, []);

  const checkBackendStatus = async () => {
    try {
      // Try to use Electron API if available
      if ((window as any).electronAPI?.getBackendStatus) {
        const electronStatus = await (window as any).electronAPI.getBackendStatus();
        setStatus(electronStatus);
        setIsChecking(false);
        return;
      }

      // Fallback: Try direct fetch
      const response = await fetch('http://localhost:8000/health', {
        method: 'GET',
        signal: AbortSignal.timeout(2000)
      });
      
      if (response.ok) {
        setStatus({ running: true, port: 8000 });
      } else {
        setStatus({ running: false, port: 8000 });
      }
    } catch (error) {
      setStatus({ running: false, port: 8000 });
    } finally {
      setIsChecking(false);
    }
  };

  if (isChecking) {
    return (
      <div className="backend-status checking" title="Checking backend...">
        <Activity size={14} className="status-icon spin" />
        <span className="status-text">Checking...</span>
      </div>
    );
  }

  if (!status || !status.running) {
    return (
      <div className="backend-status offline" title="Backend offline">
        <AlertCircle size={14} className="status-icon" />
        <span className="status-text">Backend Offline</span>
      </div>
    );
  }

  return (
    <div className="backend-status online" title={`Backend running on port ${status.port}`}>
      <CheckCircle size={14} className="status-icon" />
      <span className="status-text">Backend Ready</span>
    </div>
  );
};

// CSS for BackendStatusIndicator (to be added to StatusBar.css or global)
export const backendStatusStyles = `
.backend-status {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.25rem 0.75rem;
  border-radius: 4px;
  font-size: 0.75rem;
  font-weight: 500;
}

.backend-status.checking {
  background: #e0e0e0;
  color: #525252;
}

.backend-status.online {
  background: #d0e2ff;
  color: #0043ce;
}

.backend-status.offline {
  background: #fff1f1;
  color: #da1e28;
}

.backend-status .status-icon {
  flex-shrink: 0;
}

.backend-status .status-icon.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.backend-status .status-text {
  white-space: nowrap;
}
`;
