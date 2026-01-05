import React, { useState, useEffect } from "react";
import { X, Save } from "lucide-react";
import "./ConfigModal.css";

interface ModelConfigData {
  provider: string;
  model: string;
  temperature: number;
  maxTokens: number;
  topP: number;
  apiKey?: string;
}

interface ModelConfigProps {
  onClose: () => void;
}

export default function ModelConfig({ onClose }: ModelConfigProps) {
  const [config, setConfig] = useState<ModelConfigData>({
    provider: "watsonx",
    model: "granite-4-h-small",
    temperature: 0.0,
    maxTokens: 4096,
    topP: 1.0,
  });
  const [saveStatus, setSaveStatus] = useState<"idle" | "saving" | "success" | "error">("idle");
  const [availableModels, setAvailableModels] = useState<Array<{id: string, name: string, description: string}>>([]);
  const [errorMessage, setErrorMessage] = useState<string>("");

  useEffect(() => {
    loadConfig();
  }, []);

  useEffect(() => {
    // Load available models when provider changes
    if (config.provider) {
      loadAvailableModels(config.provider);
    }
  }, [config.provider]);

  const loadConfig = async () => {
    try {
      const response = await fetch('/api/config/model');
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
        setErrorMessage("");
      } else if (response.status === 401) {
        setErrorMessage("Authentication required. Please set AGENT_TOKEN environment variable.");
      } else if (response.status === 403) {
        setErrorMessage("Access forbidden. Please check your authentication token.");
      } else {
        setErrorMessage(`Failed to load configuration: ${response.statusText}`);
      }
    } catch (error) {
      console.error("Error loading config:", error);
      setErrorMessage("Network error. Please check if the backend server is running.");
    }
  };

  const loadAvailableModels = async (provider: string) => {
    try {
      const response = await fetch(`/api/models/${provider}`);
      if (response.ok) {
        const models = await response.json();
        setAvailableModels(models);
        // Auto-select default model if current model not in list
        const defaultModel = models.find((m: any) => m.default);
        if (defaultModel && !models.find((m: any) => m.id === config.model)) {
          setConfig(prev => ({ ...prev, model: defaultModel.id }));
        }
        setErrorMessage("");
      } else if (response.status === 404) {
        setErrorMessage(`Provider '${provider}' is not supported. Please select a different provider.`);
        setAvailableModels([]);
      } else if (response.status === 401) {
        setErrorMessage("Authentication required. Please set AGENT_TOKEN environment variable.");
        setAvailableModels([]);
      } else if (response.status === 403) {
        setErrorMessage("Access forbidden. Please check your authentication token.");
        setAvailableModels([]);
      } else {
        setErrorMessage(`Failed to load models for ${provider}: ${response.statusText}`);
        setAvailableModels([]);
      }
    } catch (error) {
      console.error("Error loading models:", error);
      setErrorMessage("Network error. Please check if the backend server is running.");
      setAvailableModels([]);
    }
  };

  const saveConfig = async () => {
    setSaveStatus("saving");
    setErrorMessage("");
    try {
      const response = await fetch('/api/config/model', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config),
      });
      
      if (response.ok) {
        setSaveStatus("success");
        setTimeout(() => setSaveStatus("idle"), 2000);
      } else if (response.status === 401) {
        setSaveStatus("error");
        setErrorMessage("Authentication required. Please set AGENT_TOKEN environment variable.");
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else if (response.status === 403) {
        setSaveStatus("error");
        setErrorMessage("Access forbidden. Please check your authentication token.");
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else if (response.status === 422) {
        setSaveStatus("error");
        setErrorMessage("Invalid configuration format. Please check your inputs.");
        setTimeout(() => setSaveStatus("idle"), 3000);
      } else {
        setSaveStatus("error");
        const errorData = await response.json().catch(() => ({ detail: response.statusText }));
        setErrorMessage(`Failed to save: ${errorData.detail || response.statusText}`);
        setTimeout(() => setSaveStatus("idle"), 3000);
      }
    } catch (error) {
      setSaveStatus("error");
      setErrorMessage("Network error. Please check if the backend server is running.");
      setTimeout(() => setSaveStatus("idle"), 3000);
    }
  };

  return (
    <div className="config-modal-overlay" onClick={onClose}>
      <div className="config-modal" onClick={(e) => e.stopPropagation()}>
        <div className="config-modal-header">
          <h2>Model Configuration</h2>
          <button className="config-modal-close" onClick={onClose}>
            <X size={20} />
          </button>
        </div>

        <div className="config-modal-content">
          {errorMessage && (
            <div className="error-banner" style={{
              padding: "12px",
              marginBottom: "16px",
              backgroundColor: "#fee",
              border: "1px solid #fcc",
              borderRadius: "4px",
              color: "#c00"
            }}>
              <strong>Error:</strong> {errorMessage}
            </div>
          )}
          
          <div className="config-card">
            <h3>Language Model Settings</h3>
            <div className="config-form">
              <div className="form-group">
                <label>Provider</label>
                <select
                  value={config.provider}
                  onChange={(e) => setConfig({ ...config, provider: e.target.value })}
                >
                  <option value="anthropic">Anthropic</option>
                  <option value="openai">OpenAI</option>
                  <option value="azure">Azure OpenAI</option>
                  <option value="watsonx">IBM watsonx</option>
                  <option value="ollama">Ollama</option>
                </select>
              </div>

              <div className="form-group">
                <label>Model</label>
                <select
                  value={config.model}
                  onChange={(e) => setConfig({ ...config, model: e.target.value })}
                >
                  {availableModels.length > 0 ? (
                    availableModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.name} - {model.description}
                      </option>
                    ))
                  ) : (
                    <option value={config.model}>{config.model}</option>
                  )}
                </select>
              </div>

              <div className="form-group">
                <label>Temperature: {config.temperature}</label>
                <input
                  type="range"
                  min="0"
                  max="2"
                  step="0.1"
                  value={config.temperature}
                  onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
                />
                <small>Controls randomness: 0 = deterministic (Granite default), 2 = creative</small>
              </div>

              <div className="form-group">
                <label>Max Tokens</label>
                <input
                  type="number"
                  value={config.maxTokens}
                  onChange={(e) => setConfig({ ...config, maxTokens: parseInt(e.target.value) })}
                  min="1"
                  max="200000"
                />
              </div>

              <div className="form-group">
                <label>Top P: {config.topP}</label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={config.topP}
                  onChange={(e) => setConfig({ ...config, topP: parseFloat(e.target.value) })}
                />
                <small>Nucleus sampling threshold</small>
              </div>

              {config.provider !== "ollama" && (
                <div className="form-group">
                  <label>API Key</label>
                  <input
                    type="password"
                    value={config.apiKey || ""}
                    onChange={(e) => setConfig({ ...config, apiKey: e.target.value })}
                    placeholder="Enter API key..."
                  />
                </div>
              )}
            </div>
          </div>
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
}


