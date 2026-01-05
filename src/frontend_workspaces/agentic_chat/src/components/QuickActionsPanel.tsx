/**
 * Quick Actions Panel Component
 * One-click access to common sales workflows
 */

import React, { useState } from 'react';
import { 
  Button, 
  Modal, 
  TextInput,
  Accordion,
  AccordionItem,
  Tag
} from '@carbon/react';
import { 
  Target, 
  Mail, 
  CheckSquare, 
  Search,
  Map,
  Zap
} from 'lucide-react';
import { 
  QUICK_ACTIONS, 
  CATEGORIES,
  QuickAction,
  fillPromptTemplate,
  validateContext,
  getActionsByCategory
} from '../config/quickActions';

interface QuickActionsPanelProps {
  onActionSelect: (prompt: string) => void;
  onClose?: () => void;
}

interface ContextInputs {
  [key: string]: string;
}

const ICON_MAP: { [key: string]: React.ComponentType } = {
  Target,
  Mail,
  CheckSquare,
  Search,
  Map,
  Zap
};

export const QuickActionsPanel: React.FC<QuickActionsPanelProps> = ({ 
  onActionSelect,
  onClose 
}) => {
  const [selectedAction, setSelectedAction] = useState<QuickAction | null>(null);
  const [contextInputs, setContextInputs] = useState<ContextInputs>({});
  const [searchQuery, setSearchQuery] = useState('');

  const handleActionClick = (action: QuickAction) => {
    if (!action.requiresContext || action.requiresContext.length === 0) {
      // No context needed, execute immediately
      onActionSelect(action.prompt);
      if (onClose) onClose();
    } else {
      // Need context, show modal
      setSelectedAction(action);
      setContextInputs({});
    }
  };

  const handleContextSubmit = () => {
    if (!selectedAction) return;

    const validation = validateContext(selectedAction, contextInputs);
    if (!validation.valid) {
      alert(`Missing required fields: ${validation.missing.join(', ')}`);
      return;
    }

    const filledPrompt = fillPromptTemplate(selectedAction.prompt, contextInputs);
    onActionSelect(filledPrompt);
    
    // Reset
    setSelectedAction(null);
    setContextInputs({});
    if (onClose) onClose();
  };

  const filteredActions = QUICK_ACTIONS.filter(action => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      action.title.toLowerCase().includes(query) ||
      action.description.toLowerCase().includes(query) ||
      action.category.toLowerCase().includes(query)
    );
  });

  const groupedActions = Object.entries(CATEGORIES).map(([key, meta]) => ({
    category: key,
    meta,
    actions: filteredActions.filter(a => a.category === key)
  })).filter(group => group.actions.length > 0);

  return (
    <div className="quick-actions-panel">
      <div className="quick-actions-header">
        <h3>Quick Actions</h3>
        <p>One-click workflows for common sales tasks</p>
      </div>

      <div className="quick-actions-search">
        <TextInput
          id="action-search"
          labelText="Search actions"
          placeholder="Find a workflow..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      <Accordion>
        {groupedActions.map(({ category, meta, actions }) => {
          const IconComponent = ICON_MAP[meta.icon] || Target;
          
          return (
            <AccordionItem
              key={category}
              title={
                <div className="category-header">
                  <IconComponent size={18} />
                  <span>{meta.label}</span>
                  <Tag type="gray" size="sm">{actions.length}</Tag>
                </div>
              }
            >
              <div className="action-list">
                {actions.map(action => {
                  const ActionIcon = ICON_MAP[action.icon] || Target;
                  
                  return (
                    <div 
                      key={action.id} 
                      className="action-card"
                      onClick={() => handleActionClick(action)}
                    >
                      <div className="action-icon">
                        <ActionIcon size={20} />
                      </div>
                      <div className="action-content">
                        <h4>{action.title}</h4>
                        <p>{action.description}</p>
                        {action.tools && (
                          <div className="action-tools">
                            {action.tools.slice(0, 2).map(tool => (
                              <Tag key={tool} type="blue" size="sm">
                                {tool.replace(/_/g, ' ')}
                              </Tag>
                            ))}
                            {action.tools.length > 2 && (
                              <Tag type="gray" size="sm">
                                +{action.tools.length - 2} more
                              </Tag>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </AccordionItem>
          );
        })}
      </Accordion>

      {/* Context Input Modal */}
      <Modal
        open={selectedAction !== null}
        onRequestClose={() => setSelectedAction(null)}
        modalHeading={selectedAction?.title}
        modalLabel="Quick Action"
        primaryButtonText="Execute"
        secondaryButtonText="Cancel"
        onRequestSubmit={handleContextSubmit}
        size="sm"
      >
        <p style={{ marginBottom: '1rem' }}>
          {selectedAction?.description}
        </p>
        
        {selectedAction?.requiresContext?.map(field => (
          <TextInput
            key={field}
            id={`context-${field}`}
            labelText={field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
            placeholder={`Enter ${field.replace(/_/g, ' ')}`}
            value={contextInputs[field] || ''}
            onChange={(e) => setContextInputs({
              ...contextInputs,
              [field]: e.target.value
            })}
            style={{ marginBottom: '1rem' }}
          />
        ))}
      </Modal>

      <style jsx>{`
        .quick-actions-panel {
          padding: 1rem;
          height: 100%;
          overflow-y: auto;
        }

        .quick-actions-header {
          margin-bottom: 1.5rem;
        }

        .quick-actions-header h3 {
          font-size: 1.25rem;
          font-weight: 600;
          margin-bottom: 0.25rem;
        }

        .quick-actions-header p {
          color: #525252;
          font-size: 0.875rem;
        }

        .quick-actions-search {
          margin-bottom: 1rem;
        }

        .category-header {
          display: flex;
          align-items: center;
          gap: 0.5rem;
        }

        .action-list {
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          padding: 0.5rem 0;
        }

        .action-card {
          display: flex;
          gap: 0.75rem;
          padding: 1rem;
          background: #f4f4f4;
          border-radius: 4px;
          cursor: pointer;
          transition: all 0.2s;
        }

        .action-card:hover {
          background: #e0e0e0;
          transform: translateY(-2px);
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }

        .action-icon {
          flex-shrink: 0;
          width: 40px;
          height: 40px;
          display: flex;
          align-items: center;
          justify-content: center;
          background: white;
          border-radius: 4px;
        }

        .action-content {
          flex: 1;
        }

        .action-content h4 {
          font-size: 0.875rem;
          font-weight: 600;
          margin-bottom: 0.25rem;
        }

        .action-content p {
          font-size: 0.75rem;
          color: #525252;
          margin-bottom: 0.5rem;
        }

        .action-tools {
          display: flex;
          gap: 0.25rem;
          flex-wrap: wrap;
        }
      `}</style>
    </div>
  );
};

export default QuickActionsPanel;
