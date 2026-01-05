/**
 * Approval Dialog Component
 * Human-in-the-loop for irreversible actions (AGENTS.md compliant)
 */

import React, { useState } from 'react';
import { AlertCircle, CheckCircle, XCircle, Info } from 'lucide-react';

export interface ApprovalRequest {
  action: string;
  reasoning: string;
  risk_level: 'low' | 'medium' | 'high';
  tool_name: string;
  inputs: Record<string, any>;
  consequences: string[];
  trace_id?: string;
}

interface ApprovalDialogProps {
  request: ApprovalRequest;
  onApprove: () => void;
  onReject: () => void;
  onCancel: () => void;
  isOpen: boolean;
}

export const ApprovalDialog: React.FC<ApprovalDialogProps> = ({
  request,
  onApprove,
  onReject,
  onCancel,
  isOpen
}) => {
  const [feedback, setFeedback] = useState('');

  if (!isOpen) return null;

  const riskConfig = {
    low: {
      color: 'text-green-600',
      bgColor: 'bg-green-50',
      borderColor: 'border-green-200',
      icon: Info
    },
    medium: {
      color: 'text-yellow-600',
      bgColor: 'bg-yellow-50',
      borderColor: 'border-yellow-200',
      icon: AlertCircle
    },
    high: {
      color: 'text-red-600',
      bgColor: 'bg-red-50',
      borderColor: 'border-red-200',
      icon: AlertCircle
    }
  };

  const config = riskConfig[request.risk_level];
  const RiskIcon = config.icon;

  const handleApprove = () => {
    // Log approval for audit trail
    console.log('[Approval] User approved:', {
      tool: request.tool_name,
      trace_id: request.trace_id,
      feedback,
      timestamp: new Date().toISOString()
    });
    onApprove();
  };

  const handleReject = () => {
    // Log rejection for audit trail
    console.log('[Approval] User rejected:', {
      tool: request.tool_name,
      trace_id: request.trace_id,
      feedback,
      timestamp: new Date().toISOString()
    });
    onReject();
  };

  return (
    <div className="approval-overlay" onClick={onCancel}>
      <div className="approval-dialog" onClick={(e) => e.stopPropagation()}>
        <div className={`approval-header ${config.bgColor} ${config.borderColor}`}>
          <div className="approval-header-content">
            <RiskIcon className={`approval-icon ${config.color}`} size={24} />
            <div>
              <h2 className="approval-title">Approval Required</h2>
              <p className="approval-subtitle">
                This action requires human confirmation
              </p>
            </div>
          </div>
          <div className={`risk-badge ${config.bgColor} ${config.color}`}>
            {request.risk_level.toUpperCase()}
          </div>
        </div>

        <div className="approval-body">
          <div className="approval-section">
            <h3 className="section-title">Tool</h3>
            <code className="tool-name">{request.tool_name}</code>
          </div>

          <div className="approval-section">
            <h3 className="section-title">Proposed Action</h3>
            <p className="section-text">{request.action}</p>
          </div>

          <div className="approval-section">
            <h3 className="section-title">Reasoning</h3>
            <p className="section-text">{request.reasoning}</p>
          </div>

          <div className="approval-section">
            <h3 className="section-title">Consequences</h3>
            <ul className="consequences-list">
              {request.consequences.map((consequence, idx) => (
                <li key={idx} className="consequence-item">
                  {consequence}
                </li>
              ))}
            </ul>
          </div>

          <div className="approval-section">
            <h3 className="section-title">Parameters</h3>
            <pre className="parameters-pre">
              {JSON.stringify(request.inputs, null, 2)}
            </pre>
          </div>

          <div className="approval-section">
            <h3 className="section-title">Your Feedback (Optional)</h3>
            <textarea
              className="feedback-textarea"
              placeholder="Add any notes about your decision..."
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              rows={3}
            />
          </div>
        </div>

        <div className="approval-footer">
          <button
            onClick={handleApprove}
            className="btn btn-approve"
          >
            <CheckCircle size={16} />
            Approve & Execute
          </button>
          <button
            onClick={handleReject}
            className="btn btn-reject"
          >
            <XCircle size={16} />
            Reject
          </button>
          <button
            onClick={onCancel}
            className="btn btn-cancel"
          >
            Cancel
          </button>
        </div>
      </div>

      <style jsx>{`
        .approval-overlay {
          position: fixed;
          inset: 0;
          background: rgba(0, 0, 0, 0.6);
          display: flex;
          align-items: center;
          justify-content: center;
          z-index: 1100;
          padding: 1rem;
          animation: fadeIn 0.2s ease;
        }

        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }

        .approval-dialog {
          background: white;
          border-radius: 8px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
          max-width: 700px;
          width: 100%;
          max-height: 90vh;
          overflow: hidden;
          display: flex;
          flex-direction: column;
          animation: slideUp 0.3s ease;
        }

        @keyframes slideUp {
          from {
            transform: translateY(20px);
            opacity: 0;
          }
          to {
            transform: translateY(0);
            opacity: 1;
          }
        }

        .approval-header {
          padding: 1.5rem;
          border-bottom: 1px solid #e5e7eb;
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
        }

        .approval-header-content {
          display: flex;
          gap: 1rem;
          align-items: flex-start;
        }

        .approval-icon {
          flex-shrink: 0;
        }

        .approval-title {
          font-size: 1.25rem;
          font-weight: 600;
          color: #1e293b;
          margin: 0;
        }

        .approval-subtitle {
          font-size: 0.875rem;
          color: #64748b;
          margin: 0.25rem 0 0 0;
        }

        .risk-badge {
          padding: 0.25rem 0.75rem;
          border-radius: 9999px;
          font-size: 0.75rem;
          font-weight: 600;
          border: 1px solid;
        }

        .approval-body {
          flex: 1;
          overflow-y: auto;
          padding: 1.5rem;
        }

        .approval-section {
          margin-bottom: 1.5rem;
        }

        .section-title {
          font-size: 0.875rem;
          font-weight: 600;
          color: #1e293b;
          margin: 0 0 0.5rem 0;
        }

        .section-text {
          font-size: 0.875rem;
          color: #475569;
          line-height: 1.5;
          margin: 0;
        }

        .tool-name {
          background: #f1f5f9;
          padding: 0.5rem 0.75rem;
          border-radius: 4px;
          font-family: 'Monaco', 'Courier New', monospace;
          font-size: 0.875rem;
          color: #0f62fe;
          display: inline-block;
        }

        .consequences-list {
          list-style: none;
          padding: 0;
          margin: 0;
        }

        .consequence-item {
          padding: 0.5rem;
          background: #fef3c7;
          border-left: 3px solid #f59e0b;
          margin-bottom: 0.5rem;
          font-size: 0.875rem;
          color: #92400e;
        }

        .parameters-pre {
          background: #f8fafc;
          padding: 1rem;
          border-radius: 4px;
          font-family: 'Monaco', 'Courier New', monospace;
          font-size: 0.75rem;
          color: #334155;
          overflow-x: auto;
          margin: 0;
          border: 1px solid #e2e8f0;
        }

        .feedback-textarea {
          width: 100%;
          padding: 0.75rem;
          border: 1px solid #cbd5e1;
          border-radius: 4px;
          font-size: 0.875rem;
          font-family: inherit;
          resize: vertical;
        }

        .feedback-textarea:focus {
          outline: none;
          border-color: #0f62fe;
          box-shadow: 0 0 0 3px rgba(15, 98, 254, 0.1);
        }

        .approval-footer {
          padding: 1rem 1.5rem;
          border-top: 1px solid #e5e7eb;
          display: flex;
          gap: 0.75rem;
          background: #f8fafc;
        }

        .btn {
          display: flex;
          align-items: center;
          gap: 0.5rem;
          padding: 0.625rem 1.25rem;
          border-radius: 4px;
          font-size: 0.875rem;
          font-weight: 500;
          border: none;
          cursor: pointer;
          transition: all 0.2s;
        }

        .btn-approve {
          flex: 1;
          background: #16a34a;
          color: white;
        }

        .btn-approve:hover {
          background: #15803d;
        }

        .btn-reject {
          flex: 1;
          background: #dc2626;
          color: white;
        }

        .btn-reject:hover {
          background: #b91c1c;
        }

        .btn-cancel {
          background: #e2e8f0;
          color: #475569;
        }

        .btn-cancel:hover {
          background: #cbd5e1;
        }

        @media (max-width: 640px) {
          .approval-dialog {
            max-height: 95vh;
          }

          .approval-footer {
            flex-direction: column;
          }

          .btn {
            width: 100%;
          }
        }
      `}</style>
    </div>
  );
};

export default ApprovalDialog;
