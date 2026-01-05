/**
 * Error Recovery Component
 * Handles partial results and retryable errors (AGENTS.md compliant)
 */

import React from 'react';
import { AlertTriangle, RefreshCw, CheckCircle, XCircle, AlertCircle } from 'lucide-react';

type FailureMode = 'AGENT' | 'SYSTEM' | 'RESOURCE' | 'POLICY' | 'USER';

interface PartialResult {
  completed: string[];
  failed: string[];
  data?: any;
}

interface ErrorRecoveryProps {
  error: Error;
  failureMode: FailureMode;
  partialResult?: PartialResult;
  onRetry?: () => void;
  onUsePartial?: () => void;
  onCancel?: () => void;
  retryable?: boolean;
}

const failureModeConfig: Record<FailureMode, {
  label: string;
  color: string;
  icon: React.ComponentType<{ size?: number; className?: string }>;
  description: string;
  retryRecommendation: string;
}> = {
  AGENT: {
    label: 'Agent Error',
    color: '#f59e0b',
    icon: AlertCircle,
    description: 'The agent encountered an issue processing your request.',
    retryRecommendation: 'Retry may succeed with adjusted parameters.'
  },
  SYSTEM: {
    label: 'System Error',
    color: '#dc2626',
    icon: XCircle,
    description: 'A system-level error occurred.',
    retryRecommendation: 'Retry may not succeed. Contact support if this persists.'
  },
  RESOURCE: {
    label: 'Resource Unavailable',
    color: '#f59e0b',
    icon: AlertTriangle,
    description: 'Required resources are temporarily unavailable.',
    retryRecommendation: 'Retry in a few moments.'
  },
  POLICY: {
    label: 'Policy Violation',
    color: '#dc2626',
    icon: AlertCircle,
    description: 'The request violates system policies or guardrails.',
    retryRecommendation: 'Retry will not succeed without modifying the request.'
  },
  USER: {
    label: 'User Error',
    color: '#0f62fe',
    icon: AlertCircle,
    description: 'The request contains invalid input or parameters.',
    retryRecommendation: 'Correct the input and retry.'
  }
};

export const ErrorRecovery: React.FC<ErrorRecoveryProps> = ({
  error,
  failureMode,
  partialResult,
  onRetry,
  onUsePartial,
  onCancel,
  retryable = true
}) => {
  const config = failureModeConfig[failureMode];
  const Icon = config.icon;
  const hasPartialResults = partialResult && partialResult.completed.length > 0;

  return (
    <div className="error-recovery">
      <div className="error-header" style={{ borderLeftColor: config.color }}>
        <Icon size={20} style={{ color: config.color }} />
        <div className="error-header-text">
          <h3 className="error-title">{config.label}</h3>
          <p className="error-description">{config.description}</p>
        </div>
      </div>

      <div className="error-details">
        <div className="error-message">
          <strong>Error:</strong> {error.message}
        </div>
        
        {partialResult && (
          <div className="partial-results-section">
            <h4 className="section-title">Execution Summary</h4>
            
            {partialResult.completed.length > 0 && (
              <div className="result-list">
                <div className="result-list-header">
                  <CheckCircle size={14} style={{ color: '#16a34a' }} />
                  <span className="result-list-title">Completed ({partialResult.completed.length})</span>
                </div>
                <ul className="result-items success">
                  {partialResult.completed.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {partialResult.failed.length > 0 && (
              <div className="result-list">
                <div className="result-list-header">
                  <XCircle size={14} style={{ color: '#dc2626' }} />
                  <span className="result-list-title">Failed ({partialResult.failed.length})</span>
                </div>
                <ul className="result-items failed">
                  {partialResult.failed.map((item, idx) => (
                    <li key={idx}>{item}</li>
                  ))}
                </ul>
              </div>
            )}

            {partialResult.data && (
              <details className="partial-data">
                <summary className="partial-data-summary">View partial data</summary>
                <pre className="partial-data-content">
                  {JSON.stringify(partialResult.data, null, 2)}
                </pre>
              </details>
            )}
          </div>
        )}

        <div className="recovery-recommendation">
          <strong>Recommendation:</strong> {config.retryRecommendation}
        </div>
      </div>

      <div className="error-actions">
        {retryable && onRetry && (
          <button 
            onClick={onRetry}
            className="btn btn-primary"
          >
            <RefreshCw size={14} />
            <span>Retry</span>
          </button>
        )}

        {hasPartialResults && onUsePartial && (
          <button 
            onClick={onUsePartial}
            className="btn btn-secondary"
          >
            <CheckCircle size={14} />
            <span>Use Partial Results</span>
          </button>
        )}

        {onCancel && (
          <button 
            onClick={onCancel}
            className="btn btn-tertiary"
          >
            Cancel
          </button>
        )}
      </div>

      <style jsx>{`
        .error-recovery {
          background: white;
          border-radius: 8px;
          border: 1px solid #e5e7eb;
          overflow: hidden;
          max-width: 600px;
        }

        .error-header {
          padding: 1rem;
          border-left: 4px solid;
          display: flex;
          gap: 0.75rem;
          align-items: flex-start;
          background: #fef2f2;
        }

        .error-header-text {
          flex: 1;
        }

        .error-title {
          margin: 0 0 0.25rem 0;
          font-size: 1rem;
          font-weight: 600;
          color: #1e293b;
        }

        .error-description {
          margin: 0;
          font-size: 0.875rem;
          color: #64748b;
          line-height: 1.4;
        }

        .error-details {
          padding: 1rem;
          display: flex;
          flex-direction: column;
          gap: 1rem;
        }

        .error-message {
          padding: 0.75rem;
          background: #f8fafc;
          border-radius: 4px;
          font-size: 0.875rem;
          color: #334155;
          word-wrap: break-word;
        }

        .error-message strong {
          color: #1e293b;
        }

        .partial-results-section {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
        }

        .section-title {
          margin: 0 0 0.5rem 0;
          font-size: 0.875rem;
          font-weight: 600;
          color: #475569;
        }

        .result-list {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .result-list-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .result-list-title {
          font-size: 0.8125rem;
          font-weight: 600;
          color: #475569;
        }

        .result-items {
          list-style: none;
          padding: 0;
          margin: 0;
          font-size: 0.8125rem;
          padding-left: 1.5rem;
        }

        .result-items li {
          padding: 0.25rem 0;
        }

        .result-items.success {
          color: #166534;
        }

        .result-items.failed {
          color: #991b1b;
        }

        .partial-data {
          margin-top: 0.5rem;
        }

        .partial-data-summary {
          cursor: pointer;
          font-size: 0.8125rem;
          color: #0f62fe;
          font-weight: 500;
          user-select: none;
        }

        .partial-data-summary:hover {
          text-decoration: underline;
        }

        .partial-data-content {
          margin: 0.5rem 0 0 0;
          padding: 0.75rem;
          background: #f8fafc;
          border-radius: 4px;
          font-size: 0.75rem;
          overflow-x: auto;
          max-height: 200px;
          overflow-y: auto;
        }

        .recovery-recommendation {
          padding: 0.75rem;
          background: #eff6ff;
          border: 1px solid #bfdbfe;
          border-radius: 4px;
          font-size: 0.875rem;
          color: #1e40af;
        }

        .recovery-recommendation strong {
          color: #1e3a8a;
        }

        .error-actions {
          padding: 1rem;
          border-top: 1px solid #e5e7eb;
          display: flex;
          gap: 0.75rem;
          justify-content: flex-end;
          background: #f8fafc;
        }

        .btn {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.5rem 1rem;
          border-radius: 6px;
          font-size: 0.875rem;
          font-weight: 500;
          cursor: pointer;
          transition: all 0.2s;
          border: none;
        }

        .btn-primary {
          background: #0f62fe;
          color: white;
        }

        .btn-primary:hover {
          background: #0353e9;
        }

        .btn-secondary {
          background: #16a34a;
          color: white;
        }

        .btn-secondary:hover {
          background: #15803d;
        }

        .btn-tertiary {
          background: transparent;
          color: #64748b;
          border: 1px solid #cbd5e1;
        }

        .btn-tertiary:hover {
          background: #f1f5f9;
          color: #475569;
        }
      `}</style>
    </div>
  );
};

export default ErrorRecovery;
