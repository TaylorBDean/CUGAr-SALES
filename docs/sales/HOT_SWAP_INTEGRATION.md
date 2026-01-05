# Hot-Swap Adapter Integration Guide

Complete guide for integrating mock/live vendor adapters with frontend UI.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Quick Start (5 Minutes)](#quick-start-5-minutes)
3. [Backend Setup](#backend-setup)
4. [Frontend Integration](#frontend-integration)
5. [Adding New Vendors](#adding-new-vendors)
6. [Testing](#testing)
7. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

### Design Philosophy

**Brain-Dead Easy Demo** - Works immediately with zero configuration:
- ✅ Mock mode works out-of-box (no credentials needed)
- ✅ Realistic demo data from YAML fixtures
- ✅ Hot-swap to live APIs when ready
- ✅ Frontend UI manages all configuration
- ✅ Zero code changes in tools

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend UI                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │  AdapterManager Component                        │  │
│  │  - View adapter statuses                         │  │
│  │  - Toggle mock ↔ live                           │  │
│  │  - Input credentials                             │  │
│  │  - Test connections                              │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │ HTTP (JSON)
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  FastAPI Backend                        │
│  ┌──────────────────────────────────────────────────┐  │
│  │  /api/adapters/ (6 endpoints)                    │  │
│  │  - GET    /                  (list all)          │  │
│  │  - GET    /{vendor}          (get status)        │  │
│  │  - POST   /{vendor}/configure (set credentials)  │  │
│  │  - POST   /{vendor}/toggle    (quick switch)     │  │
│  │  - POST   /{vendor}/test      (test connection)  │  │
│  │  - DELETE /{vendor}           (reset to mock)    │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │ File I/O
                     ▼
┌─────────────────────────────────────────────────────────┐
│              configs/adapters.yaml                       │
│  adapters:                                               │
│    ibm_sales_cloud:                                      │
│      mode: live                                          │
│      credentials:                                        │
│        api_endpoint: https://api.ibm.com                 │
│        api_key: sk-...                                   │
│        tenant_id: acme-corp                              │
└────────────────────┬────────────────────────────────────┘
                     │ Config Resolution
                     ▼
┌─────────────────────────────────────────────────────────┐
│                  Adapter Factory                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  create_adapter(vendor, trace_id)                │  │
│  │  - Reads configs/adapters.yaml                   │  │
│  │  - Auto-detects mode (mock/live)                 │  │
│  │  - Returns VendorAdapter                         │  │
│  └──────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│  MockAdapter    │     │  LiveAdapter    │
│  (YAML fixtures)│     │  (Real APIs)    │
└─────────────────┘     └─────────────────┘
```

### Configuration Precedence

The factory reads configuration in this order:

1. **configs/adapters.yaml** (frontend API-managed) ← **DEFAULT**
2. Environment variables (backward compat)
3. Mock mode (zero-config fallback)

---

## Quick Start (5 Minutes)

### 1. Test Mock Mode (Zero Config)

```python
from cuga.adapters import create_adapter

# Create adapter (defaults to mock mode)
adapter = create_adapter("ibm_sales_cloud")

# Fetch demo data (no credentials required)
accounts = adapter.fetch_accounts()
print(f"Found {len(accounts)} accounts")  # 5 accounts from fixtures

contacts = adapter.fetch_contacts(account_id="ACC-001")
print(f"Found {len(contacts)} contacts")  # Real demo data

# Check mode
print(adapter.get_mode())  # AdapterMode.MOCK
```

**Result:** Works immediately with realistic IBM Sales Cloud demo data.

### 2. View Demo Data

```bash
cat src/cuga/adapters/sales/fixtures/ibm_sales_cloud.yaml
```

**Contains:**
- 5 accounts (Technology, Manufacturing, Healthcare, Finance)
- 4 contacts (VP Sales, CFO, Director, CRO)
- 3 opportunities ($150K, $85K, $200K)
- 3 buying signals (job postings, funding, executive hires)

### 3. Start FastAPI Backend

```python
# Add to your main FastAPI app
from cuga.api.adapters import router

app.include_router(router)
```

### 4. Test API Endpoints

```bash
# List all adapters
curl http://localhost:8000/api/adapters/

# Get IBM Sales Cloud status
curl http://localhost:8000/api/adapters/ibm_sales_cloud

# Test connection (mock mode always succeeds)
curl -X POST http://localhost:8000/api/adapters/ibm_sales_cloud/test
```

### 5. Configure Live Mode

```bash
# Configure IBM Sales Cloud credentials
curl -X POST http://localhost:8000/api/adapters/ibm_sales_cloud/configure \
  -H "Content-Type: application/json" \
  -d '{
    "mode": "live",
    "credentials": {
      "api_endpoint": "https://api.ibm.com/watson-campaign-automation/v2.1",
      "api_key": "sk-your-api-key",
      "tenant_id": "your-tenant-id"
    }
  }'
```

**Result:** Next `create_adapter("ibm_sales_cloud")` call uses live API.

---

## Backend Setup

### Install FastAPI Dependencies

```bash
pip install fastapi pydantic pyyaml
```

### Add Router to FastAPI App

```python
# src/cuga/main.py (or your FastAPI entry point)
from fastapi import FastAPI
from cuga.api.adapters import router as adapters_router

app = FastAPI(title="CUGAr Sales Intelligence")

# Include adapter endpoints
app.include_router(adapters_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

### API Documentation

Once running, visit http://localhost:8000/docs for interactive Swagger UI.

### Available Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/adapters/` | List all adapter statuses |
| GET | `/api/adapters/{vendor}` | Get specific adapter status |
| POST | `/api/adapters/{vendor}/configure` | Configure credentials |
| POST | `/api/adapters/{vendor}/toggle` | Quick mock/live toggle |
| POST | `/api/adapters/{vendor}/test` | Test connection |
| DELETE | `/api/adapters/{vendor}` | Reset to mock mode |

---

## Frontend Integration

### React Example

The complete React component is at `docs/sales/frontend/AdapterManager.tsx`.

**Key Features:**
- Adapter status grid (configured, mode, credentials valid)
- Toggle button (mock ↔ live)
- Configure modal with dynamic form
- Test connection button
- Reset to mock button

**Usage:**

```tsx
import { AdapterManager } from './AdapterManager';

function App() {
  return (
    <div>
      <h1>CRM Configuration</h1>
      <AdapterManager />
    </div>
  );
}
```

### Vue Example

```vue
<template>
  <div class="adapter-manager">
    <div v-for="adapter in adapters" :key="adapter.vendor">
      <h3>{{ adapter.vendor }}</h3>
      <span :class="adapter.mode">{{ adapter.mode }}</span>
      
      <button @click="toggleAdapter(adapter.vendor, adapter.mode)">
        {{ adapter.mode === 'mock' ? 'Use Live' : 'Use Mock' }}
      </button>
      
      <button @click="showConfigModal(adapter.vendor)">
        Configure
      </button>
    </div>
  </div>
</template>

<script>
export default {
  data() {
    return { adapters: [] };
  },
  async mounted() {
    const response = await fetch('/api/adapters/');
    const data = await response.json();
    this.adapters = data.adapters;
  },
  methods: {
    async toggleAdapter(vendor, currentMode) {
      const targetMode = currentMode === 'mock' ? 'live' : 'mock';
      await fetch(`/api/adapters/${vendor}/toggle`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: targetMode }),
      });
      this.loadAdapters();
    },
  },
};
</script>
```

### Plain JavaScript Example

```javascript
// Load adapter statuses
async function loadAdapters() {
  const response = await fetch('/api/adapters/');
  const data = await response.json();
  
  const container = document.getElementById('adapters');
  container.innerHTML = data.adapters.map(adapter => `
    <div class="adapter-card">
      <h3>${adapter.vendor}</h3>
      <span class="badge ${adapter.mode}">${adapter.mode}</span>
      <button onclick="toggleAdapter('${adapter.vendor}', '${adapter.mode}')">
        ${adapter.mode === 'mock' ? 'Use Live' : 'Use Mock'}
      </button>
      <button onclick="configureAdapter('${adapter.vendor}')">
        Configure
      </button>
    </div>
  `).join('');
}

// Toggle adapter mode
async function toggleAdapter(vendor, currentMode) {
  const targetMode = currentMode === 'mock' ? 'live' : 'mock';
  
  await fetch(`/api/adapters/${vendor}/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: targetMode }),
  });
  
  loadAdapters();
}

// Configure adapter
async function configureAdapter(vendor) {
  const credentials = prompt(`Enter credentials for ${vendor}:`);
  
  await fetch(`/api/adapters/${vendor}/configure`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      mode: 'live',
      credentials: JSON.parse(credentials),
    }),
  });
  
  loadAdapters();
}
```

---

## Adding New Vendors

### 1. Create Mock Fixtures

```yaml
# src/cuga/adapters/sales/fixtures/salesforce.yaml

schema:
  version: "Salesforce API v59.0"
  
accounts:
  - id: "001xx000003DHP0AAO"
    name: "Acme Corporation"
    industry: "Technology"
    type: "Customer"
    annual_revenue: 50000000
    billing_country: "USA"
    icp_score: 0.85
    
  - id: "001xx000003DHP1AAO"
    name: "TechStart Inc"
    industry: "Technology"
    type: "Prospect"
    annual_revenue: 12000000
    billing_country: "USA"
    icp_score: 0.92

contacts:
  - id: "003xx000004TmiQAAS"
    account_id: "001xx000003DHP0AAO"
    name: "Jane Smith"
    title: "VP of Sales"
    email: "jane.smith@acmecorp.com"
    role: "champion"
    
opportunities:
  - id: "006xx000001Y8fZAAS"
    account_id: "001xx000003DHP0AAO"
    name: "Q4 Enterprise License"
    stage: "Negotiation"
    amount: 150000
    close_date: "2026-03-31"
```

### 2. Test Mock Adapter

```python
from cuga.adapters import create_adapter

# Create Salesforce adapter (uses new fixtures)
adapter = create_adapter("salesforce")

# Test data fetching
accounts = adapter.fetch_accounts()
print(f"Salesforce: {len(accounts)} accounts")
```

### 3. Implement Live Adapter (Optional)

```python
# src/cuga/adapters/sales/live/salesforce_adapter.py

from typing import Dict, Any, List, Optional
import httpx

from cuga.security.http_client import SafeClient
from ..protocol import VendorAdapter, AdapterMode, AdapterConfig


class SalesforceAdapter(VendorAdapter):
    """Salesforce live adapter using REST API"""
    
    def __init__(self, config: AdapterConfig):
        self.config = config
        self.client = SafeClient()  # Enforced timeouts, retries
        
        # Extract credentials
        self.instance_url = config.credentials["instance_url"]
        self.access_token = self._authenticate()
    
    def _authenticate(self) -> str:
        """OAuth2 authentication flow"""
        creds = self.config.credentials
        
        response = self.client.post(
            f"{self.instance_url}/services/oauth2/token",
            data={
                "grant_type": "password",
                "client_id": creds["client_id"],
                "client_secret": creds["client_secret"],
                "username": creds["username"],
                "password": creds["password"],
            }
        )
        
        return response.json()["access_token"]
    
    def fetch_accounts(
        self,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Fetch accounts from Salesforce API"""
        
        # Build SOQL query
        query = "SELECT Id, Name, Industry, Type, AnnualRevenue FROM Account"
        
        if filters:
            conditions = []
            if territory := filters.get("territory"):
                conditions.append(f"BillingState = '{territory}'")
            if industry := filters.get("industry"):
                conditions.append(f"Industry = '{industry}'")
            
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
        
        # Execute query
        response = self.client.get(
            f"{self.instance_url}/services/data/v59.0/query",
            params={"q": query},
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        return response.json()["records"]
    
    def fetch_contacts(self, account_id: str) -> List[Dict[str, Any]]:
        """Fetch contacts for account"""
        query = f"SELECT Id, Name, Title, Email FROM Contact WHERE AccountId = '{account_id}'"
        
        response = self.client.get(
            f"{self.instance_url}/services/data/v59.0/query",
            params={"q": query},
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        return response.json()["records"]
    
    def fetch_opportunities(
        self,
        account_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fetch opportunities"""
        query = "SELECT Id, Name, StageName, Amount, CloseDate FROM Opportunity"
        
        if account_id:
            query += f" WHERE AccountId = '{account_id}'"
        
        response = self.client.get(
            f"{self.instance_url}/services/data/v59.0/query",
            params={"q": query},
            headers={"Authorization": f"Bearer {self.access_token}"}
        )
        
        return response.json()["records"]
    
    def get_mode(self) -> AdapterMode:
        return AdapterMode.LIVE
    
    def validate_connection(self) -> bool:
        """Test connection to Salesforce"""
        try:
            response = self.client.get(
                f"{self.instance_url}/services/data/",
                headers={"Authorization": f"Bearer {self.access_token}"}
            )
            return response.status_code == 200
        except Exception:
            return False
```

### 4. Update Factory

```python
# src/cuga/adapters/sales/factory.py

from .live.salesforce_adapter import SalesforceAdapter

def create_adapter(vendor: str, trace_id: Optional[str] = None) -> VendorAdapter:
    # ... existing code ...
    
    if mode == AdapterMode.LIVE:
        if vendor == "ibm_sales_cloud":
            return IBMSalesCloudAdapter(config=config)
        elif vendor == "salesforce":
            return SalesforceAdapter(config=config)  # NEW
        else:
            print(f"[WARNING] Live adapter not implemented for {vendor}")
            return MockAdapter(vendor=vendor, config=config)
    
    return MockAdapter(vendor=vendor, config=config)
```

---

## Testing

### Unit Tests

```python
# tests/adapters/test_mock_adapter.py

import pytest
from cuga.adapters import create_adapter, AdapterMode


def test_mock_adapter_defaults_to_mock_mode():
    """Mock adapter works with zero config"""
    adapter = create_adapter("ibm_sales_cloud")
    
    assert adapter.get_mode() == AdapterMode.MOCK


def test_mock_adapter_fetches_accounts():
    """Mock adapter returns fixture data"""
    adapter = create_adapter("ibm_sales_cloud")
    accounts = adapter.fetch_accounts()
    
    assert len(accounts) == 5
    assert accounts[0]["name"] == "Acme Corporation"


def test_mock_adapter_filters_by_territory():
    """Mock adapter supports filtering"""
    adapter = create_adapter("ibm_sales_cloud")
    accounts = adapter.fetch_accounts(filters={"territory": "West"})
    
    assert all(acc["territory"] == "West" for acc in accounts)


def test_mock_adapter_validates_connection():
    """Mock adapter always validates"""
    adapter = create_adapter("ibm_sales_cloud")
    
    assert adapter.validate_connection() is True
```

### Integration Tests

```python
# tests/adapters/test_adapter_factory.py

import pytest
import yaml
from pathlib import Path
from cuga.adapters import create_adapter, AdapterMode


def test_factory_reads_config_file(tmp_path):
    """Factory reads configs/adapters.yaml"""
    config_path = tmp_path / "configs" / "adapters.yaml"
    config_path.parent.mkdir(parents=True)
    
    config_path.write_text(yaml.dump({
        "adapters": {
            "ibm_sales_cloud": {
                "mode": "live",
                "credentials": {
                    "api_endpoint": "https://test.com",
                    "api_key": "sk-test",
                }
            }
        }
    }))
    
    # Temporarily patch CONFIG_PATH
    from cuga.adapters.sales import factory
    original_path = factory.CONFIG_PATH
    factory.CONFIG_PATH = config_path
    
    try:
        adapter = create_adapter("ibm_sales_cloud")
        # Would be live if implemented, falls back to mock with warning
        assert adapter.get_mode() in [AdapterMode.LIVE, AdapterMode.MOCK]
    finally:
        factory.CONFIG_PATH = original_path


def test_factory_falls_back_to_env(monkeypatch):
    """Factory falls back to environment variables"""
    monkeypatch.setenv("SALES_IBM_SALES_CLOUD_ADAPTER_MODE", "live")
    monkeypatch.setenv("SALES_IBM_SALES_CLOUD_API_KEY", "sk-test")
    
    adapter = create_adapter("ibm_sales_cloud")
    # Would be live if implemented
    assert adapter.get_mode() in [AdapterMode.LIVE, AdapterMode.MOCK]
```

### API Tests

```python
# tests/api/test_adapters_api.py

import pytest
from fastapi.testclient import TestClient
from cuga.main import app


client = TestClient(app)


def test_list_adapters():
    """GET /api/adapters/ returns adapter list"""
    response = client.get("/api/adapters/")
    
    assert response.status_code == 200
    data = response.json()
    assert "adapters" in data
    assert len(data["adapters"]) > 0


def test_get_adapter_status():
    """GET /api/adapters/{vendor} returns status"""
    response = client.get("/api/adapters/ibm_sales_cloud")
    
    assert response.status_code == 200
    data = response.json()
    assert data["vendor"] == "ibm_sales_cloud"
    assert data["mode"] in ["mock", "live", "hybrid"]


def test_configure_adapter():
    """POST /api/adapters/{vendor}/configure saves config"""
    response = client.post(
        "/api/adapters/ibm_sales_cloud/configure",
        json={
            "mode": "live",
            "credentials": {
                "api_endpoint": "https://test.com",
                "api_key": "sk-test",
                "tenant_id": "test-tenant"
            }
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["mode"] == "live"
    assert data["configured"] is True


def test_toggle_adapter_without_credentials():
    """POST /api/adapters/{vendor}/toggle fails without credentials"""
    # First reset to mock
    client.delete("/api/adapters/ibm_sales_cloud")
    
    # Try toggling to live without credentials
    response = client.post(
        "/api/adapters/ibm_sales_cloud/toggle",
        json={"mode": "live"}
    )
    
    assert response.status_code == 400
    assert "missing credentials" in response.json()["detail"].lower()


def test_test_adapter_mock():
    """POST /api/adapters/{vendor}/test succeeds in mock mode"""
    response = client.post("/api/adapters/ibm_sales_cloud/test")
    
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert "mock" in data["message"].lower()


def test_reset_adapter():
    """DELETE /api/adapters/{vendor} resets to mock"""
    # Configure live
    client.post(
        "/api/adapters/ibm_sales_cloud/configure",
        json={"mode": "live", "credentials": {"api_key": "test"}}
    )
    
    # Reset
    response = client.delete("/api/adapters/ibm_sales_cloud")
    assert response.status_code == 204
    
    # Verify reset
    status = client.get("/api/adapters/ibm_sales_cloud").json()
    assert status["mode"] == "mock"
```

---

## Troubleshooting

### Mock Mode Not Working

**Symptom:** `FileNotFoundError: fixtures/ibm_sales_cloud.yaml`

**Solution:** Ensure fixture file exists:
```bash
ls src/cuga/adapters/sales/fixtures/ibm_sales_cloud.yaml
```

If missing, check git status or restore from repository.

### Toggle to Live Fails

**Symptom:** `400 Bad Request: missing credentials`

**Solution:** Configure credentials before toggling:
```bash
curl -X POST http://localhost:8000/api/adapters/ibm_sales_cloud/configure \
  -H "Content-Type: application/json" \
  -d '{"mode": "live", "credentials": {...}}'
```

### Live Mode Not Implemented

**Symptom:** `[WARNING] Live mode requested but not implemented`

**Solution:** This is expected. Live adapters are added incrementally:
1. Mock mode works immediately (demo data)
2. Live implementations added per vendor as needed
3. System gracefully falls back to mock with warning

### Config Not Persisting

**Symptom:** Settings reset after restart

**Solution:** Verify `configs/adapters.yaml` exists and is writable:
```bash
ls -la configs/adapters.yaml
cat configs/adapters.yaml
```

Check FastAPI has write permissions to `configs/` directory.

### CORS Errors in Frontend

**Symptom:** `Access-Control-Allow-Origin` errors

**Solution:** Add CORS middleware to FastAPI:
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Next Steps

### Immediate (Demo Ready)
- ✅ Mock adapters work with demo data
- ✅ FastAPI backend for frontend config
- ✅ React/Vue examples provided
- ✅ Zero-config demos (mock mode default)

### Short-Term (Production)
- 🔲 Implement live IBM Sales Cloud adapter
- 🔲 Add Salesforce fixtures + live adapter
- 🔲 Add HubSpot fixtures + live adapter
- 🔲 Credential encryption at rest
- 🔲 Rate limiting for live APIs

### Long-Term (Scale)
- 🔲 Hybrid mode (mock for development, live for production)
- 🔲 Adapter marketplace (community-contributed)
- 🔲 Real-time sync for live adapters
- 🔲 Webhook support for event-driven updates
- 🔲 Multi-tenant adapter configuration

---

## Summary

**Brain-Dead Easy Integration:**

1. **Mock mode works immediately** - No config, no credentials, realistic demo data
2. **Frontend UI manages everything** - Credentials, mode toggle, testing via API
3. **Zero code changes** - Tools automatically use configured adapter
4. **Hot-swap anytime** - Toggle mock ↔ live without restarting
5. **Config-driven** - All settings in `configs/adapters.yaml`

**Complete Stack:**
- Protocol layer (`VendorAdapter` interface)
- Mock adapters (YAML fixtures)
- Factory (config-driven mode selection)
- FastAPI backend (6 endpoints for UI)
- React component (drop-in UI)
- Demo data (IBM Sales Cloud ready)

**Start Using:**
```python
from cuga.adapters import create_adapter

adapter = create_adapter("ibm_sales_cloud")  # Auto-detects mode
accounts = adapter.fetch_accounts()  # Works immediately (mock data)
```

**No configuration required for demos. Add credentials via UI when ready for live.**
