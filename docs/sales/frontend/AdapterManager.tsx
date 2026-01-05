/**
 * React component for adapter hot-swap management.
 * 
 * Features:
 * - View all adapter statuses (configured, mode, credentials valid)
 * - Quick toggle between mock/live
 * - Configure credentials via modal
 * - Test connection
 * - Reset to mock mode
 * 
 * Backend: FastAPI endpoints at /api/adapters/
 */

import React, { useState, useEffect } from 'react';
import axios from 'axios';

const API_BASE = '/api/adapters';

interface AdapterStatus {
  vendor: string;
  mode: 'mock' | 'live' | 'hybrid';
  configured: boolean;
  credentials_valid: boolean;
  required_fields: string[];
  missing_fields: string[];
}

interface AdapterListResponse {
  adapters: AdapterStatus[];
}

interface ConfigureModalProps {
  vendor: string;
  requiredFields: string[];
  onClose: () => void;
  onSave: (credentials: Record<string, string>) => void;
}

// Configure modal for credential input
const ConfigureModal: React.FC<ConfigureModalProps> = ({
  vendor,
  requiredFields,
  onClose,
  onSave,
}) => {
  const [credentials, setCredentials] = useState<Record<string, string>>({});

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(credentials);
  };

  return (
    <div className="modal-overlay">
      <div className="modal">
        <h2>Configure {vendor}</h2>
        <form onSubmit={handleSubmit}>
          {requiredFields.map((field) => (
            <div key={field} className="form-group">
              <label>{field.replace(/_/g, ' ')}</label>
              <input
                type={field.includes('secret') || field.includes('password') ? 'password' : 'text'}
                value={credentials[field] || ''}
                onChange={(e) =>
                  setCredentials({ ...credentials, [field]: e.target.value })
                }
                required
              />
            </div>
          ))}
          <div className="form-actions">
            <button type="button" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="primary">
              Save
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

// Main adapter management component
export const AdapterManager: React.FC = () => {
  const [adapters, setAdapters] = useState<AdapterStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [configureVendor, setConfigureVendor] = useState<string | null>(null);

  // Load adapter statuses
  const loadAdapters = async () => {
    try {
      const response = await axios.get<AdapterListResponse>(API_BASE);
      setAdapters(response.data.adapters);
    } catch (error) {
      console.error('Failed to load adapters:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAdapters();
  }, []);

  // Toggle mock/live mode
  const handleToggle = async (vendor: string, currentMode: string) => {
    const targetMode = currentMode === 'mock' ? 'live' : 'mock';

    try {
      await axios.post(`${API_BASE}/${vendor}/toggle`, { mode: targetMode });
      await loadAdapters(); // Refresh
    } catch (error: any) {
      alert(error.response?.data?.detail || 'Toggle failed');
    }
  };

  // Configure adapter credentials
  const handleConfigure = async (
    vendor: string,
    credentials: Record<string, string>
  ) => {
    try {
      await axios.post(`${API_BASE}/${vendor}/configure`, {
        mode: 'live',
        credentials,
      });
      setConfigureVendor(null);
      await loadAdapters(); // Refresh
    } catch (error) {
      alert('Configuration failed');
    }
  };

  // Test connection
  const handleTest = async (vendor: string) => {
    try {
      const response = await axios.post(`${API_BASE}/${vendor}/test`);
      alert(
        response.data.success
          ? `✅ ${response.data.message}`
          : `❌ ${response.data.message}`
      );
    } catch (error) {
      alert('Test failed');
    }
  };

  // Reset to mock mode
  const handleReset = async (vendor: string) => {
    if (!confirm(`Reset ${vendor} to mock mode?`)) return;

    try {
      await axios.delete(`${API_BASE}/${vendor}`);
      await loadAdapters(); // Refresh
    } catch (error) {
      alert('Reset failed');
    }
  };

  if (loading) return <div>Loading adapters...</div>;

  const adapterToConfig = adapters.find((a) => a.vendor === configureVendor);

  return (
    <div className="adapter-manager">
      <h1>Adapter Configuration</h1>

      {/* Configure modal */}
      {configureVendor && adapterToConfig && (
        <ConfigureModal
          vendor={configureVendor}
          requiredFields={adapterToConfig.required_fields}
          onClose={() => setConfigureVendor(null)}
          onSave={(creds) => handleConfigure(configureVendor, creds)}
        />
      )}

      {/* Adapter grid */}
      <div className="adapter-grid">
        {adapters.map((adapter) => (
          <div key={adapter.vendor} className="adapter-card">
            <h3>{adapter.vendor.replace(/_/g, ' ')}</h3>

            <div className="adapter-status">
              <span className={`badge ${adapter.mode}`}>{adapter.mode}</span>
              <span className={`badge ${adapter.configured ? 'success' : 'warning'}`}>
                {adapter.configured ? 'Configured' : 'Not Configured'}
              </span>
            </div>

            <div className="adapter-actions">
              {/* Toggle button */}
              <button
                onClick={() => handleToggle(adapter.vendor, adapter.mode)}
                disabled={adapter.mode === 'live' && !adapter.configured}
                title={
                  adapter.mode === 'live' && !adapter.configured
                    ? 'Configure credentials first'
                    : `Switch to ${adapter.mode === 'mock' ? 'live' : 'mock'} mode`
                }
              >
                {adapter.mode === 'mock' ? '🔴 Use Live' : '🟢 Use Mock'}
              </button>

              {/* Configure button */}
              <button onClick={() => setConfigureVendor(adapter.vendor)}>
                ⚙️ Configure
              </button>

              {/* Test button */}
              <button onClick={() => handleTest(adapter.vendor)}>
                🧪 Test
              </button>

              {/* Reset button */}
              {adapter.mode === 'live' && (
                <button onClick={() => handleReset(adapter.vendor)} className="danger">
                  🔄 Reset
                </button>
              )}
            </div>

            {/* Missing fields warning */}
            {adapter.missing_fields.length > 0 && (
              <div className="warning">
                Missing: {adapter.missing_fields.join(', ')}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Refresh button */}
      <button onClick={loadAdapters} className="refresh">
        🔄 Refresh All
      </button>
    </div>
  );
};

export default AdapterManager;
