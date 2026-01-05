/**
 * Data Source Configuration Component
 * 
 * Production-ready hot-swap toggle for vendor integrations.
 * Clean, aesthetic UI with IBM Carbon design patterns.
 */

import React, { useState, useEffect } from 'react';
import { Database, Settings, CheckCircle, AlertCircle, TestTube2, Power } from 'lucide-react';

// API Configuration
const API_BASE = process.env.REACT_APP_API_BASE || 'http://localhost:8000/api/adapters';

// Types
interface AdapterStatus {
  vendor: string;
  mode: 'mock' | 'live' | 'hybrid';
  configured: boolean;
  credentials_valid: boolean;
  required_fields: string[];
  missing_fields: string[];
}

interface VendorConfig {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: 'crm' | 'enrichment' | 'signals';
  requiredFields: {
    name: string;
    label: string;
    type: 'text' | 'password' | 'url';
    placeholder: string;
    helpText?: string;
  }[];
}

// Vendor configurations with clean UI metadata
const VENDOR_CONFIGS: VendorConfig[] = [
  {
    id: 'ibm_sales_cloud',
    name: 'IBM Sales Cloud',
    description: 'Watson Campaign Automation for CRM and pipeline data',
    icon: '🔷',
    category: 'crm',
    requiredFields: [
      {
        name: 'api_endpoint',
        label: 'API Endpoint',
        type: 'url',
        placeholder: 'https://api.ibm.com/watson-campaign-automation/v2.1',
        helpText: 'Your IBM Sales Cloud API endpoint'
      },
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        placeholder: 'sk-...',
        helpText: 'API key from IBM Cloud console'
      },
      {
        name: 'tenant_id',
        label: 'Tenant ID',
        type: 'text',
        placeholder: 'your-tenant-id',
        helpText: 'Your organization tenant identifier'
      }
    ]
  },
  {
    id: 'salesforce',
    name: 'Salesforce',
    description: 'World\'s #1 CRM for accounts, contacts, and opportunities',
    icon: '☁️',
    category: 'crm',
    requiredFields: [
      {
        name: 'instance_url',
        label: 'Instance URL',
        type: 'url',
        placeholder: 'https://yourinstance.salesforce.com'
      },
      {
        name: 'client_id',
        label: 'Client ID',
        type: 'text',
        placeholder: 'Connected App Client ID'
      },
      {
        name: 'client_secret',
        label: 'Client Secret',
        type: 'password',
        placeholder: 'Connected App Secret'
      },
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        placeholder: 'user@company.com'
      },
      {
        name: 'password',
        label: 'Password + Token',
        type: 'password',
        placeholder: 'password + security token'
      }
    ]
  },
  {
    id: 'hubspot',
    name: 'HubSpot',
    description: 'Inbound marketing and sales platform',
    icon: '🟠',
    category: 'crm',
    requiredFields: [
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        placeholder: 'pat-na1-...'
      }
    ]
  },
  {
    id: 'zoominfo',
    name: 'ZoomInfo',
    description: 'Company and contact intelligence',
    icon: '🔍',
    category: 'enrichment',
    requiredFields: [
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        placeholder: 'Your ZoomInfo API key'
      },
      {
        name: 'username',
        label: 'Username',
        type: 'text',
        placeholder: 'ZoomInfo username'
      }
    ]
  },
  {
    id: 'sixsense',
    name: '6sense',
    description: 'B2B buyer intent signals',
    icon: '🎯',
    category: 'signals',
    requiredFields: [
      {
        name: 'api_key',
        label: 'API Key',
        type: 'password',
        placeholder: '6sense API key'
      },
      {
        name: 'company_id',
        label: 'Company ID',
        type: 'text',
        placeholder: 'Your 6sense company ID'
      }
    ]
  }
];

// Main Component
export const DataSourceConfig: React.FC = () => {
  const [adapters, setAdapters] = useState<Record<string, AdapterStatus>>({});
  const [loading, setLoading] = useState(true);
  const [configuring, setConfiguring] = useState<string | null>(null);
  const [credentials, setCredentials] = useState<Record<string, string>>({});
  const [testing, setTesting] = useState<string | null>(null);
  const [testResults, setTestResults] = useState<Record<string, { success: boolean; message: string }>>({});

  // Load adapter statuses
  const loadAdapters = async () => {
    try {
      const response = await fetch(API_BASE);
      const data = await response.json();
      
      const statusMap: Record<string, AdapterStatus> = {};
      data.adapters.forEach((adapter: AdapterStatus) => {
        statusMap[adapter.vendor] = adapter;
      });
      
      setAdapters(statusMap);
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
  const handleToggle = async (vendorId: string) => {
    const status = adapters[vendorId];
    if (!status) return;

    const targetMode = status.mode === 'mock' ? 'live' : 'mock';

    // Check if credentials needed for live mode
    if (targetMode === 'live' && !status.configured) {
      setConfiguring(vendorId);
      return;
    }

    try {
      await fetch(`${API_BASE}/${vendorId}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: targetMode })
      });
      
      await loadAdapters();
    } catch (error) {
      console.error('Toggle failed:', error);
      alert('Failed to toggle mode. See console for details.');
    }
  };

  // Configure credentials
  const handleConfigure = async (vendorId: string) => {
    try {
      await fetch(`${API_BASE}/${vendorId}/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          mode: 'live',
          credentials
        })
      });
      
      setConfiguring(null);
      setCredentials({});
      await loadAdapters();
    } catch (error) {
      console.error('Configuration failed:', error);
      alert('Failed to save configuration. See console for details.');
    }
  };

  // Test connection
  const handleTest = async (vendorId: string) => {
    setTesting(vendorId);
    
    try {
      const response = await fetch(`${API_BASE}/${vendorId}/test`, {
        method: 'POST'
      });
      
      const result = await response.json();
      setTestResults({
        ...testResults,
        [vendorId]: {
          success: result.success,
          message: result.message
        }
      });
      
      setTimeout(() => {
        setTestResults(prev => {
          const next = { ...prev };
          delete next[vendorId];
          return next;
        });
      }, 3000);
    } catch (error) {
      setTestResults({
        ...testResults,
        [vendorId]: {
          success: false,
          message: 'Connection test failed'
        }
      });
    } finally {
      setTesting(null);
    }
  };

  // Reset to mock mode
  const handleReset = async (vendorId: string) => {
    if (!confirm(`Reset ${vendorId} to demo mode? This will remove live credentials.`)) {
      return;
    }

    try {
      await fetch(`${API_BASE}/${vendorId}`, {
        method: 'DELETE'
      });
      
      await loadAdapters();
    } catch (error) {
      console.error('Reset failed:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-indigo-700 rounded-lg shadow-lg p-6 text-white">
        <div className="flex items-center gap-3 mb-2">
          <Database className="w-8 h-8" />
          <h1 className="text-3xl font-bold">Data Source Configuration</h1>
        </div>
        <p className="text-blue-100">
          Toggle between demo data and live integrations. Demo mode works immediately with realistic sample data.
        </p>
      </div>

      {/* Vendor Grid by Category */}
      {['crm', 'enrichment', 'signals'].map(category => {
        const categoryVendors = VENDOR_CONFIGS.filter(v => v.category === category);
        if (categoryVendors.length === 0) return null;

        return (
          <div key={category} className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-700 capitalize flex items-center gap-2">
              {category === 'crm' && '💼'}
              {category === 'enrichment' && '📊'}
              {category === 'signals' && '📡'}
              {category === 'crm' ? 'CRM Systems' : category === 'enrichment' ? 'Data Enrichment' : 'Intent Signals'}
            </h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {categoryVendors.map(vendor => {
                const status = adapters[vendor.id];
                const isLive = status?.mode === 'live';
                const isConfigured = status?.configured ?? false;
                const testResult = testResults[vendor.id];

                return (
                  <div
                    key={vendor.id}
                    className={`bg-white rounded-lg shadow-md border-2 transition-all ${
                      isLive ? 'border-green-500' : 'border-gray-200'
                    } hover:shadow-lg`}
                  >
                    <div className="p-6">
                      {/* Vendor Header */}
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex items-center gap-3">
                          <span className="text-3xl">{vendor.icon}</span>
                          <div>
                            <h3 className="text-lg font-semibold text-gray-900">{vendor.name}</h3>
                            <p className="text-sm text-gray-500">{vendor.description}</p>
                          </div>
                        </div>
                      </div>

                      {/* Status Badges */}
                      <div className="flex gap-2 mb-4">
                        <span
                          className={`inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium ${
                            isLive
                              ? 'bg-green-100 text-green-800'
                              : 'bg-blue-100 text-blue-800'
                          }`}
                        >
                          <Power className="w-3 h-3" />
                          {isLive ? 'Live Data' : 'Demo Mode'}
                        </span>
                        
                        {isConfigured ? (
                          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800">
                            <CheckCircle className="w-3 h-3" />
                            Configured
                          </span>
                        ) : isLive ? (
                          <span className="inline-flex items-center gap-1 px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                            <AlertCircle className="w-3 h-3" />
                            Needs Setup
                          </span>
                        ) : null}
                      </div>

                      {/* Test Result */}
                      {testResult && (
                        <div
                          className={`mb-4 p-3 rounded-md text-sm ${
                            testResult.success
                              ? 'bg-green-50 text-green-800 border border-green-200'
                              : 'bg-red-50 text-red-800 border border-red-200'
                          }`}
                        >
                          {testResult.message}
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex gap-2">
                        {/* Toggle Button */}
                        <button
                          onClick={() => handleToggle(vendor.id)}
                          disabled={isLive && !isConfigured}
                          className={`flex-1 px-4 py-2 rounded-md font-medium transition-colors ${
                            isLive
                              ? 'bg-blue-600 hover:bg-blue-700 text-white'
                              : 'bg-green-600 hover:bg-green-700 text-white'
                          } disabled:opacity-50 disabled:cursor-not-allowed`}
                          title={
                            isLive && !isConfigured
                              ? 'Configure credentials first'
                              : isLive
                              ? 'Switch to demo data'
                              : 'Switch to live data'
                          }
                        >
                          {isLive ? '← Demo Mode' : 'Live Mode →'}
                        </button>

                        {/* Configure Button */}
                        <button
                          onClick={() => setConfiguring(vendor.id)}
                          className="px-4 py-2 rounded-md font-medium bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
                          title="Configure credentials"
                        >
                          <Settings className="w-5 h-5" />
                        </button>

                        {/* Test Button */}
                        <button
                          onClick={() => handleTest(vendor.id)}
                          disabled={testing === vendor.id}
                          className="px-4 py-2 rounded-md font-medium bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors disabled:opacity-50"
                          title="Test connection"
                        >
                          <TestTube2 className={`w-5 h-5 ${testing === vendor.id ? 'animate-pulse' : ''}`} />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}

      {/* Configuration Modal */}
      {configuring && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-2xl font-bold text-gray-900">
                Configure {VENDOR_CONFIGS.find(v => v.id === configuring)?.name}
              </h2>
              <p className="text-sm text-gray-500 mt-1">
                Enter your API credentials to enable live data access
              </p>
            </div>

            <div className="p-6 space-y-4">
              {VENDOR_CONFIGS.find(v => v.id === configuring)?.requiredFields.map(field => (
                <div key={field.name}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    {field.label}
                  </label>
                  <input
                    type={field.type}
                    value={credentials[field.name] || ''}
                    onChange={e => setCredentials({ ...credentials, [field.name]: e.target.value })}
                    placeholder={field.placeholder}
                    className="w-full px-4 py-2 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  />
                  {field.helpText && (
                    <p className="text-xs text-gray-500 mt-1">{field.helpText}</p>
                  )}
                </div>
              ))}
            </div>

            <div className="p-6 border-t border-gray-200 flex gap-3">
              <button
                onClick={() => {
                  setConfiguring(null);
                  setCredentials({});
                }}
                className="flex-1 px-4 py-2 rounded-md font-medium bg-gray-100 hover:bg-gray-200 text-gray-700 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => handleConfigure(configuring)}
                className="flex-1 px-4 py-2 rounded-md font-medium bg-blue-600 hover:bg-blue-700 text-white transition-colors"
              >
                Save Configuration
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DataSourceConfig;
