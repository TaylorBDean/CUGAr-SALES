# Phase 4 Roadmap: Completing External Data Integration (50% → 100%)

**Status**: 📋 Planning  
**Current Coverage**: 5/10 adapters (50%)  
**Target Coverage**: 10/10 adapters (100%)  
**Estimated Timeline**: 4-5 days

---

## 🎯 Phase 4 Objectives

**Goal**: Complete remaining 5 adapters to achieve 100% external data integration coverage.

**Remaining Adapters**:
1. **6sense** (Predictive Intent) - High Priority
2. **Apollo.io** (Contact Enrichment) - High Priority
3. **Pipedrive** (SMB CRM) - Medium Priority
4. **Crunchbase** (Funding Events) - Medium Priority
5. **BuiltWith** (Tech Tracking) - Low Priority

---

## 📦 Adapter Specifications

### **1. 6sense Adapter** (Predictive Intent Platform)

**Priority**: 🟡 High  
**Estimated Effort**: 1-2 days  
**Complexity**: High (predictive analytics API)

**File**: `src/cuga/adapters/sales/sixsense_live.py`  
**Tests**: `tests/adapters/test_sixsense_live.py`

**Authentication**:
- API Key authentication (Bearer token)

**Core Methods**:
```python
def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search accounts with intent filters.
    
    Filters:
    - intent_score_min: Minimum intent score (0-100)
    - intent_score_max: Maximum intent score (0-100)
    - buying_stage: awareness, consideration, decision, purchase
    - keywords: List of keywords being researched
    - segment_id: Intent segment filter
    """

def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch contacts for account (if available)."""

def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
    """Fetch intent signals for account.
    
    Returns:
    - intent_surge: Sudden increase in research activity
    - keyword_match: Researching relevant keywords
    - buying_stage_advance: Moved to later buying stage
    - segment_engagement: Active in intent segment
    """

def get_account_score(self, domain: str) -> Dict[str, Any]:
    """Get predictive intent score (0-100) for domain."""

def get_intent_segments(self, domain: str) -> List[Dict[str, Any]]:
    """Get intent segments (topics) for domain."""

def get_keyword_research(self, domain: str) -> List[Dict[str, Any]]:
    """Get keywords being researched by account."""
```

**API Endpoints**:
- `GET /v1/accounts` - Search accounts with intent filters
- `GET /v1/accounts/{id}` - Get account details + intent score
- `GET /v1/accounts/{id}/intent` - Get intent data
- `GET /v1/accounts/{id}/keywords` - Get keyword research
- `GET /v1/accounts/{id}/segments` - Get intent segments
- `GET /v1/accounts/{id}/buying_stage` - Get buying stage

**Signal Types** (4):
- `intent_surge`: Confidence 0.8-1.0 (based on velocity)
- `keyword_match`: Confidence 0.7-0.9 (based on relevance)
- `buying_stage_advance`: Confidence 0.8-0.95 (based on stage)
- `segment_engagement`: Confidence 0.6-0.8

**Normalized Schema**:
```python
{
    "id": "6sense-account-123",
    "name": "Example Corp",
    "domain": "example.com",
    "intent_score": 85,  # 0-100
    "buying_stage": "decision",  # awareness, consideration, decision, purchase
    "keywords": ["crm software", "sales automation"],
    "segments": ["Sales Technology", "CRM Buyers"],
    "metadata": {
        "score_change": 15,  # Last 30 days
        "top_keywords": [...],
        "intent_velocity": "high"
    }
}
```

**Test Coverage** (target 15+ tests):
- Initialization, config validation
- Account search with intent filters
- Intent score retrieval
- Keyword research
- Segment retrieval
- Buying stage tracking
- Signal derivation (4 types)
- Error handling (401, 429, timeout)
- Pagination (if applicable)
- Schema normalization

**Estimated LOC**: 500-600 lines (adapter + tests)

---

### **2. Apollo.io Adapter** (Contact Enrichment)

**Priority**: 🟡 High  
**Estimated Effort**: 1 day  
**Complexity**: Medium (enrichment API)

**File**: `src/cuga/adapters/sales/apollo_live.py`  
**Tests**: `tests/adapters/test_apollo_live.py`

**Authentication**:
- API Key authentication (header-based)

**Core Methods**:
```python
def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search companies.
    
    Filters:
    - industry: Industry filter
    - revenue_min/max: Revenue range
    - employees_min/max: Employee range
    - location: Geographic filter
    """

def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search contacts with filters.
    
    Filters:
    - title: Job title filter
    - seniority: Seniority level
    - department: Department filter
    - email_status: verified, unverified
    """

def enrich_contact(self, email: str) -> Optional[Dict[str, Any]]:
    """Enrich contact by email (get full profile)."""

def verify_email(self, email: str) -> Dict[str, Any]:
    """Verify email deliverability.
    
    Returns:
    - status: valid, invalid, unknown
    - deliverable: True/False
    - free_email: True/False (Gmail, Yahoo, etc.)
    """

def get_engagement(self, contact_id: str) -> List[Dict[str, Any]]:
    """Get engagement history (email opens, clicks, etc.)."""

def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
    """Derive buying signals from enrichment.
    
    Returns:
    - email_verified: Contact email verified
    - engagement_detected: Contact engaged with outreach
    """
```

**API Endpoints**:
- `POST /v1/organizations/search` - Search companies
- `POST /v1/people/search` - Search contacts
- `POST /v1/people/match` - Enrich contact by email
- `POST /v1/emailer_campaigns/{id}/email_statuses` - Get engagement
- `POST /v1/email_verifier/verify` - Verify email

**Signal Types** (2):
- `email_verified`: Confidence 0.9
- `engagement_detected`: Confidence 0.7-0.9 (based on action type)

**Estimated LOC**: 400-500 lines (adapter + tests)

---

### **3. Pipedrive Adapter** (SMB CRM)

**Priority**: 🟢 Medium  
**Estimated Effort**: 1 day  
**Complexity**: Low (simple CRM API)

**File**: `src/cuga/adapters/sales/pipedrive_live.py`  
**Tests**: `tests/adapters/test_pipedrive_live.py`

**Authentication**:
- API Token authentication (query parameter)

**Core Methods**:
```python
def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch organizations."""

def fetch_contacts(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch persons for organization."""

def fetch_opportunities(self, account_id: str, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Fetch deals for organization."""

def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
    """Derive signals from deal activity.
    
    Returns:
    - deal_created: New deal created
    - deal_progression: Deal moved forward
    - activity_logged: Recent activity
    """
```

**API Endpoints**:
- `GET /v1/organizations` - List organizations
- `GET /v1/persons` - List persons
- `GET /v1/deals` - List deals
- `GET /v1/activities` - List activities

**Signal Types** (3):
- `deal_created`: Confidence 0.7
- `deal_progression`: Confidence 0.8
- `activity_logged`: Confidence 0.6

**Estimated LOC**: 350-450 lines (adapter + tests)

---

### **4. Crunchbase Adapter** (Funding Events)

**Priority**: 🟢 Medium  
**Estimated Effort**: 1 day  
**Complexity**: Low (read-only API)

**File**: `src/cuga/adapters/sales/crunchbase_live.py`  
**Tests**: `tests/adapters/test_crunchbase_live.py`

**Authentication**:
- API Key authentication (header-based)

**Core Methods**:
```python
def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search organizations.
    
    Filters:
    - funding_round_min/max: Funding amount range
    - funding_stage: seed, series_a, series_b, etc.
    - founded_year_min/max: Company age
    """

def enrich_company(self, domain: str) -> Optional[Dict[str, Any]]:
    """Get company profile by domain."""

def get_funding_rounds(self, organization_id: str) -> List[Dict[str, Any]]:
    """Get funding history."""

def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
    """Derive signals from funding events.
    
    Returns:
    - funding_event: New funding round announced
    - acquisition: Company acquired
    - ipo: IPO filed/completed
    - executive_change: Leadership transition
    """
```

**API Endpoints**:
- `GET /v4/entities/organizations` - Search organizations
- `GET /v4/entities/organizations/{id}` - Get organization
- `GET /v4/entities/organizations/{id}/funding_rounds` - Funding history

**Signal Types** (4):
- `funding_event`: Confidence 0.9
- `acquisition`: Confidence 1.0
- `ipo`: Confidence 1.0
- `executive_change`: Confidence 0.8

**Estimated LOC**: 350-450 lines (adapter + tests)

---

### **5. BuiltWith Adapter** (Tech Tracking)

**Priority**: ⚪ Low  
**Estimated Effort**: 1 day  
**Complexity**: Low (tech tracking API)

**File**: `src/cuga/adapters/sales/builtwith_live.py`  
**Tests**: `tests/adapters/test_builtwith_live.py`

**Authentication**:
- API Key authentication (query parameter)

**Core Methods**:
```python
def fetch_accounts(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Search by technology usage.
    
    Filters:
    - technology: Specific technology (e.g., "Salesforce")
    - category: Tech category (e.g., "CRM")
    """

def get_technologies(self, domain: str) -> List[Dict[str, Any]]:
    """Get current tech stack for domain."""

def get_tech_history(self, domain: str) -> List[Dict[str, Any]]:
    """Get historical tech stack changes."""

def fetch_buying_signals(self, account_id: str) -> List[Dict[str, Any]]:
    """Derive signals from tech changes.
    
    Returns:
    - tech_adoption: New technology adopted
    - tech_removal: Technology removed
    - tech_upgrade: Technology version upgraded
    """
```

**API Endpoints**:
- `GET /v20/api.json` - Get tech stack for domain
- `GET /trends/v9/api.json` - Get tech trends

**Signal Types** (3):
- `tech_adoption`: Confidence 0.8
- `tech_removal`: Confidence 0.7
- `tech_upgrade`: Confidence 0.6

**Estimated LOC**: 300-400 lines (adapter + tests)

---

## 📊 Phase 4 Metrics

### **Code Volume Estimates**

| Adapter | Adapter LOC | Test LOC | Total LOC |
|---------|-------------|----------|-----------|
| 6sense | 550 | 450 | 1,000 |
| Apollo.io | 450 | 350 | 800 |
| Pipedrive | 400 | 350 | 750 |
| Crunchbase | 400 | 350 | 750 |
| BuiltWith | 350 | 300 | 650 |
| **Total** | **2,150** | **1,800** | **3,950** |

### **Combined Project Totals** (Phase 1-4)

| Metric | Phase 1-3 | Phase 4 | Total |
|--------|-----------|---------|-------|
| Adapters | 5 | 5 | 10 |
| Adapter LOC | 2,552 | 2,150 | 4,702 |
| Test LOC | 2,106 | 1,800 | 3,906 |
| Unit Tests | 62 | ~70 | ~132 |
| API Endpoints | 19 | ~20 | ~39 |
| Signal Types | 18 | 14 | 32 |
| **Total LOC** | **5,548** | **3,950** | **9,498** |

---

## 🗓️ Implementation Timeline

### **Week 1** (Days 1-2)
**Day 1**: 6sense Adapter
- Morning: API research, authentication setup
- Afternoon: Core methods (fetch_accounts, get_account_score)
- Evening: Intent signals, keyword research

**Day 2**: 6sense Testing + Apollo.io Start
- Morning: 6sense unit tests (15+), documentation
- Afternoon: Apollo.io adapter (company search, contact search)
- Evening: Apollo.io enrichment methods

### **Week 1** (Days 3-4)
**Day 3**: Apollo.io Completion + Pipedrive Start
- Morning: Apollo.io unit tests (12+), email verification
- Afternoon: Pipedrive adapter (organizations, persons)
- Evening: Pipedrive deals, activities

**Day 4**: Pipedrive + Crunchbase
- Morning: Pipedrive unit tests (12+), documentation
- Afternoon: Crunchbase adapter (organization search, funding rounds)
- Evening: Crunchbase signals, unit tests (12+)

### **Week 2** (Day 5)
**Day 5**: BuiltWith + Final Integration
- Morning: BuiltWith adapter (tech stack, history)
- Afternoon: BuiltWith unit tests (10+)
- Evening: Final integration, documentation updates

---

## ✅ Acceptance Criteria

### **Per Adapter**
- [ ] Adapter file created (`src/cuga/adapters/sales/{vendor}_live.py`)
- [ ] Test file created (`tests/adapters/test_{vendor}_live.py`)
- [ ] Minimum 10 unit tests written
- [ ] All tests pass with mocked HTTP responses
- [ ] Factory routing updated
- [ ] Setup script updated with test function
- [ ] Authentication implemented and validated
- [ ] Core methods implemented (fetch_accounts, fetch_contacts, etc.)
- [ ] Buying signals derived
- [ ] Schema normalization complete
- [ ] Error handling (404, 401, 429, timeouts)
- [ ] Observability events emitted
- [ ] SafeClient compliance (10s timeout, auto-retry)
- [ ] Documentation updated

### **Phase 4 Complete**
- [ ] All 5 adapters implemented
- [ ] All unit tests passing (70+ new tests)
- [ ] Factory routes all 10 vendors
- [ ] Setup script tests all 10 adapters
- [ ] Environment configuration updated (`.env.sales.example`)
- [ ] Documentation updated:
  - [ ] `PHASE_4_COMPLETE.md` created
  - [ ] `EXTERNAL_DATA_FEEDS_STATUS.md` updated (100% coverage)
  - [ ] `docs/sales/DATA_FEED_INTEGRATION.md` updated
  - [ ] `QUICK_TEST_GUIDE.md` updated with new adapters
- [ ] Verification outputs created (line counts, test counts)
- [ ] Grand totals calculated (~9,500 LOC, ~132 tests)

---

## 🎯 Success Metrics

### **Coverage**
- [x] Phase 1-3: 5/10 adapters (50%)
- [ ] Phase 4: 10/10 adapters (100%)

### **Quality**
- [x] Phase 1-3: 62 tests passing
- [ ] Phase 4: ~132 tests passing (100%)
- [ ] All adapters follow consistent patterns
- [ ] All adapters normalize to canonical schema
- [ ] All adapters emit observability events
- [ ] All adapters comply with SafeClient standards

### **Production Readiness**
- [ ] 100% adapter coverage
- [ ] ~132 unit tests (100% passing)
- [ ] Comprehensive error handling
- [ ] Full observability integration
- [ ] Complete documentation
- [ ] Hot-swap architecture validated for all 10 adapters

---

## 🚀 Post-Phase 4 Next Steps

### **Immediate** (1-2 days)
1. Obtain credentials for all 10 adapters
2. Run live tests: `python scripts/setup_data_feeds.py`
3. Validate: `✓ PASS` for all 10 adapters
4. Smoke tests with real data

### **Short-Term** (1 week)
1. Integration tests (real API calls with credentials)
2. Performance optimization (caching, batching)
3. Rate limit monitoring and optimization
4. Cost tracking (API usage, quotas)

### **Long-Term** (2-4 weeks)
1. Production deployment (staging → prod)
2. Monitor observability (error rates, latency)
3. User feedback collection
4. Iterative improvements
5. Additional adapters (if needed)

---

## 📋 Pre-Phase 4 Checklist

**Before Starting Implementation**:
- [ ] Review Phase 1-3 learnings
- [ ] Study vendor API documentation:
  - [ ] 6sense API docs
  - [ ] Apollo.io API docs
  - [ ] Pipedrive API docs
  - [ ] Crunchbase API docs
  - [ ] BuiltWith API docs
- [ ] Obtain sandbox/test credentials (if available)
- [ ] Set up API testing tools (Postman, curl)
- [ ] Review AGENTS.md guardrails
- [ ] Review existing adapter patterns
- [ ] Prepare development environment

**Dependencies**:
- [x] httpx installed
- [x] pyyaml installed
- [x] click installed
- [x] python-dotenv installed
- [x] pytest installed

---

## 🎊 Phase 4 Completion Vision

**Upon Completion**:
- ✅ 10/10 external data adapters (100% coverage)
- ✅ ~9,500 lines of production code
- ✅ ~132 comprehensive unit tests
- ✅ 32 buying signal types
- ✅ ~39 API endpoints integrated
- ✅ Hot-swap architecture for all adapters
- ✅ Complete sales automation platform
- ✅ Ready for enterprise production deployment

**Capabilities**:
- **CRM Integration**: Salesforce, HubSpot, Pipedrive (3 vendors)
- **Intent Signals**: ZoomInfo, 6sense (2 vendors)
- **Enrichment**: Clearbit, Apollo.io (2 vendors)
- **Funding Events**: Crunchbase (1 vendor)
- **Tech Tracking**: Clearbit, BuiltWith (2 vendors)
- **Buying Signals**: 32 types across 10 vendors

**System Value**:
- Multi-vendor coverage (no vendor lock-in)
- Unified interface (consistent API across vendors)
- Production-ready (error handling, observability, security)
- Scalable (hot-swap, caching, rate limiting)
- Testable (comprehensive unit test coverage)
- Maintainable (clear patterns, documentation)

---

**End of Phase 4 Roadmap**

Ready to proceed? Start with 6sense adapter implementation.

🚀 Let's complete the journey to 100% coverage!
