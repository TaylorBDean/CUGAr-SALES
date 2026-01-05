/**
 * Budget Indicator Component
 * Displays tool budget usage (AGENTS.md compliant)
 */

import React from 'react';
import { Activity, AlertTriangle } from 'lucide-react';

interface BudgetIndicatorProps {
  used: number;
  limit: number;
  category?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

export const BudgetIndicator: React.FC<BudgetIndicatorProps> = ({ 
  used, 
  limit, 
  category = 'Tool Calls',
  showLabel = true,
  size = 'md'
}) => {
  const percentage = Math.min((used / limit) * 100, 100);
  const isWarning = percentage > 70;
  const isCritical = percentage > 90;

  const sizeClasses = {
    sm: 'budget-sm',
    md: 'budget-md',
    lg: 'budget-lg'
  };

  return (
    <div className={`budget-indicator ${sizeClasses[size]}`}>
      {showLabel && (
        <div className="budget-header">
          <Activity className="budget-icon" />
          <span className="budget-category">{category}</span>
        </div>
      )}
      
      <div className="budget-bar-container">
        <div className="budget-bar">
          <div 
            className={`budget-fill ${isCritical ? 'critical' : isWarning ? 'warning' : 'normal'}`}
            style={{ width: `${percentage}%` }}
          />
        </div>
        <span className={`budget-text ${isCritical ? 'critical' : isWarning ? 'warning' : ''}`}>
          {used}/{limit}
        </span>
      </div>

      {isCritical && (
        <div className="budget-alert">
          <AlertTriangle size={12} />
          <span>Budget nearly exceeded</span>
        </div>
      )}

      <style jsx>{`
        .budget-indicator {
          display: flex;
          flex-direction: column;
          gap: 0.5rem;
        }

        .budget-sm {
          font-size: 0.75rem;
        }

        .budget-md {
          font-size: 0.875rem;
        }

        .budget-lg {
          font-size: 1rem;
        }

        .budget-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .budget-icon {
          width: 1em;
          height: 1em;
          color: #64748b;
          flex-shrink: 0;
        }

        .budget-category {
          color: #475569;
          font-weight: 500;
        }

        .budget-bar-container {
          display: flex;
          align-items: center;
          gap: 0.75rem;
        }

        .budget-bar {
          flex: 1;
          height: 0.5rem;
          background: #e2e8f0;
          border-radius: 9999px;
          overflow: hidden;
          min-width: 60px;
        }

        .budget-fill {
          height: 100%;
          transition: width 0.3s ease, background-color 0.3s ease;
          border-radius: 9999px;
        }

        .budget-fill.normal {
          background: linear-gradient(90deg, #16a34a, #22c55e);
        }

        .budget-fill.warning {
          background: linear-gradient(90deg, #f59e0b, #fbbf24);
        }

        .budget-fill.critical {
          background: linear-gradient(90deg, #dc2626, #ef4444);
          animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
          0%, 100% {
            opacity: 1;
          }
          50% {
            opacity: 0.8;
          }
        }

        .budget-text {
          font-family: 'Monaco', 'Courier New', monospace;
          font-size: 0.75em;
          color: #64748b;
          font-weight: 600;
          white-space: nowrap;
          flex-shrink: 0;
        }

        .budget-text.warning {
          color: #f59e0b;
        }

        .budget-text.critical {
          color: #dc2626;
        }

        .budget-alert {
          display: flex;
          align-items: center;
          gap: 0.375rem;
          padding: 0.375rem 0.625rem;
          background: #fef2f2;
          border: 1px solid #fecaca;
          border-radius: 4px;
          color: #dc2626;
          font-size: 0.75em;
        }
      `}</style>
    </div>
  );
};

export default BudgetIndicator;
