import { useState, Component, ErrorInfo, ReactNode, useCallback, useRef, useEffect } from "react";
import React from "react";
import { createRoot } from "react-dom/client";
import { CustomChat } from "./CustomChat";
import { ConfigHeader } from "./ConfigHeader";
import { LeftSidebar } from "./LeftSidebar";
import { StatusBar } from "./StatusBar";
import { WorkspacePanel } from "./WorkspacePanel";
import { FileAutocomplete } from "./FileAutocomplete";
import { GuidedTour, TourStep } from "./GuidedTour";
import { useTour } from "./useTour";
import { AdvancedTourButton } from "./AdvancedTourButton";
import { HelpCircle, Zap } from "lucide-react";
import "./AppLayout.css";
import "./mockApi";
import "./workspaceThrottle"; // Enforce 3-second minimum interval between workspace API calls
import { DataSourceConfig } from "./DataSourceConfig";
import QuickActionsPanel from "./components/QuickActionsPanel";
import { BackendStatusIndicator } from "./components/BackendStatusIndicator";
import { useKeyboardShortcuts, DEFAULT_SHORTCUTS } from "./hooks/useKeyboardShortcuts";
import { ApprovalDialog } from "./components/ApprovalDialog";
import { TraceViewer } from "./components/TraceViewer";
import { BudgetIndicator } from "./components/BudgetIndicator";
import { CapabilityStatus } from "./components/CapabilityStatus";
import { ErrorRecovery } from "./components/ErrorRecovery";
import { ProfileSelector } from "./components/ProfileSelector";

// Error Boundary Component
class ErrorBoundary extends Component<
  { children: ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("Error caught by boundary:", error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: "20px", textAlign: "center" }}>
          <h2>Something went wrong</h2>
          <p>{this.state.error?.message || "Unknown error"}</p>
          <button
            onClick={() => {
              this.setState({ hasError: false, error: null });
              window.location.reload();
            }}
          >
            Reload Page
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export function App() {
  const [globalVariables, setGlobalVariables] = useState<Record<string, any>>({});
  const [variablesHistory, setVariablesHistory] = useState<Array<{
    id: string;
    title: string;
    timestamp: number;
    variables: Record<string, any>;
  }>>([]);
  const [selectedAnswerId, setSelectedAnswerId] = useState<string | null>(null);
  const [workspacePanelOpen, setWorkspacePanelOpen] = useState(true);
  const [leftSidebarCollapsed, setLeftSidebarCollapsed] = useState(false);
  const [highlightedFile, setHighlightedFile] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<"conversations" | "variables" | "savedflows" | "datasources">("conversations");
  const [previousVariablesCount, setPreviousVariablesCount] = useState(0);
  const [previousHistoryLength, setPreviousHistoryLength] = useState(0);
  const [threadId, setThreadId] = useState<string>("");
  const leftSidebarRef = useRef<{ addConversation: (title: string) => void } | null>(null);
  // Initialize hasStartedChat from URL query parameter immediately
  const [hasStartedChat, setHasStartedChat] = useState(() => {
    const urlParams = new URLSearchParams(window.location.search);
    return urlParams.get('mode') === 'advanced';
  });
  const [showQuickActions, setShowQuickActions] = useState(false);
  const chatInputRef = useRef<{ sendMessage: (message: string) => void } | null>(null);

  // AGENTS.md Compliance State
  const [approvalRequest, setApprovalRequest] = useState<any>(null);
  const [showTraces, setShowTraces] = useState(false);
  const [traces, setTraces] = useState<any[]>([]);
  const [budgets, setBudgets] = useState<any[]>([]);
  const [errorState, setErrorState] = useState<any>(null);
  const [showCapabilityStatus, setShowCapabilityStatus] = useState(false);

  // Update URL when entering advanced mode
  useEffect(() => {
    if (hasStartedChat) {
      const url = new URL(window.location.href);
      url.searchParams.set('mode', 'advanced');
      window.history.replaceState({}, '', url.toString());
    }
  }, [hasStartedChat]);

  // AGENTS.md Compliance: Listen for approval requests
  useEffect(() => {
    const handleApprovalRequest = (event: CustomEvent) => {
      console.log('[App] Approval requested:', event.detail);
      setApprovalRequest(event.detail);
    };
    window.addEventListener('approval-requested' as any, handleApprovalRequest);
    return () => window.removeEventListener('approval-requested' as any, handleApprovalRequest);
  }, []);

  // AGENTS.md Compliance: Fetch traces when trace viewer is opened
  useEffect(() => {
    if (showTraces && threadId) {
      const fetchTraces = async () => {
        try {
          const response = await fetch(`http://localhost:8000/api/traces?session_id=${threadId}`);
          if (response.ok) {
            const data = await response.json();
            setTraces(data.events || []);
          }
        } catch (err) {
          console.warn('[App] Failed to fetch traces:', err);
          // Set mock traces for demo
          setTraces([
            {
              trace_id: threadId,
              event_id: '1',
              event_type: 'plan_created',
              timestamp: new Date().toISOString(),
              status: 'success',
              duration_ms: 120
            }
          ]);
        }
      };
      fetchTraces();
    }
  }, [showTraces, threadId]);

  // AGENTS.md Compliance: Poll budgets
  useEffect(() => {
    if (!hasStartedChat) return;
    
    const pollBudgets = async () => {
      try {
        const response = await fetch('http://localhost:8000/api/budgets');
        if (response.ok) {
          const data = await response.json();
          setBudgets(data);
        }
      } catch (err) {
        // Set mock budgets for demo
        setBudgets([
          { category: 'CRM', used: 5, limit: 20 },
          { category: 'AI', used: 12, limit: 50 }
        ]);
      }
    };
    
    pollBudgets();
    const interval = setInterval(pollBudgets, 5000);
    return () => clearInterval(interval);
  }, [hasStartedChat]);
  
  const { isTourActive, hasSeenTour, startTour, completeTour, skipTour, resetTour } = useTour();

  // Keyboard shortcuts
  useKeyboardShortcuts([
    {
      ...DEFAULT_SHORTCUTS.QUICK_ACTIONS,
      handler: () => setShowQuickActions(prev => !prev)
    },
    {
      ...DEFAULT_SHORTCUTS.TOGGLE_SIDEBAR,
      handler: () => setLeftSidebarCollapsed(prev => !prev)
    },
    {
      key: 't',
      ctrlKey: true,
      metaKey: true,
      description: 'Toggle trace viewer',
      handler: () => setShowTraces(prev => !prev)
    },
  ]);

  // Handle variables updates from CustomChat
  const handleVariablesUpdate = useCallback((variables: Record<string, any>, history: Array<any>) => {
    console.log('[App] handleVariablesUpdate called');
    console.log('[App] Variables keys:', Object.keys(variables));
    console.log('[App] History length:', history.length);
    console.log('[App] Previous variables count:', previousVariablesCount);
    console.log('[App] Previous history length:', previousHistoryLength);

    const currentVariablesCount = Object.keys(variables).length;
    const currentHistoryLength = history.length;

    setGlobalVariables(variables);
    setVariablesHistory(history);

    // Only switch to variables tab when there's new data (more variables or longer history)
    const hasNewVariables = currentVariablesCount > previousVariablesCount;
    const hasNewHistory = currentHistoryLength > previousHistoryLength;

    if (hasNewVariables || hasNewHistory) {
      console.log('[App] Switching to variables tab - new data detected');
      setActiveTab("variables");
    }

    // Update previous counts
    setPreviousVariablesCount(currentVariablesCount);
    setPreviousHistoryLength(currentHistoryLength);
  }, [previousVariablesCount, previousHistoryLength]);

  // Handle message sent from CustomChat
  const handleMessageSent = useCallback((message: string) => {
    console.log('[App] handleMessageSent called with message:', message);
    console.log('[App] leftSidebarRef.current:', leftSidebarRef.current);
    // Add a new conversation to the left sidebar
    if (leftSidebarRef.current) {
      const title = message.length > 50 ? message.substring(0, 50) + "..." : message;
      console.log('[App] Calling addConversation with title:', title);
      leftSidebarRef.current.addConversation(title);
    } else {
      console.log('[App] leftSidebarRef.current is null');
    }
    // Switch to conversations tab to show the new conversation
    setActiveTab("conversations");
  }, []);

  // Handle chat started state
  const handleChatStarted = useCallback((started: boolean) => {
    setHasStartedChat(started);
  }, []);

  const handleQuickActionSelect = useCallback((prompt: string) => {
    // Send the prompt to chat
    // Trigger message send if CustomChat ref is available
    if (chatInputRef.current?.sendMessage) {
      chatInputRef.current.sendMessage(prompt);
    }
    // Close quick actions panel
    setShowQuickActions(false);
  }, []);

  // AGENTS.md Compliance: Approval handlers
  const handleApprove = useCallback(async (feedback?: string) => {
    try {
      await fetch('http://localhost:8000/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: approvalRequest?.requestId,
          approved: true,
          feedback
        })
      });
      console.log('[App] Approval sent');
    } catch (err) {
      console.error('[App] Failed to send approval:', err);
    }
    setApprovalRequest(null);
  }, [approvalRequest]);

  const handleReject = useCallback(async (reason?: string) => {
    try {
      await fetch('http://localhost:8000/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          request_id: approvalRequest?.requestId,
          approved: false,
          reason
        })
      });
      console.log('[App] Rejection sent');
    } catch (err) {
      console.error('[App] Failed to send rejection:', err);
    }
    setApprovalRequest(null);
  }, [approvalRequest]);

  // AGENTS.md Compliance: Error handlers
  const handleRetry = useCallback(() => {
    console.log('[App] Retrying operation');
    // Trigger retry logic
    setErrorState(null);
  }, []);

  const handleUsePartial = useCallback(() => {
    console.log('[App] Using partial results');
    // Use partial results
    setErrorState(null);
  }, []);

  // Define tour steps
  const tourSteps: TourStep[] = [
    {
      target: ".welcome-title",
      title: "Welcome to CUGA!",
      content: "CUGA is an intelligent digital agent that autonomously executes complex tasks through multi-agent orchestration, API integration, and code generation.",
      placement: "bottom",
      highlightPadding: 12,
    },
    {
      target: "#main-input_field",
      title: "Chat Input",
      content: "Type your requests here. You can ask CUGA to manage contacts, read files, send emails, or perform any complex task.",
      placement: "top",
      highlightPadding: 10,
    },
    {
      target: "#main-input_field",
      title: "File Tagging with @",
      content: "Type @ followed by a file name to tag files in your message. This allows CUGA to access and work with specific files from your workspace.",
      placement: "top",
      highlightPadding: 10,
    },
    {
      target: ".example-utterances-widget",
      title: "Try Example Queries",
      content: "Click any of these example queries to get started quickly. These demonstrate the types of tasks CUGA can handle.",
      placement: "top",
      highlightPadding: 12,
      beforeShow: () => {
        const input = document.getElementById("main-input_field");
        if (input) input.focus();
      },
    },
    {
      target: ".welcome-features",
      title: "Key Features",
      content: "CUGA offers multi-agent coordination, secure code execution, API integration, and smart memory to handle complex workflows.",
      placement: "top",
      highlightPadding: 12,
    },
  ];

  // Disabled: Tour no longer starts automatically on welcome screen
  // Start tour automatically for first-time users after a delay
  // useEffect(() => {
  //   if (!hasSeenTour && !hasStartedChat) {
  //     const timer = setTimeout(() => {
  //       startTour();
  //     }, 1000);
  //     return () => clearTimeout(timer);
  //   }
  // }, [hasSeenTour, hasStartedChat, startTour]);

  return (
    <ErrorBoundary>
      <div className={`app-layout ${!hasStartedChat ? 'welcome-mode' : ''}`}>
        {hasStartedChat && (
          <ConfigHeader
            onToggleLeftSidebar={() => setLeftSidebarCollapsed(!leftSidebarCollapsed)}
            onToggleWorkspace={() => setWorkspacePanelOpen(!workspacePanelOpen)}
            leftSidebarCollapsed={leftSidebarCollapsed}
            workspaceOpen={workspacePanelOpen}
          />
        )}
        <div className="main-layout">
          {hasStartedChat && (
            <LeftSidebar
              globalVariables={globalVariables}
              variablesHistory={variablesHistory}
              selectedAnswerId={selectedAnswerId}
              onSelectAnswer={setSelectedAnswerId}
              isCollapsed={leftSidebarCollapsed}
              activeTab={activeTab}
              onTabChange={setActiveTab}
              leftSidebarRef={leftSidebarRef}
            />
          )}
          <div className="chat-container">
            {activeTab === "datasources" ? (
              <DataSourceConfig />
            ) : (
              <>
                <CustomChat
                  onVariablesUpdate={handleVariablesUpdate}
                  onFileAutocompleteOpen={() => setWorkspacePanelOpen(true)}
                  onFileHover={setHighlightedFile}
                  onMessageSent={handleMessageSent}
                  onChatStarted={handleChatStarted}
                  initialChatStarted={hasStartedChat}
                  onThreadIdChange={setThreadId}
                />
                {/* Quick Actions Button - Floating */}
                {hasStartedChat && (
                  <button
                    className="quick-actions-fab"
                    onClick={() => setShowQuickActions(!showQuickActions)}
                    title="Quick Actions (Cmd/Ctrl + K)"
                  >
                    <Zap size={20} />
                  </button>
                )}
              </>
            )}
          </div>
          {hasStartedChat && (
            <WorkspacePanel
              isOpen={workspacePanelOpen}
              onToggle={() => setWorkspacePanelOpen(!workspacePanelOpen)}
              highlightedFile={highlightedFile}
            />
          )}
        </div>
        {hasStartedChat && (
          <div className="status-bar-wrapper">
            <StatusBar threadId={threadId} />
            {/* Budget Indicators */}
            <div className="budget-indicators">
              {budgets.map(budget => (
                <BudgetIndicator
                  key={budget.category}
                  used={budget.used}
                  limit={budget.limit}
                  category={budget.category}
                  size="sm"
                  showLabel={false}
                />
              ))}
            </div>
            {/* Profile Selector */}
            <ProfileSelector
              compact={true}
              onProfileChange={(profileId) => {
                console.log('[App] Profile changed to:', profileId);
                // Optionally reload app state or tools
              }}
            />
            {/* Capability Status Toggle */}
            <button
              className="capability-status-toggle"
              onClick={() => setShowCapabilityStatus(!showCapabilityStatus)}
              title="View Capability Health"
            >
              {showCapabilityStatus ? '✓' : '⚙'} Health
            </button>
            {/* Trace Viewer Toggle */}
            <button
              className="trace-viewer-toggle"
              onClick={() => setShowTraces(!showTraces)}
              title="View Execution Traces (Ctrl/Cmd+T)"
            >
              {showTraces ? '✓' : '📊'} Traces
            </button>
          </div>
        )}
        
        {/* Quick Actions Panel - Modal/Sidebar */}
        {showQuickActions && hasStartedChat && (
          <div className="quick-actions-overlay" onClick={() => setShowQuickActions(false)}>
            <div className="quick-actions-modal" onClick={(e) => e.stopPropagation()}>
              <QuickActionsPanel
                onActionSelect={handleQuickActionSelect}
                onClose={() => setShowQuickActions(false)}
              />
            </div>
          </div>
        )}

        {/* AGENTS.md Compliance: Capability Status Panel */}
        {showCapabilityStatus && hasStartedChat && (
          <div className="capability-status-overlay" onClick={() => setShowCapabilityStatus(false)}>
            <div className="capability-status-panel" onClick={(e) => e.stopPropagation()}>
              <CapabilityStatus autoRefresh={true} refreshInterval={30000} />
            </div>
          </div>
        )}

        {/* AGENTS.md Compliance: Trace Viewer Panel */}
        {showTraces && hasStartedChat && (
          <div className="trace-viewer-overlay" onClick={() => setShowTraces(false)}>
            <div className="trace-viewer-panel" onClick={(e) => e.stopPropagation()}>
              <TraceViewer
                traceId={threadId}
                events={traces}
                onClose={() => setShowTraces(false)}
              />
            </div>
          </div>
        )}

        {/* AGENTS.md Compliance: Approval Dialog */}
        {approvalRequest && (
          <ApprovalDialog
            request={approvalRequest}
            onApprove={handleApprove}
            onReject={handleReject}
            onCancel={() => setApprovalRequest(null)}
          />
        )}

        {/* AGENTS.md Compliance: Error Recovery */}
        {errorState && (
          <ErrorRecovery
            error={errorState.error}
            failureMode={errorState.failureMode}
            partialResult={errorState.partialResult}
            onRetry={handleRetry}
            onUsePartial={handleUsePartial}
            onCancel={() => setErrorState(null)}
            retryable={errorState.failureMode !== 'POLICY'}
          />
        )}
        
        <FileAutocomplete
          onFileSelect={(path) => console.log("File selected:", path)}
          onAutocompleteOpen={() => setWorkspacePanelOpen(true)}
          onFileHover={setHighlightedFile}
          disabled={false}
        />
        
        {/* Tour help button - welcome screen - DISABLED */}
        {/* {!hasStartedChat && hasSeenTour && (
          <button
            className="tour-help-button"
            onClick={resetTour}
            title="Restart Tour"
          >
            <HelpCircle size={20} />
          </button>
        )} */}
        
        {/* Advanced tour button - after chat started */}
        {hasStartedChat && <AdvancedTourButton />}
        
        {/* Guided Tour - only show when chat has started (disabled on welcome screen) */}
        {hasStartedChat && isTourActive && (
          <GuidedTour
            steps={tourSteps}
            isActive={isTourActive}
            onComplete={completeTour}
            onSkip={skipTour}
          />
        )}
      </div>
    </ErrorBoundary>
  );
}

export function BootstrapAgentic(contentRoot: HTMLElement) {
  // Create a root for React to render into.
  console.log("Bootstrapping Agentic Chat in sidepanel");
  const root = createRoot(contentRoot);
  // Render the App component into the root.
  root.render(
      <App />
  );
}