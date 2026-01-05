# Quick Test Guide: External Data Feed Adapters

**Last Updated**: 2026-01-04  
**Status**: 10/10 adapters ready for testing ✅ 🚀

---

## 🚀 Quick Start

### **1. Install Dependencies**
```bash
pip install httpx pyyaml click python-dotenv
```

### **2. Copy Environment Template**
```bash
cp .env.sales.example .env.sales
```

### **3. Configure Credentials**
Edit `.env.sales` with your API keys (see sections below)

### **4. Run Tests**
```bash
# Test all adapters
python scripts/setup_data_feeds.py

# Test specific adapter
python -c "from cuga.adapters.sales.factory import create_adapter; \
adapter = create_adapter('salesforce', trace_id='test'); \
print(adapter.validate_connection())"
```

---

## 📦 Adapter-Specific Setup

### **IBM Sales Cloud** (Critical)

**Credentials Needed**:
- OAuth Client ID + Secret
- API Key
- Tenant ID

**Setup Steps**:
1. Log into IBM Sales Cloud admin portal
2. Create OAuth application:
   - Go to Settings → Integrations → API Access
   - Click "New Application"
   - Note Client ID and Secret
3. Generate API key:
   - Go to Settings → API Keys
   - Click "Generate New Key"
   - Copy key value
4. Find tenant ID:
   - In URL: `https://app.ibm.com/tenant/{TENANT_ID}/...`

**Environment Variables**:
```bash
export SALES_IBM_SALES_CLOUD_ADAPTER_MODE=live
export SALES_IBM_CLIENT_ID=<oauth-client-id>
export SALES_IBM_CLIENT_SECRET=<oauth-client-secret>
export SALES_IBM_API_KEY=<api-key>
export SALES_IBM_TENANT_ID=<tenant-id>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_adapter
adapter = create_adapter('ibm_sales_cloud', trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'limit': 5})
print(f'Fetched {len(accounts)} accounts')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 accounts
```

---

### **Salesforce** (Critical)

**Credentials Needed**:
- OAuth Client ID + Secret
- Username + Password
- Security Token (if IP restrictions enabled)
- Instance URL

**Setup Steps**:
1. Create Connected App:
   - Setup → Apps → App Manager → New Connected App
   - Enable OAuth Settings
   - Callback URL: `http://localhost:8080/callback`
   - Scopes: `api`, `refresh_token`, `offline_access`
   - Save and note Client ID + Secret
2. Get security token:
   - Settings → My Personal Information → Reset Security Token
   - Check email for new token

**Environment Variables**:
```bash
export SALES_SALESFORCE_ADAPTER_MODE=live
export SALES_SALESFORCE_CLIENT_ID=<connected-app-client-id>
export SALES_SALESFORCE_CLIENT_SECRET=<connected-app-secret>
export SALES_SALESFORCE_USERNAME=<your-email@company.com>
export SALES_SALESFORCE_PASSWORD=<password>
export SALES_SALESFORCE_SECURITY_TOKEN=<token-from-email>
export SALES_SALESFORCE_INSTANCE_URL=https://yourinstance.my.salesforce.com
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_adapter
adapter = create_adapter('salesforce', trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'where': \"Industry = 'Technology'\", 'limit': 5})
print(f'Fetched {len(accounts)} accounts')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 accounts
```

---

### **ZoomInfo** (High Priority)

**Credentials Needed**:
- API Key (Bearer token)

**Setup Steps**:
1. Log into ZoomInfo portal
2. Go to Settings → API Access
3. Generate API key
4. Copy key value

**Environment Variables**:
```bash
export SALES_ZOOMINFO_ADAPTER_MODE=live
export SALES_ZOOMINFO_API_KEY=<api-key>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_adapter
adapter = create_adapter('zoominfo', trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'revenue_min': 10000000, 'employees_min': 100, 'limit': 5})
print(f'Fetched {len(accounts)} accounts')
signals = adapter.fetch_buying_signals('example.com')
print(f'Fetched {len(signals)} buying signals')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 accounts
Fetched 3 buying signals
```

---

### **Clearbit** (Medium Priority)

**Credentials Needed**:
- API Key

**Setup Steps**:
1. Sign up at clearbit.com
2. Go to Dashboard → API Keys
3. Copy API key

**Environment Variables**:
```bash
export SALES_CLEARBIT_ADAPTER_MODE=live
export SALES_CLEARBIT_API_KEY=<api-key>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_adapter
adapter = create_adapter('clearbit', trace_id='test')
print('Connection:', adapter.validate_connection())
company = adapter.enrich_company('stripe.com')
print('Company:', company.get('name'))
person = adapter.enrich_contact('john@stripe.com')
print('Person:', person.get('name') if person else 'Not found')
tech = adapter.get_technologies('stripe.com')
print(f'Technologies: {len(tech)} found')
"
```

**Expected Output**:
```
Connection: True
Company: Stripe
Person: John Doe
Technologies: 15 found
```

---

### **HubSpot** (High Priority)

**Credentials Needed**:
- Private App Token (API Key)

**Setup Steps**:
1. Log into HubSpot account
2. Go to Settings → Integrations → Private Apps
3. Click "Create a private app"
4. Grant scopes:
   - `crm.objects.companies.read`
   - `crm.objects.contacts.read`
   - `crm.objects.deals.read`
5. Click "Create app" and copy token

**Environment Variables**:
```bash
export SALES_HUBSPOT_ADAPTER_MODE=live
export SALES_HUBSPOT_API_KEY=<private-app-token>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_adapter
adapter = create_adapter('hubspot', trace_id='test')
print('Connection:', adapter.validate_connection())
companies = adapter.fetch_accounts({'limit': 5})
print(f'Fetched {len(companies)} companies')
if companies:
    company_id = companies[0]['id']
    contacts = adapter.fetch_contacts(company_id)
    print(f'Fetched {len(contacts)} contacts for company')
    deals = adapter.fetch_opportunities(company_id)
    print(f'Fetched {len(deals)} deals for company')
    signals = adapter.fetch_buying_signals(company_id)
    print(f'Fetched {len(signals)} buying signals')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 companies
Fetched 3 contacts for company
Fetched 2 deals for company
Fetched 2 buying signals
```

---

### **6sense** (Medium Priority - Phase 4) 🎉

**Credentials Needed**:
- API Key

**Setup Steps**:
1. Log into 6sense admin portal
2. Navigate to Settings → Integrations → API Access
3. Click "Generate API Key"
4. Copy key value

**Environment Variables**:
```bash
export SALES_SIXSENSE_ADAPTER_MODE=live
export SALES_SIXSENSE_API_KEY=<api-key>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_sixsense_adapter
adapter = create_sixsense_adapter(trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'score_min': 70, 'limit': 5})
print(f'Fetched {len(accounts)} high-intent accounts')
score = adapter.get_account_score(accounts[0]['id']) if accounts else None
print(f'Intent score: {score}')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 high-intent accounts
Intent score: {'account_id': '123', 'score': 85, 'velocity': 'increasing'}
```

---

### **Apollo.io** (Medium Priority - Phase 4) 🎉

**Credentials Needed**:
- API Key

**Setup Steps**:
1. Log into Apollo.io dashboard
2. Go to Settings → Integrations
3. Click "API" tab
4. Copy or generate API key

**Environment Variables**:
```bash
export SALES_APOLLO_ADAPTER_MODE=live
export SALES_APOLLO_API_KEY=<api-key>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_apollo_adapter
adapter = create_apollo_adapter(trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'industry': 'Software', 'limit': 5})
print(f'Fetched {len(accounts)} accounts')
verification = adapter.verify_email('test@example.com')
print(f'Email verification: {verification}')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 accounts
Email verification: {'valid': True, 'deliverable': True, 'score': 95}
```

---

### **Pipedrive** (Medium Priority - Phase 4) 🎉

**Credentials Needed**:
- API Token

**Setup Steps**:
1. Log into Pipedrive
2. Go to Settings → Personal Preferences → API
3. Copy or generate personal API token

**Environment Variables**:
```bash
export SALES_PIPEDRIVE_ADAPTER_MODE=live
export SALES_PIPEDRIVE_API_TOKEN=<api-token>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_pipedrive_adapter
adapter = create_pipedrive_adapter(trace_id='test')
print('Connection:', adapter.validate_connection())
orgs = adapter.fetch_accounts({'limit': 5})
print(f'Fetched {len(orgs)} organizations')
deals = adapter.fetch_opportunities({'status': 'open', 'limit': 5})
print(f'Fetched {len(deals)} open deals')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 organizations
Fetched 5 open deals
```

---

### **Crunchbase** (Low Priority - Phase 4) 🎉

**Credentials Needed**:
- API Key

**Setup Steps**:
1. Sign up for Crunchbase Pro account
2. Navigate to Account Settings → API Access
3. Generate API key
4. Copy key value

**Environment Variables**:
```bash
export SALES_CRUNCHBASE_ADAPTER_MODE=live
export SALES_CRUNCHBASE_API_KEY=<api-key>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_crunchbase_adapter
adapter = create_crunchbase_adapter(trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'funding_total_min': 5000000, 'limit': 5})
print(f'Fetched {len(accounts)} funded companies')
funding = adapter.get_funding_rounds(accounts[0]['id']) if accounts else []
print(f'Funding rounds: {len(funding)}')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 funded companies
Funding rounds: 3
```

---

### **BuiltWith** (Low Priority - Phase 4) 🎉

**Credentials Needed**:
- API Key

**Setup Steps**:
1. Sign up for BuiltWith account
2. Go to API Documentation section
3. Generate API key from account dashboard
4. Copy key value

**Environment Variables**:
```bash
export SALES_BUILTWITH_ADAPTER_MODE=live
export SALES_BUILTWITH_API_KEY=<api-key>
```

**Test Command**:
```bash
python -c "
from cuga.adapters.sales.factory import create_builtwith_adapter
adapter = create_builtwith_adapter(trace_id='test')
print('Connection:', adapter.validate_connection())
accounts = adapter.fetch_accounts({'technology': 'Salesforce', 'limit': 5})
print(f'Fetched {len(accounts)} companies using Salesforce')
tech_profile = adapter.get_technology_profile('example.com')
print(f'Technologies detected: {len(tech_profile.get(\"technologies\", []))}')
"
```

**Expected Output**:
```
Connection: True
Fetched 5 companies using Salesforce
Technologies detected: 12
```

---

## 🧪 Full Test Suite

### **Run All Tests**
```bash
python scripts/setup_data_feeds.py
```

**Expected Output**:
```
=== CUGAr-SALES Data Feed Setup & Validation ===

Phase 1-3 Adapters:
✓ PASS Mock Adapters
✓ PASS IBM Sales Cloud
✓ PASS Salesforce
✓ PASS ZoomInfo
✓ PASS Clearbit
✓ PASS HubSpot

Phase 4 Adapters (NEW):
✓ PASS 6sense
✓ PASS Apollo.io
✓ PASS Pipedrive
✓ PASS Crunchbase
✓ PASS BuiltWith

Results: 11 passed, 0 failed, 0 skipped (100% coverage)
```

---

## 🐛 Troubleshooting

### **Import Errors**
```
ModuleNotFoundError: No module named 'httpx'
```
**Solution**: Install dependencies
```bash
pip install httpx pyyaml click python-dotenv
```

### **Authentication Errors**

**IBM Sales Cloud**:
```
ValueError: IBM adapter requires client_id, client_secret, api_key, and tenant_id
```
**Solution**: Export all 4 required credentials

**Salesforce**:
```
ValueError: Salesforce adapter requires client_id, client_secret, username, password
```
**Solution**: Export credentials + security_token (if needed)

**ZoomInfo/Clearbit/HubSpot/6sense/Apollo/Crunchbase/BuiltWith**:
```
ValueError: {Adapter} requires api_key in credentials
```
**Solution**: Export `SALES_{VENDOR}_API_KEY`

**Pipedrive**:
```
ValueError: Pipedrive adapter requires api_token in credentials
```
**Solution**: Export `SALES_PIPEDRIVE_API_TOKEN`

### **Connection Failures**

**Timeout Errors**:
```
httpx.TimeoutException: Read timeout
```
**Solution**: Check network connection, increase timeout in adapter

**Rate Limiting**:
```
Exception: Rate limit hit. Retry after 60 seconds.
```
**Solution**: Wait for retry_after duration, check API quota

**404 Not Found**:
```
Returns empty list or None
```
**Solution**: Verify account/contact/opportunity IDs exist

### **Mock Mode Fallback**
If adapter imports fail, system automatically falls back to mock mode:
```
Adapter factory falling back to mock for vendor: {vendor}
```
**Solution**: Check credentials, ensure `ADAPTER_MODE=live` set

---

## 📊 Validation Checklist

### **Before Testing**
- [ ] Dependencies installed (`httpx`, `pyyaml`, `click`)
- [ ] `.env.sales` file created from template
- [ ] Credentials obtained for all adapters
- [ ] Environment variables exported
- [ ] Network connection available

### **During Testing**
- [ ] Mock adapters pass (offline test)
- [ ] Connection validation passes for each adapter
- [ ] Sample data fetched successfully
- [ ] No authentication errors
- [ ] No rate limit errors
- [ ] Response schemas match expected format

### **After Testing**
- [ ] Document any API quirks or edge cases
- [ ] Update `.env.sales.example` if needed
- [ ] Note rate limits and quotas
- [ ] Record sample response formats
- [ ] Update documentation with findings

---

## 🎯 Success Criteria

**All 10 adapters should:**
1. ✅ Authenticate successfully
2. ✅ Fetch sample data (accounts, contacts, opportunities)
3. ✅ Return normalized schemas
4. ✅ Handle errors gracefully (404, 401, 429)
5. ✅ Emit observability events
6. ✅ Complete within timeout limits (10s)

**Final Output**:
```
Results: 11 passed, 0 failed, 0 skipped (100% coverage)
```

---

## 📞 Support

**Documentation**:
- `PHASE_4_FINAL_SUMMARY.md` - Complete Phase 4 summary
- `QUICK_REFERENCE.md` - Quick reference with examples
- `docs/sales/DATA_FEED_INTEGRATION.md` - Full integration guide
- `EXTERNAL_DATA_FEEDS_STATUS.md` - Progress tracker (100% complete)
- `.env.sales.example` - Environment configuration reference

**Interactive Setup**:
```bash
python3 -m cuga.frontend.setup_wizard
```

**Common Issues**:
- Authentication: Check credentials in `.env.sales`
- Timeouts: Increase timeout in adapter config
- Rate limits: Check API quota and retry_after headers
- Schema mismatches: Verify API version compatibility

---

**End of Quick Test Guide**

Ready to test? Run: `python scripts/setup_data_feeds.py`

🚀 100% Coverage Complete - All 10 Adapters Ready!

