import { useState, useEffect } from "react";
import { X, Save, Plus, Trash2, ChevronDown, ChevronUp } from "lucide-react";
import "./ConfigModal.css";
import React from "react";

interface IntentPolicy {
  id: string;
  name: string;
  policyType: "intent";
  enabled: boolean;
  intentPattern: string;
  action: "block" | "redirect" | "restrict";
  response?: string;
  allowedTopics?: string[];
  redirectTo?: string;
}

interface SOPPolicy {
  id: string;
  name: string;
  policyType: "sop";
  enabled: boolean;
  trigger: string;
  steps: string[];
  description: string;
}

interface SubAgentPolicy {
  id: string;
  name: string;
  policyType: "subagent";
  enabled: boolean;
  subAgentName: string;
  constraints: string[];
  allowedTools: string[];
  restrictions: string;
}

interface AppPolicy {
  id: string;
  name: string;
  policyType: "app";
  enabled: boolean;
  appName: string;
  instructions?: string;
  rules: string[];
  permissions: string[];
}

interface ToolGuard {
  id: string;
  name: string;
  policyType: "toolguard";
  enabled: boolean;
  toolName: string;
  guardType: "rate_limit" | "input_validation" | "output_filter" | "approval_required" | "time_restriction";
  config: {
    maxCallsPerMinute?: number;
    maxCallsPerHour?: number;
    inputValidationRules?: string[];
    outputFilterPatterns?: string[];
    approvers?: string[];
    allowedTimeRanges?: Array<{ start: string; end: string }>;
    requireConfirmation?: boolean;
  };
  description: string;
}

interface ToolEnrichment {
  id: string;
  name: string;
  policyType: "toolenrichment";
  enabled: boolean;
  toolName: string;
  customInstructions: string[];
  preExecutionPrompt?: string;
  postProcessingRules?: string;
  exampleUsages: string[];
  bestPractices: string[];
  contextHints?: string;
}

interface AnswerPolicy {
  id: string;
  name: string;
  policyType: "answer";
  enabled: boolean;
  responseFormat: "natural" | "json" | "structured" | "markdown";
  tone: "professional" | "casual" | "technical" | "friendly" | "formal";
  includeConfidence: boolean;
  includeSources: boolean;
  maxResponseLength?: number;
  jsonSchema?: string;
  customInstructions: string[];
  forbiddenPhrases: string[];
  requiredDisclaimer?: string;
}

interface PoliciesConfigData {
  enablePolicies: boolean;
  intentPolicies: IntentPolicy[];
  sopPolicies: SOPPolicy[];
  subAgentPolicies: SubAgentPolicy[];
  appPolicies: AppPolicy[];
  toolGuards: ToolGuard[];
  toolEnrichments: ToolEnrichment[];
  answerPolicies: AnswerPolicy[];
  strictMode: boolean;
  logViolations: boolean;
}

interface PoliciesConfigProps {
  onClose: () => void;
}

export default function PoliciesConfig({ onClose }: PoliciesConfigProps) {
  const [config, setConfig] = useState<PoliciesConfigData>({
    enablePolicies: true,
    intentPolicies: [],
    sopPolicies: [],
    subAgentPolicies: [],
    appPolicies: [],
    toolGuards: [],
    toolEnrichments: [],
    answerPolicies: [],
    strictMode: false,
    logViolations: true,
  });
  const [activeTab, setActiveTab] = useState<"intent" | "sop" | "subagent" | "app" | "toolguards" | "toolenrichments" | "answer">("intent");
  const [toolsSubTab, setToolsSubTab] = useState<"guards" | "enrichments">("guards");
  const [expandedPolicy, setExpandedPolicy] = useState<string | null>(null);
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");

  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const response = await fetch('/api/config/policies');
      if (response.ok) {
        const data = await response.json();
        setConfig({
          enablePolicies: data.enablePolicies ?? true,
          intentPolicies: data.intentPolicies ?? [],
          sopPolicies: data.sopPolicies ?? [],
          subAgentPolicies: data.subAgentPolicies ?? [],
          appPolicies: data.appPolicies ?? [],
          toolGuards: data.toolGuards ?? [],
          toolEnrichments: data.toolEnrichments ?? [],
          answerPolicies: data.answerPolicies ?? [],
          strictMode: data.strictMode ?? false,
          logViolations: data.logViolations ?? true,
        });
      }
    } catch (error) {
      console.error("Error loading config:", error);
    }
  };

  const saveConfig = async () => {
    setSaveStatus("saving");
    try {
      const response = await fetch('/api/config/policies', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      
      if (response.ok) {
        setSaveStatus("success");
        setTimeout(() => setSaveStatus("idle"), 2000);
      } else {
        setSaveStatus("error");
        setTimeout(() => setSaveStatus("idle"), 2000);
      }
    } catch (error) {
      setSaveStatus("error");
      setTimeout(() => setSaveStatus("idle"), 2000);
    }
  };

  const addIntentPolicy = () => {
    const newPolicy: IntentPolicy = {
      id: Date.now().toString(),
      name: "New Intent Policy",
      policyType: "intent",
      enabled: true,
      intentPattern: "",
      action: "block",
      response: "",
      allowedTopics: [],
    };
    setConfig({
      ...config,
      intentPolicies: [...config.intentPolicies, newPolicy],
    });
  };

  const addSOPPolicy = () => {
    const newPolicy: SOPPolicy = {
      id: Date.now().toString(),
      name: "New SOP",
      policyType: "sop",
      enabled: true,
      trigger: "",
      steps: [""],
      description: "",
    };
    setConfig({
      ...config,
      sopPolicies: [...config.sopPolicies, newPolicy],
    });
  };

  const addSubAgentPolicy = () => {
    const newPolicy: SubAgentPolicy = {
      id: Date.now().toString(),
      name: "New Sub-Agent Policy",
      policyType: "subagent",
      enabled: true,
      subAgentName: "",
      constraints: [],
      allowedTools: [],
      restrictions: "",
    };
    setConfig({
      ...config,
      subAgentPolicies: [...config.subAgentPolicies, newPolicy],
    });
  };

  const addAppPolicy = () => {
    const newPolicy: AppPolicy = {
      id: Date.now().toString(),
      name: "New App Policy",
      policyType: "app",
      enabled: true,
      appName: "",
      instructions: "",
      rules: [],
      permissions: [],
    };
    setConfig({
      ...config,
      appPolicies: [...config.appPolicies, newPolicy],
    });
  };

  const addToolGuard = () => {
    const newGuard: ToolGuard = {
      id: Date.now().toString(),
      name: "New Tool Guard",
      policyType: "toolguard",
      enabled: true,
      toolName: "",
      guardType: "rate_limit",
      config: {
        maxCallsPerMinute: 10,
        maxCallsPerHour: 100,
      },
      description: "",
    };
    setConfig({
      ...config,
      toolGuards: [...config.toolGuards, newGuard],
    });
  };

  const addAnswerPolicy = () => {
    const newPolicy: AnswerPolicy = {
      id: Date.now().toString(),
      name: "New Answer Policy",
      policyType: "answer",
      enabled: true,
      responseFormat: "natural",
      tone: "professional",
      includeConfidence: false,
      includeSources: false,
      customInstructions: [],
      forbiddenPhrases: [],
    };
    setConfig({
      ...config,
      answerPolicies: [...config.answerPolicies, newPolicy],
    });
  };

  const addToolEnrichment = () => {
    const newEnrichment: ToolEnrichment = {
      id: Date.now().toString(),
      name: "New Tool Enrichment",
      policyType: "toolenrichment",
      enabled: true,
      toolName: "",
      customInstructions: [],
      exampleUsages: [],
      bestPractices: [],
    };
    setConfig({
      ...config,
      toolEnrichments: [...config.toolEnrichments, newEnrichment],
    });
  };

  const updateIntentPolicy = (id: string, updates: Partial<IntentPolicy>) => {
    setConfig({
      ...config,
      intentPolicies: config.intentPolicies.map(policy =>
        policy.id === id ? { ...policy, ...updates } : policy
      ),
    });
  };

  const updateSOPPolicy = (id: string, updates: Partial<SOPPolicy>) => {
    setConfig({
      ...config,
      sopPolicies: config.sopPolicies.map(policy =>
        policy.id === id ? { ...policy, ...updates } : policy
      ),
    });
  };

  const updateSubAgentPolicy = (id: string, updates: Partial<SubAgentPolicy>) => {
    setConfig({
      ...config,
      subAgentPolicies: config.subAgentPolicies.map(policy =>
        policy.id === id ? { ...policy, ...updates } : policy
      ),
    });
  };

  const updateAppPolicy = (id: string, updates: Partial<AppPolicy>) => {
    setConfig({
      ...config,
      appPolicies: config.appPolicies.map(policy =>
        policy.id === id ? { ...policy, ...updates } : policy
      ),
    });
  };

  const updateToolGuard = (id: string, updates: Partial<ToolGuard>) => {
    setConfig({
      ...config,
      toolGuards: config.toolGuards.map(guard =>
        guard.id === id ? { ...guard, ...updates } : guard
      ),
    });
  };

  const updateAnswerPolicy = (id: string, updates: Partial<AnswerPolicy>) => {
    setConfig({
      ...config,
      answerPolicies: config.answerPolicies.map(policy =>
        policy.id === id ? { ...policy, ...updates } : policy
      ),
    });
  };

  const updateToolEnrichment = (id: string, updates: Partial<ToolEnrichment>) => {
    setConfig({
      ...config,
      toolEnrichments: config.toolEnrichments.map(enrichment =>
        enrichment.id === id ? { ...enrichment, ...updates } : enrichment
      ),
    });
  };

  const removePolicy = (id: string, type: "intent" | "sop" | "subagent" | "app" | "toolguards" | "toolenrichments" | "answer") => {
    switch (type) {
      case "intent":
        setConfig({ ...config, intentPolicies: config.intentPolicies.filter(p => p.id !== id) });
        break;
      case "sop":
        setConfig({ ...config, sopPolicies: config.sopPolicies.filter(p => p.id !== id) });
        break;
      case "subagent":
        setConfig({ ...config, subAgentPolicies: config.subAgentPolicies.filter(p => p.id !== id) });
        break;
      case "app":
        setConfig({ ...config, appPolicies: config.appPolicies.filter(p => p.id !== id) });
        break;
      case "toolguards":
        setConfig({ ...config, toolGuards: config.toolGuards.filter(p => p.id !== id) });
        break;
      case "toolenrichments":
        setConfig({ ...config, toolEnrichments: config.toolEnrichments.filter(p => p.id !== id) });
        break;
      case "answer":
        setConfig({ ...config, answerPolicies: config.answerPolicies.filter(p => p.id !== id) });
        break;
    }
  };

  return (
    <div className="config-modal-overlay" onClick={onClose}>
      <div className="config-modal" onClick={(e) => e.stopPropagation()}>
        <div className="config-modal-header">
          <h2>Policies Configuration</h2>
          <button className="config-modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="config-modal-tabs">
          <button
            className={`config-tab ${activeTab === "intent" ? "active" : ""}`}
            onClick={() => setActiveTab("intent")}
          >
            Intent Policies
          </button>
          <button
            className={`config-tab ${activeTab === "sop" ? "active" : ""}`}
            onClick={() => setActiveTab("sop")}
          >
            SOPs
          </button>
          <button
            className={`config-tab ${activeTab === "subagent" ? "active" : ""}`}
            onClick={() => setActiveTab("subagent")}
          >
            Sub-Agent Policies
          </button>
          <button
            className={`config-tab ${activeTab === "app" ? "active" : ""}`}
            onClick={() => setActiveTab("app")}
          >
            App Policies
          </button>
          <button
            className={`config-tab ${activeTab === "toolguards" || activeTab === "toolenrichments" ? "active" : ""}`}
            onClick={() => {
              setActiveTab("toolguards");
              setToolsSubTab("guards");
            }}
          >
            Tools
          </button>
          <button
            className={`config-tab ${activeTab === "answer" ? "active" : ""}`}
            onClick={() => setActiveTab("answer")}
          >
            Answer Policy
          </button>
        </div>

        <div className="config-modal-content">
          <div className="config-card">
            <h3>Global Settings</h3>
            <div className="config-form">
              <div className="form-group">
                <label className="checkbox-label">
                  <input
                    type="checkbox"
                    checked={config.enablePolicies}
                    onChange={(e) => setConfig({ ...config, enablePolicies: e.target.checked })}
                  />
                  <span>Enable All Policies</span>
                </label>
                <small>Master switch for all policy enforcement</small>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={config.strictMode}
                      onChange={(e) => setConfig({ ...config, strictMode: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <span>Strict Mode</span>
                  </label>
                  <small>Deny all actions not explicitly allowed</small>
                </div>

                <div className="form-group">
                  <label className="checkbox-label">
                    <input
                      type="checkbox"
                      checked={config.logViolations}
                      onChange={(e) => setConfig({ ...config, logViolations: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <span>Log Violations</span>
                  </label>
                  <small>Record all policy violations</small>
                </div>
              </div>
            </div>
          </div>

          {activeTab === "intent" && renderIntentPolicies()}
          {activeTab === "sop" && renderSOPPolicies()}
          {activeTab === "subagent" && renderSubAgentPolicies()}
          {activeTab === "app" && renderAppPolicies()}
          {(activeTab === "toolguards" || activeTab === "toolenrichments") && renderToolsSection()}
          {activeTab === "answer" && renderAnswerPolicies()}
        </div>

        <div className="config-modal-footer">
          <button className="cancel-btn" onClick={onClose}>
            Cancel
          </button>
          <button 
            className={`save-btn ${saveStatus}`}
            onClick={saveConfig}
            disabled={saveStatus === "saving"}
          >
            <Save size={16} />
            {saveStatus === "idle" && "Save Changes"}
            {saveStatus === "saving" && "Saving..."}
            {saveStatus === "success" && "Saved!"}
            {saveStatus === "error" && "Error!"}
          </button>
        </div>
      </div>
    </div>
  );

  function renderIntentPolicies() {
    return (
      <div className="config-card">
        <div className="section-header">
          <h3>Intent Blockers & Redirections</h3>
          <button className="add-btn" onClick={addIntentPolicy} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add Intent Policy
          </button>
        </div>
        
        <div className="sources-list">
          {config.intentPolicies.map((policy) => {
            const isExpanded = expandedPolicy === policy.id;
            return (
              <div key={policy.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={policy.enabled}
                      onChange={(e) => updateIntentPolicy(policy.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={policy.name}
                      onChange={(e) => updateIntentPolicy(policy.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="Policy Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : policy.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(policy.id, "intent")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-group">
                      <label>Intent Pattern</label>
                      <input
                        type="text"
                        value={policy.intentPattern}
                        onChange={(e) => updateIntentPolicy(policy.id, { intentPattern: e.target.value })}
                        placeholder="e.g., 'personal information', 'sensitive data'"
                        disabled={!config.enablePolicies}
                      />
                      <small>Keywords or phrases that trigger this policy</small>
                    </div>

                    <div className="form-group">
                      <label>Action</label>
                      <select
                        value={policy.action}
                        onChange={(e) => updateIntentPolicy(policy.id, { action: e.target.value as any })}
                        disabled={!config.enablePolicies}
                      >
                        <option value="block">Block</option>
                        <option value="redirect">Redirect</option>
                        <option value="restrict">Restrict to Topics</option>
                      </select>
                    </div>

                    {policy.action === "block" && (
                      <div className="form-group">
                        <label>Response Message</label>
                        <textarea
                          value={policy.response || ""}
                          onChange={(e) => updateIntentPolicy(policy.id, { response: e.target.value })}
                          placeholder="I cannot help with that request."
                          rows={2}
                          disabled={!config.enablePolicies}
                        />
                      </div>
                    )}

                    {policy.action === "redirect" && (
                      <div className="form-group">
                        <label>Redirect To</label>
                        <input
                          type="text"
                          value={policy.redirectTo || ""}
                          onChange={(e) => updateIntentPolicy(policy.id, { redirectTo: e.target.value })}
                          placeholder="Alternative response or agent"
                          disabled={!config.enablePolicies}
                        />
                      </div>
                    )}

                    {policy.action === "restrict" && (
                      <div className="form-group">
                        <label>Allowed Topics</label>
                        <input
                          type="text"
                          value={policy.allowedTopics?.join(", ") || ""}
                          onChange={(e) => updateIntentPolicy(policy.id, { 
                            allowedTopics: e.target.value.split(",").map(t => t.trim()).filter(t => t)
                          })}
                          placeholder="topic1, topic2, topic3"
                          disabled={!config.enablePolicies}
                        />
                        <small>Comma-separated list of allowed topics</small>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.intentPolicies.length === 0 && (
          <div className="empty-state">
            <p>No intent policies configured. Click "Add Intent Policy" to create one.</p>
          </div>
        )}
      </div>
    );
  }

  function renderSOPPolicies() {
    return (
      <div className="config-card">
        <div className="section-header">
          <h3>Standard Operating Procedures (SOPs)</h3>
          <button className="add-btn" onClick={addSOPPolicy} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add SOP
          </button>
        </div>
        
        <div className="sources-list">
          {config.sopPolicies.map((policy) => {
            const isExpanded = expandedPolicy === policy.id;
            return (
              <div key={policy.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={policy.enabled}
                      onChange={(e) => updateSOPPolicy(policy.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={policy.name}
                      onChange={(e) => updateSOPPolicy(policy.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="SOP Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : policy.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(policy.id, "sop")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  {!isExpanded && (
                    <div className="agent-summary">
                      <span className="agent-summary-item">{policy.steps.length} step{policy.steps.length !== 1 ? 's' : ''}</span>
                    </div>
                  )}
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-group">
                      <label>Description</label>
                      <textarea
                        value={policy.description}
                        onChange={(e) => updateSOPPolicy(policy.id, { description: e.target.value })}
                        placeholder="What this SOP is for..."
                        rows={2}
                        disabled={!config.enablePolicies}
                      />
                    </div>

                    <div className="form-group">
                      <label>Trigger Condition</label>
                      <input
                        type="text"
                        value={policy.trigger}
                        onChange={(e) => updateSOPPolicy(policy.id, { trigger: e.target.value })}
                        placeholder="When should this SOP be applied?"
                        disabled={!config.enablePolicies}
                      />
                      <small>Condition or keywords that activate this SOP</small>
                    </div>

                    <div className="form-group">
                      <div className="form-group-header">
                        <label>Steps (in order)</label>
                        <button
                          className="add-small-btn"
                          onClick={() => updateSOPPolicy(policy.id, { steps: [...policy.steps, ""] })}
                          disabled={!config.enablePolicies}
                        >
                          <Plus size={12} />
                          Add Step
                        </button>
                      </div>
                      <div className="policies-list">
                        {policy.steps.map((step, index) => (
                          <div key={index} className="policy-item">
                            <span style={{ fontWeight: "bold", marginRight: "8px" }}>{index + 1}.</span>
                            <textarea
                              value={step}
                              onChange={(e) => {
                                const newSteps = [...policy.steps];
                                newSteps[index] = e.target.value;
                                updateSOPPolicy(policy.id, { steps: newSteps });
                              }}
                              placeholder="Describe this step..."
                              rows={2}
                              disabled={!config.enablePolicies}
                            />
                            <button
                              className="remove-btn"
                              onClick={() => {
                                const newSteps = policy.steps.filter((_, i) => i !== index);
                                updateSOPPolicy(policy.id, { steps: newSteps });
                              }}
                              disabled={!config.enablePolicies}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.sopPolicies.length === 0 && (
          <div className="empty-state">
            <p>No SOPs configured. Click "Add SOP" to create one.</p>
          </div>
        )}
      </div>
    );
  }

  function renderSubAgentPolicies() {
    return (
      <div className="config-card">
        <div className="section-header">
          <h3>Sub-Agent Policies</h3>
          <button className="add-btn" onClick={addSubAgentPolicy} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add Sub-Agent Policy
          </button>
        </div>
        
        <div className="sources-list">
          {config.subAgentPolicies.map((policy) => {
            const isExpanded = expandedPolicy === policy.id;
            return (
              <div key={policy.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={policy.enabled}
                      onChange={(e) => updateSubAgentPolicy(policy.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={policy.name}
                      onChange={(e) => updateSubAgentPolicy(policy.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="Policy Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : policy.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(policy.id, "subagent")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-group">
                      <label>Sub-Agent Name</label>
                      <input
                        type="text"
                        value={policy.subAgentName}
                        onChange={(e) => updateSubAgentPolicy(policy.id, { subAgentName: e.target.value })}
                        placeholder="Which sub-agent does this apply to?"
                        disabled={!config.enablePolicies}
                      />
                    </div>

                    <div className="form-group">
                      <label>Restrictions</label>
                      <textarea
                        value={policy.restrictions}
                        onChange={(e) => updateSubAgentPolicy(policy.id, { restrictions: e.target.value })}
                        placeholder="General restrictions for this sub-agent..."
                        rows={2}
                        disabled={!config.enablePolicies}
                      />
                    </div>

                    <div className="form-group">
                      <label>Constraints</label>
                      <input
                        type="text"
                        value={policy.constraints.join(", ")}
                        onChange={(e) => updateSubAgentPolicy(policy.id, { 
                          constraints: e.target.value.split(",").map(c => c.trim()).filter(c => c)
                        })}
                        placeholder="constraint1, constraint2, constraint3"
                        disabled={!config.enablePolicies}
                      />
                      <small>Comma-separated behavioral constraints</small>
                    </div>

                    <div className="form-group">
                      <label>Allowed Tools</label>
                      <input
                        type="text"
                        value={policy.allowedTools.join(", ")}
                        onChange={(e) => updateSubAgentPolicy(policy.id, { 
                          allowedTools: e.target.value.split(",").map(t => t.trim()).filter(t => t)
                        })}
                        placeholder="tool1, tool2, tool3"
                        disabled={!config.enablePolicies}
                      />
                      <small>Tools this sub-agent is allowed to use</small>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.subAgentPolicies.length === 0 && (
          <div className="empty-state">
            <p>No sub-agent policies configured. Click "Add Sub-Agent Policy" to create one.</p>
          </div>
        )}
      </div>
    );
  }

  function renderAppPolicies() {
    return (
      <div className="config-card">
        <div className="section-header">
          <h3>Application Policies</h3>
          <button className="add-btn" onClick={addAppPolicy} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add App Policy
          </button>
        </div>
        
        <div className="sources-list">
          {config.appPolicies.map((policy) => {
            const isExpanded = expandedPolicy === policy.id;
            return (
              <div key={policy.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={policy.enabled}
                      onChange={(e) => updateAppPolicy(policy.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={policy.name}
                      onChange={(e) => updateAppPolicy(policy.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="Policy Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : policy.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(policy.id, "app")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-group">
                      <label>Application Name</label>
                      <input
                        type="text"
                        value={policy.appName}
                        onChange={(e) => updateAppPolicy(policy.id, { appName: e.target.value })}
                        placeholder="Which app does this apply to?"
                        disabled={!config.enablePolicies}
                      />
                    </div>

                    <div className="form-group">
                      <label>Instructions</label>
                      <textarea
                        value={policy.instructions || ""}
                        onChange={(e) => updateAppPolicy(policy.id, { instructions: e.target.value })}
                        placeholder="Specific instructions for how the agent should use this application..."
                        disabled={!config.enablePolicies}
                        rows={4}
                        style={{ resize: 'vertical', fontFamily: 'inherit' }}
                      />
                      <small>General guidance for using this app (separate from rules and permissions)</small>
                    </div>

                    <div className="form-group">
                      <label>Rules</label>
                      <input
                        type="text"
                        value={policy.rules.join(", ")}
                        onChange={(e) => updateAppPolicy(policy.id, { 
                          rules: e.target.value.split(",").map(r => r.trim()).filter(r => r)
                        })}
                        placeholder="rule1, rule2, rule3"
                        disabled={!config.enablePolicies}
                      />
                      <small>Comma-separated application rules</small>
                    </div>

                    <div className="form-group">
                      <label>Permissions</label>
                      <input
                        type="text"
                        value={policy.permissions.join(", ")}
                        onChange={(e) => updateAppPolicy(policy.id, { 
                          permissions: e.target.value.split(",").map(p => p.trim()).filter(p => p)
                        })}
                        placeholder="read, write, execute"
                        disabled={!config.enablePolicies}
                      />
                      <small>What the app is allowed to do</small>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.appPolicies.length === 0 && (
          <div className="empty-state">
            <p>No app policies configured. Click "Add App Policy" to create one.</p>
          </div>
        )}
      </div>
    );
  }

  function renderToolsSection() {
    return (
      <div className="config-card">
        <div className="config-modal-tabs" style={{ marginBottom: "16px" }}>
          <button
            className={`config-tab ${toolsSubTab === "guards" ? "active" : ""}`}
            onClick={() => setToolsSubTab("guards")}
          >
            Tool Guards
          </button>
          <button
            className={`config-tab ${toolsSubTab === "enrichments" ? "active" : ""}`}
            onClick={() => setToolsSubTab("enrichments")}
          >
            Tool Enrichment
          </button>
        </div>

        {toolsSubTab === "guards" ? renderToolGuards() : renderToolEnrichments()}
      </div>
    );
  }

  function renderToolGuards() {
    return (
      <>
        <div className="section-header">
          <h3>Tool Guards & Safety Rails</h3>
          <button className="add-btn" onClick={addToolGuard} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add Tool Guard
          </button>
        </div>
        
        <div className="sources-list">
          {config.toolGuards.map((guard) => {
            const isExpanded = expandedPolicy === guard.id;
            return (
              <div key={guard.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={guard.enabled}
                      onChange={(e) => updateToolGuard(guard.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={guard.name}
                      onChange={(e) => updateToolGuard(guard.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="Guard Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : guard.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(guard.id, "toolguards")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  {!isExpanded && (
                    <div className="agent-summary">
                      <span className="agent-summary-item">{guard.guardType.replace('_', ' ')}</span>
                      <span className="agent-summary-item">{guard.toolName || 'No tool set'}</span>
                    </div>
                  )}
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-group">
                      <label>Tool Name</label>
                      <input
                        type="text"
                        value={guard.toolName}
                        onChange={(e) => updateToolGuard(guard.id, { toolName: e.target.value })}
                        placeholder="e.g., web_search, file_system, send_email"
                        disabled={!config.enablePolicies}
                      />
                      <small>The specific tool this guard applies to</small>
                    </div>

                    <div className="form-group">
                      <label>Description</label>
                      <textarea
                        value={guard.description}
                        onChange={(e) => updateToolGuard(guard.id, { description: e.target.value })}
                        placeholder="What this guard does..."
                        rows={2}
                        disabled={!config.enablePolicies}
                      />
                    </div>

                    <div className="form-group">
                      <label>Guard Type</label>
                      <select
                        value={guard.guardType}
                        onChange={(e) => {
                          const newType = e.target.value as any;
                          let newConfig = {};
                          
                          switch (newType) {
                            case "rate_limit":
                              newConfig = { maxCallsPerMinute: 10, maxCallsPerHour: 100 };
                              break;
                            case "input_validation":
                              newConfig = { inputValidationRules: [] };
                              break;
                            case "output_filter":
                              newConfig = { outputFilterPatterns: [] };
                              break;
                            case "approval_required":
                              newConfig = { approvers: [], requireConfirmation: true };
                              break;
                            case "time_restriction":
                              newConfig = { allowedTimeRanges: [] };
                              break;
                          }
                          
                          updateToolGuard(guard.id, { guardType: newType, config: newConfig });
                        }}
                        disabled={!config.enablePolicies}
                      >
                        <option value="rate_limit">Rate Limit</option>
                        <option value="input_validation">Input Validation</option>
                        <option value="output_filter">Output Filter</option>
                        <option value="approval_required">Approval Required</option>
                        <option value="time_restriction">Time Restriction</option>
                      </select>
                      <small>Type of safety mechanism</small>
                    </div>

                    {guard.guardType === "rate_limit" && (
                      <div className="form-row">
                        <div className="form-group">
                          <label>Max Calls Per Minute</label>
                          <input
                            type="number"
                            value={guard.config.maxCallsPerMinute || 10}
                            onChange={(e) => updateToolGuard(guard.id, { 
                              config: { ...guard.config, maxCallsPerMinute: parseInt(e.target.value) }
                            })}
                            min="1"
                            disabled={!config.enablePolicies}
                          />
                        </div>
                        <div className="form-group">
                          <label>Max Calls Per Hour</label>
                          <input
                            type="number"
                            value={guard.config.maxCallsPerHour || 100}
                            onChange={(e) => updateToolGuard(guard.id, { 
                              config: { ...guard.config, maxCallsPerHour: parseInt(e.target.value) }
                            })}
                            min="1"
                            disabled={!config.enablePolicies}
                          />
                        </div>
                      </div>
                    )}

                    {guard.guardType === "input_validation" && (
                      <div className="form-group">
                        <label>Validation Rules</label>
                        <input
                          type="text"
                          value={guard.config.inputValidationRules?.join(", ") || ""}
                          onChange={(e) => updateToolGuard(guard.id, { 
                            config: { 
                              ...guard.config, 
                              inputValidationRules: e.target.value.split(",").map(r => r.trim()).filter(r => r)
                            }
                          })}
                          placeholder="no-urls, max-length-1000, alphanumeric-only"
                          disabled={!config.enablePolicies}
                        />
                        <small>Rules to validate input parameters (comma-separated)</small>
                      </div>
                    )}

                    {guard.guardType === "output_filter" && (
                      <div className="form-group">
                        <label>Filter Patterns</label>
                        <input
                          type="text"
                          value={guard.config.outputFilterPatterns?.join(", ") || ""}
                          onChange={(e) => updateToolGuard(guard.id, { 
                            config: { 
                              ...guard.config, 
                              outputFilterPatterns: e.target.value.split(",").map(p => p.trim()).filter(p => p)
                            }
                          })}
                          placeholder="password, api-key, credit-card, ssn"
                          disabled={!config.enablePolicies}
                        />
                        <small>Patterns to filter from tool output (comma-separated)</small>
                      </div>
                    )}

                    {guard.guardType === "approval_required" && (
                      <>
                        <div className="form-group">
                          <label>Approvers</label>
                          <input
                            type="text"
                            value={guard.config.approvers?.join(", ") || ""}
                            onChange={(e) => updateToolGuard(guard.id, { 
                              config: { 
                                ...guard.config, 
                                approvers: e.target.value.split(",").map(a => a.trim()).filter(a => a)
                              }
                            })}
                            placeholder="admin, manager, supervisor"
                            disabled={!config.enablePolicies}
                          />
                          <small>Who can approve tool execution (comma-separated)</small>
                        </div>
                        <div className="form-group">
                          <label className="checkbox-label">
                            <input
                              type="checkbox"
                              checked={guard.config.requireConfirmation || false}
                              onChange={(e) => updateToolGuard(guard.id, { 
                                config: { ...guard.config, requireConfirmation: e.target.checked }
                              })}
                              disabled={!config.enablePolicies}
                            />
                            <span>Require Explicit Confirmation</span>
                          </label>
                          <small>User must manually confirm each tool call</small>
                        </div>
                      </>
                    )}

                    {guard.guardType === "time_restriction" && (
                      <div className="form-group">
                        <label>Allowed Time Ranges</label>
                        <input
                          type="text"
                          value={guard.config.allowedTimeRanges?.map(r => `${r.start}-${r.end}`).join(", ") || ""}
                          onChange={(e) => {
                            const ranges = e.target.value.split(",").map(r => {
                              const [start, end] = r.trim().split("-");
                              return start && end ? { start: start.trim(), end: end.trim() } : null;
                            }).filter(r => r !== null) as Array<{ start: string; end: string }>;
                            
                            updateToolGuard(guard.id, { 
                              config: { ...guard.config, allowedTimeRanges: ranges }
                            });
                          }}
                          placeholder="09:00-17:00, 14:00-18:00"
                          disabled={!config.enablePolicies}
                        />
                        <small>Time ranges when tool can be used (HH:MM-HH:MM, comma-separated)</small>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.toolGuards.length === 0 && (
          <div className="empty-state">
            <p>No tool guards configured. Click "Add Tool Guard" to create one.</p>
          </div>
        )}
      </>
    );
  }

  function renderToolEnrichments() {
    return (
      <>
        <div className="section-header">
          <h3>Tool Enrichment & Custom Instructions</h3>
          <button className="add-btn" onClick={addToolEnrichment} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add Tool Enrichment
          </button>
        </div>
        
        <div className="sources-list">
          {config.toolEnrichments.map((enrichment) => {
            const isExpanded = expandedPolicy === enrichment.id;
            return (
              <div key={enrichment.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={enrichment.enabled}
                      onChange={(e) => updateToolEnrichment(enrichment.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={enrichment.name}
                      onChange={(e) => updateToolEnrichment(enrichment.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="Enrichment Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : enrichment.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(enrichment.id, "toolenrichments")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  {!isExpanded && (
                    <div className="agent-summary">
                      <span className="agent-summary-item">{enrichment.toolName || 'No tool set'}</span>
                      <span className="agent-summary-item">{enrichment.customInstructions.length} instruction{enrichment.customInstructions.length !== 1 ? 's' : ''}</span>
                    </div>
                  )}
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-group">
                      <label>Tool Name</label>
                      <input
                        type="text"
                        value={enrichment.toolName}
                        onChange={(e) => updateToolEnrichment(enrichment.id, { toolName: e.target.value })}
                        placeholder="e.g., web_search, file_system, send_email"
                        disabled={!config.enablePolicies}
                      />
                      <small>The specific tool this enrichment applies to</small>
                    </div>

                    <div className="form-group">
                      <label>Pre-Execution Prompt</label>
                      <textarea
                        value={enrichment.preExecutionPrompt || ""}
                        onChange={(e) => updateToolEnrichment(enrichment.id, { preExecutionPrompt: e.target.value })}
                        placeholder="Instructions to consider before using this tool..."
                        rows={3}
                        disabled={!config.enablePolicies}
                      />
                      <small>Guidance provided to the agent before executing the tool</small>
                    </div>

                    <div className="form-group">
                      <label>Post-Processing Rules</label>
                      <textarea
                        value={enrichment.postProcessingRules || ""}
                        onChange={(e) => updateToolEnrichment(enrichment.id, { postProcessingRules: e.target.value })}
                        placeholder="How to process or interpret the tool's output..."
                        rows={3}
                        disabled={!config.enablePolicies}
                      />
                      <small>Instructions for handling the tool's response</small>
                    </div>

                    <div className="form-group">
                      <label>Context Hints</label>
                      <textarea
                        value={enrichment.contextHints || ""}
                        onChange={(e) => updateToolEnrichment(enrichment.id, { contextHints: e.target.value })}
                        placeholder="When this tool is most useful, what context to consider..."
                        rows={2}
                        disabled={!config.enablePolicies}
                      />
                      <small>Contextual information about when and how to use this tool</small>
                    </div>

                    <div className="form-group">
                      <div className="form-group-header">
                        <label>Custom Instructions</label>
                        <button
                          className="add-small-btn"
                          onClick={() => updateToolEnrichment(enrichment.id, { customInstructions: [...enrichment.customInstructions, ""] })}
                          disabled={!config.enablePolicies}
                        >
                          <Plus size={12} />
                          Add Instruction
                        </button>
                      </div>
                      <small>Specific instructions for using this tool effectively</small>
                      <div className="policies-list">
                        {enrichment.customInstructions.map((instruction, index) => (
                          <div key={index} className="policy-item">
                            <textarea
                              value={instruction}
                              onChange={(e) => {
                                const newInstructions = [...enrichment.customInstructions];
                                newInstructions[index] = e.target.value;
                                updateToolEnrichment(enrichment.id, { customInstructions: newInstructions });
                              }}
                              placeholder="e.g., Always verify the search query is relevant before calling"
                              rows={2}
                              disabled={!config.enablePolicies}
                            />
                            <button
                              className="remove-btn"
                              onClick={() => {
                                const newInstructions = enrichment.customInstructions.filter((_, i) => i !== index);
                                updateToolEnrichment(enrichment.id, { customInstructions: newInstructions });
                              }}
                              disabled={!config.enablePolicies}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <div className="form-group-header">
                        <label>Example Usages</label>
                        <button
                          className="add-small-btn"
                          onClick={() => updateToolEnrichment(enrichment.id, { exampleUsages: [...enrichment.exampleUsages, ""] })}
                          disabled={!config.enablePolicies}
                        >
                          <Plus size={12} />
                          Add Example
                        </button>
                      </div>
                      <small>Example scenarios or use cases for this tool</small>
                      <div className="policies-list">
                        {enrichment.exampleUsages.map((example, index) => (
                          <div key={index} className="policy-item">
                            <textarea
                              value={example}
                              onChange={(e) => {
                                const newExamples = [...enrichment.exampleUsages];
                                newExamples[index] = e.target.value;
                                updateToolEnrichment(enrichment.id, { exampleUsages: newExamples });
                              }}
                              placeholder="e.g., Use when user asks about current weather in a specific location"
                              rows={2}
                              disabled={!config.enablePolicies}
                            />
                            <button
                              className="remove-btn"
                              onClick={() => {
                                const newExamples = enrichment.exampleUsages.filter((_, i) => i !== index);
                                updateToolEnrichment(enrichment.id, { exampleUsages: newExamples });
                              }}
                              disabled={!config.enablePolicies}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <div className="form-group-header">
                        <label>Best Practices</label>
                        <button
                          className="add-small-btn"
                          onClick={() => updateToolEnrichment(enrichment.id, { bestPractices: [...enrichment.bestPractices, ""] })}
                          disabled={!config.enablePolicies}
                        >
                          <Plus size={12} />
                          Add Practice
                        </button>
                      </div>
                      <small>Best practices and tips for optimal tool usage</small>
                      <div className="policies-list">
                        {enrichment.bestPractices.map((practice, index) => (
                          <div key={index} className="policy-item">
                            <input
                              type="text"
                              value={practice}
                              onChange={(e) => {
                                const newPractices = [...enrichment.bestPractices];
                                newPractices[index] = e.target.value;
                                updateToolEnrichment(enrichment.id, { bestPractices: newPractices });
                              }}
                              placeholder="e.g., Limit search results to top 5 for faster processing"
                              disabled={!config.enablePolicies}
                            />
                            <button
                              className="remove-btn"
                              onClick={() => {
                                const newPractices = enrichment.bestPractices.filter((_, i) => i !== index);
                                updateToolEnrichment(enrichment.id, { bestPractices: newPractices });
                              }}
                              disabled={!config.enablePolicies}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.toolEnrichments.length === 0 && (
          <div className="empty-state">
            <p>No tool enrichments configured. Click "Add Tool Enrichment" to create one.</p>
          </div>
        )}
      </>
    );
  }

  function renderAnswerPolicies() {
    return (
      <div className="config-card">
        <div className="section-header">
          <h3>Answer & Response Policies</h3>
          <button className="add-btn" onClick={addAnswerPolicy} disabled={!config.enablePolicies}>
            <Plus size={16} />
            Add Answer Policy
          </button>
        </div>
        
        <div className="sources-list">
          {config.answerPolicies.map((policy) => {
            const isExpanded = expandedPolicy === policy.id;
            return (
              <div key={policy.id} className="agent-config-card">
                <div className="agent-config-header">
                  <div className="agent-config-top">
                    <input
                      type="checkbox"
                      checked={policy.enabled}
                      onChange={(e) => updateAnswerPolicy(policy.id, { enabled: e.target.checked })}
                      disabled={!config.enablePolicies}
                    />
                    <input
                      type="text"
                      value={policy.name}
                      onChange={(e) => updateAnswerPolicy(policy.id, { name: e.target.value })}
                      className="agent-config-name"
                      placeholder="Policy Name"
                      disabled={!config.enablePolicies}
                    />
                    <button
                      className="expand-btn"
                      onClick={() => setExpandedPolicy(isExpanded ? null : policy.id)}
                    >
                      {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                    </button>
                    <button
                      className="delete-btn"
                      onClick={() => removePolicy(policy.id, "answer")}
                      disabled={!config.enablePolicies}
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                  {!isExpanded && (
                    <div className="agent-summary">
                      <span className="agent-summary-item">{policy.responseFormat}</span>
                      <span className="agent-summary-item">{policy.tone} tone</span>
                    </div>
                  )}
                </div>

                {isExpanded && (
                  <div className="agent-config-details">
                    <div className="form-row">
                      <div className="form-group">
                        <label>Response Format</label>
                        <select
                          value={policy.responseFormat}
                          onChange={(e) => updateAnswerPolicy(policy.id, { responseFormat: e.target.value as any })}
                          disabled={!config.enablePolicies}
                        >
                          <option value="natural">Natural Language</option>
                          <option value="json">JSON</option>
                          <option value="structured">Structured</option>
                          <option value="markdown">Markdown</option>
                        </select>
                        <small>How responses should be formatted</small>
                      </div>

                      <div className="form-group">
                        <label>Response Tone</label>
                        <select
                          value={policy.tone}
                          onChange={(e) => updateAnswerPolicy(policy.id, { tone: e.target.value as any })}
                          disabled={!config.enablePolicies}
                        >
                          <option value="professional">Professional</option>
                          <option value="casual">Casual</option>
                          <option value="technical">Technical</option>
                          <option value="friendly">Friendly</option>
                          <option value="formal">Formal</option>
                        </select>
                        <small>Communication style for responses</small>
                      </div>
                    </div>

                    {policy.responseFormat === "json" && (
                      <div className="form-group">
                        <label>JSON Schema</label>
                        <textarea
                          value={policy.jsonSchema || ""}
                          onChange={(e) => updateAnswerPolicy(policy.id, { jsonSchema: e.target.value })}
                          placeholder={'{\n  "type": "object",\n  "properties": {\n    "answer": { "type": "string" }\n  }\n}'}
                          rows={6}
                          disabled={!config.enablePolicies}
                          style={{ fontFamily: "monospace", fontSize: "12px" }}
                        />
                        <small>JSON schema that responses must adhere to</small>
                      </div>
                    )}

                    <div className="form-group">
                      <label>Max Response Length</label>
                      <input
                        type="number"
                        value={policy.maxResponseLength || ""}
                        onChange={(e) => updateAnswerPolicy(policy.id, { maxResponseLength: e.target.value ? parseInt(e.target.value) : undefined })}
                        placeholder="e.g., 500"
                        min="1"
                        disabled={!config.enablePolicies}
                      />
                      <small>Maximum number of characters (leave empty for no limit)</small>
                    </div>

                    <div className="form-row">
                      <div className="form-group">
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={policy.includeConfidence}
                            onChange={(e) => updateAnswerPolicy(policy.id, { includeConfidence: e.target.checked })}
                            disabled={!config.enablePolicies}
                          />
                          <span>Include Confidence Score</span>
                        </label>
                        <small>Add confidence level to responses</small>
                      </div>

                      <div className="form-group">
                        <label className="checkbox-label">
                          <input
                            type="checkbox"
                            checked={policy.includeSources}
                            onChange={(e) => updateAnswerPolicy(policy.id, { includeSources: e.target.checked })}
                            disabled={!config.enablePolicies}
                          />
                          <span>Include Sources</span>
                        </label>
                        <small>Cite information sources in responses</small>
                      </div>
                    </div>

                    <div className="form-group">
                      <label>Required Disclaimer</label>
                      <textarea
                        value={policy.requiredDisclaimer || ""}
                        onChange={(e) => updateAnswerPolicy(policy.id, { requiredDisclaimer: e.target.value })}
                        placeholder="Optional disclaimer to append to all responses..."
                        rows={2}
                        disabled={!config.enablePolicies}
                      />
                      <small>Text automatically added to every response</small>
                    </div>

                    <div className="form-group">
                      <div className="form-group-header">
                        <label>Custom Instructions</label>
                        <button
                          className="add-small-btn"
                          onClick={() => updateAnswerPolicy(policy.id, { customInstructions: [...policy.customInstructions, ""] })}
                          disabled={!config.enablePolicies}
                        >
                          <Plus size={12} />
                          Add Instruction
                        </button>
                      </div>
                      <small>Additional rules the agent must follow when responding</small>
                      <div className="policies-list">
                        {policy.customInstructions.map((instruction, index) => (
                          <div key={index} className="policy-item">
                            <input
                              type="text"
                              value={instruction}
                              onChange={(e) => {
                                const newInstructions = [...policy.customInstructions];
                                newInstructions[index] = e.target.value;
                                updateAnswerPolicy(policy.id, { customInstructions: newInstructions });
                              }}
                              placeholder="e.g., Always include a summary at the start"
                              disabled={!config.enablePolicies}
                            />
                            <button
                              className="remove-btn"
                              onClick={() => {
                                const newInstructions = policy.customInstructions.filter((_, i) => i !== index);
                                updateAnswerPolicy(policy.id, { customInstructions: newInstructions });
                              }}
                              disabled={!config.enablePolicies}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="form-group">
                      <div className="form-group-header">
                        <label>Forbidden Phrases</label>
                        <button
                          className="add-small-btn"
                          onClick={() => updateAnswerPolicy(policy.id, { forbiddenPhrases: [...policy.forbiddenPhrases, ""] })}
                          disabled={!config.enablePolicies}
                        >
                          <Plus size={12} />
                          Add Phrase
                        </button>
                      </div>
                      <small>Phrases that must not appear in responses</small>
                      <div className="policies-list">
                        {policy.forbiddenPhrases.map((phrase, index) => (
                          <div key={index} className="policy-item">
                            <input
                              type="text"
                              value={phrase}
                              onChange={(e) => {
                                const newPhrases = [...policy.forbiddenPhrases];
                                newPhrases[index] = e.target.value;
                                updateAnswerPolicy(policy.id, { forbiddenPhrases: newPhrases });
                              }}
                              placeholder="e.g., I'm not sure, I don't know"
                              disabled={!config.enablePolicies}
                            />
                            <button
                              className="remove-btn"
                              onClick={() => {
                                const newPhrases = policy.forbiddenPhrases.filter((_, i) => i !== index);
                                updateAnswerPolicy(policy.id, { forbiddenPhrases: newPhrases });
                              }}
                              disabled={!config.enablePolicies}
                            >
                              <X size={14} />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {config.answerPolicies.length === 0 && (
          <div className="empty-state">
            <p>No answer policies configured. Click "Add Answer Policy" to create one.</p>
          </div>
        )}
      </div>
    );
  }
}



