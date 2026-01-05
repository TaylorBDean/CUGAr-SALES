# Phase 4 Intelligence Deployment Guide

**Document Status**: Production-Ready  
**Version**: 1.0.0  
**Last Updated**: 2026-01-03  
**UAT Status**: 4/4 tests passing (100%)

---

## Executive Summary

Phase 4 Intelligence provides **win/loss analysis** and **buyer persona extraction** capabilities for sales leadership. This is a **standalone capability** requiring no CRM integration, SDR workflows, or real-time features.

**Target Users**: VP Sales, Sales Ops, RevOps  
**Use Case**: Quarterly ICP reviews, territory planning, sales process optimization  
**Deployment Timeline**: Week 7 (staging validation), Week 8 (production)

---

## What's Included

### Functions
1. **`analyze_win_loss_patterns()`**
   - Input: Historical closed deals (won/lost) with account data
   - Output: Win patterns (industry, revenue), loss patterns (reasons), ICP recommendations, qualification insights
   - Example: "Technology accounts 10-50M revenue show 82% win rate → Target more Technology"

2. **`extract_buyer_personas()`**
   - Input: Won deals with contact data
   - Output: Buyer personas (title patterns, roles, decision makers)
   - Example: "VP Sales appears in 8/10 won deals as champion → Target VP Sales"

### Validation Status
- ✅ **Unit Tests**: 14/14 passing (`tests/sales/test_intelligence.py`)
- ✅ **UAT Tests**: 4/4 passing (`scripts/uat/run_phase4_uat.py`)
  - Basic win/loss analysis (60% win rate detection)
  - Industry pattern detection (Technology 100% win rate identified)
  - Buyer persona extraction (VP Sales + CFO patterns detected)
  - ICP recommendations (Technology targeting suggested)
- ✅ **Config Validation**: Budget enforcement, Python 3.12.3, offline mode verified

---

## Prerequisites

### Environment
- **Python**: 3.12+ (verified in config validation)
- **Dependencies**: See `pyproject.toml` (no external API requirements)
- **Budget**: `AGENT_BUDGET_CEILING=100` (default, no escalation needed for batch analysis)
- **Observability**: Optional (OTEL/LangFuse/LangSmith for trace visibility)

### Data Requirements
- **Format**: JSON/dict with fields:
  - `deal_id` (string)
  - `outcome` (string: "won"/"lost")
  - `account` (dict with `name`, `industry`, `revenue`)
  - `deal_value` (number)
  - `sales_cycle_days` (number)
  - `qualification_score` (float 0-1)
  - `loss_reason` (string, for lost deals)
  - `contacts` (list of dicts with `name`, `title`, `department`, `role`, `seniority`, for persona extraction)
- **Source**: CRM exports (manual quarterly export, no live integration)
- **Volume**: 20-200 deals per analysis (min 5 for pattern detection)

### Access
- **Offline Mode**: No network required (deterministic, local-only execution)
- **CRM**: Not required (manual data export from existing CRM)
- **Approval**: Sales leadership approval for data access (PII considerations)

---

## Deployment Steps

### Week 7: Staging Validation

#### Step 1: Environment Setup (30 min)
```bash
# Clone/update repository
cd /path/to/CUGAr-SALES
git checkout main
git pull

# Verify Python version
python3 --version  # Should be 3.12+

# Install dependencies
pip install -e .

# Validate configuration
python scripts/deployment/validate_config.py
# Expected: ✅ Configuration valid, No CRM (offline mode), Budget: 100
```

#### Step 2: Run Phase 4 UAT Tests (10 min)
```bash
# Run Phase 4-specific UAT tests
python scripts/uat/run_phase4_uat.py

# Expected Output:
# Phase 4 UAT Results: 4/4 passed (100%)
# ✅ All Phase 4 UAT tests passed - Ready for production deployment
```

#### Step 3: Export Q4 2025 Data (Sales Ops, 2 hours)
1. Log into CRM (HubSpot/Salesforce/Pipedrive)
2. Export closed deals (Oct 1 - Dec 31, 2025):
   - Deal ID, Outcome (Won/Lost), Account Name, Industry, Revenue
   - Deal Value, Sales Cycle (days), Qualification Score (if available)
   - Loss Reason (for lost deals)
   - Contact Names, Titles, Departments, Roles (for won deals)
3. Save as `q4_2025_deals.json` in expected format

**Data Format Example**:
```json
[
  {
    "deal_id": "D12345",
    "outcome": "won",
    "account": {
      "name": "Acme Corp",
      "industry": "Technology",
      "revenue": 25000000
    },
    "deal_value": 100000,
    "sales_cycle_days": 45,
    "qualification_score": 0.85,
    "contacts": [
      {
        "name": "John Doe",
        "title": "VP Sales",
        "department": "Sales",
        "role": "champion",
        "seniority": "VP"
      },
      {
        "name": "Jane Smith",
        "title": "CFO",
        "department": "Finance",
        "role": "decision_maker",
        "seniority": "C-level"
      }
    ]
  },
  {
    "deal_id": "D67890",
    "outcome": "lost",
    "account": {
      "name": "Beta Industries",
      "industry": "Manufacturing",
      "revenue": 50000000
    },
    "deal_value": 75000,
    "sales_cycle_days": 60,
    "qualification_score": 0.50,
    "loss_reason": "price"
  }
]
```

#### Step 4: Test Analysis (VP Sales, 1 hour)
```python
# Load data
import json
with open("q4_2025_deals.json") as f:
    deals = json.load(f)

# Run win/loss analysis
from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns

analysis = analyze_win_loss_patterns(
    inputs={
        "deals": deals,
        "min_deals_for_pattern": 5  # Require 5+ deals for pattern confidence
    },
    context={
        "trace_id": "q4-2025-review",
        "profile": "sales"
    }
)

# Review results
print(f"Win Rate: {analysis['summary']['win_rate']:.0%}")
print(f"Avg Deal Value (Won): ${analysis['summary']['avg_deal_value']:,.0f}")
print(f"Avg Sales Cycle: {analysis['summary']['avg_sales_cycle']:.0f} days")

print("\nTop Win Patterns:")
for pattern in analysis['win_patterns'][:3]:
    print(f"  • {pattern['pattern_value']}: {pattern['win_rate']:.0%} win rate "
          f"(confidence: {pattern['confidence']:.2f})")
    print(f"    Recommendation: {pattern['recommendation']}")

print("\nTop Loss Reasons:")
for pattern in analysis['loss_patterns'][:3]:
    print(f"  • {pattern['reason']}: {pattern['percentage']:.0%} of losses")
    print(f"    Recommendation: {pattern['recommendation']}")

print("\nICP Recommendations:")
for rec in analysis['icp_recommendations']:
    print(f"  • {rec['attribute']}: {rec['recommended']}")
    print(f"    Rationale: {rec['rationale']}")
```

**Expected Insights**:
- Win rate breakdown (overall, by industry, by revenue band)
- Industry win patterns (e.g., "Technology: 82% win rate → Target more")
- Revenue sweet spots (e.g., "$10-50M: 78% win rate → Focus here")
- Loss reason breakdown (e.g., "Price: 39% → Consider value-based pricing")
- ICP recommendations (data-driven targeting adjustments)
- Qualification accuracy (optimal threshold, false positive/negative rates)

#### Step 5: Extract Buyer Personas (VP Sales, 30 min)
```python
# Filter won deals
won_deals = [d for d in deals if d["outcome"] == "won"]

# Extract personas
from cuga.modular.tools.sales.intelligence import extract_buyer_personas

personas = extract_buyer_personas(
    inputs={
        "deals": won_deals,
        "min_occurrences": 3  # Require 3+ occurrences for persona
    },
    context={
        "trace_id": "q4-2025-personas",
        "profile": "sales"
    }
)

# Review personas
print("Common Buyer Personas:")
for persona in personas['personas']:
    print(f"\n  • {persona['title_pattern']} ({persona['occurrence_count']}x)")
    print(f"    Typical Roles: {', '.join(persona['typical_roles'])}")
    print(f"    Recommendation: {persona['recommendation']}")

print("\nDecision Maker Patterns:")
dm_patterns = personas['decision_maker_patterns']
print(f"  • Most Common Title: {dm_patterns['most_common_title']}")
print(f"  • Most Common Seniority: {dm_patterns['most_common_seniority']}")
```

**Expected Insights**:
- Top buyer personas (e.g., "VP Sales appears 8x as champion")
- Decision maker patterns (e.g., "CFO most common decision maker")
- Role distribution (champions vs decision makers vs influencers)
- Targeting recommendations (who to prioritize in outreach)

#### Step 6: Leadership Review (VP Sales + CRO, 2 hours)
- Review analysis results in leadership meeting
- Validate insights against known Q4 performance
- Identify action items for Q1 2026 (territory adjustments, ICP refinements, process changes)
- Approve production deployment if insights are actionable

**Success Criteria for Staging**:
- ✅ UAT tests pass (4/4)
- ✅ Q4 data loads successfully (no parsing errors)
- ✅ Analysis completes in <5 minutes for 100 deals
- ✅ Insights are actionable (leadership can identify 3+ action items)
- ✅ No PII leakage (logs redacted, trace_id propagated)

---

### Week 8: Production Deployment

#### Step 1: Production Environment Setup (1 hour)
```bash
# Production server/environment
cd /opt/cuga-sales  # Or wherever production code lives
git checkout v1.0.0  # Tag for Phase 4 release

# Install dependencies
pip install -e .

# Validate config in production
python scripts/deployment/validate_config.py

# Set production env vars (if using observability)
export OTEL_EXPORTER_OTLP_ENDPOINT="https://otel.yourcompany.com"
export OTEL_SERVICE_NAME="cuga-sales-intelligence"
export LANGFUSE_PUBLIC_KEY="pk_..."  # Optional
export LANGFUSE_SECRET_KEY="sk_..."  # Optional
```

#### Step 2: Schedule Quarterly Analysis (Sales Ops, 30 min)
Create cron job or scheduled task for quarterly analysis:

```bash
# crontab entry (run first Monday of quarter at 8am)
0 8 1 1,4,7,10 * /opt/cuga-sales/scripts/run_quarterly_analysis.sh
```

**Sample Script** (`scripts/run_quarterly_analysis.sh`):
```bash
#!/bin/bash
# Quarterly ICP Analysis Automation

QUARTER=$(date +%Y-Q%q)
DATA_DIR="/data/cuga-sales"
REPORT_DIR="/reports/cuga-sales"

echo "Starting Quarterly Analysis: $QUARTER"

# 1. Sales Ops manually exports deals (not automated - requires CRM login)
echo "MANUAL STEP: Export closed deals from CRM to $DATA_DIR/${QUARTER}_deals.json"
echo "Press Enter when export is complete..."
read

# 2. Run analysis
python3 << EOF
import json
from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns, extract_buyer_personas

# Load data
with open("$DATA_DIR/${QUARTER}_deals.json") as f:
    deals = json.load(f)

# Analysis
analysis = analyze_win_loss_patterns(
    inputs={"deals": deals, "min_deals_for_pattern": 5},
    context={"trace_id": "$QUARTER-analysis", "profile": "sales"}
)

won_deals = [d for d in deals if d["outcome"] == "won"]
personas = extract_buyer_personas(
    inputs={"deals": won_deals, "min_occurrences": 3},
    context={"trace_id": "$QUARTER-personas", "profile": "sales"}
)

# Save results
import json
with open("$REPORT_DIR/${QUARTER}_analysis.json", "w") as f:
    json.dump({"analysis": analysis, "personas": personas}, f, indent=2)

print(f"Analysis complete: {analysis['summary']['win_rate']:.0%} win rate")
EOF

# 3. Generate human-readable report (optional)
echo "Generating report..."
python3 scripts/generate_analysis_report.py \
    --input "$REPORT_DIR/${QUARTER}_analysis.json" \
    --output "$REPORT_DIR/${QUARTER}_report.pdf"

echo "Quarterly Analysis Complete: $REPORT_DIR/${QUARTER}_report.pdf"
```

#### Step 3: User Training (Sales Leadership, 1 hour)
- Demo live analysis with real Q4 data
- Walk through win/loss patterns, ICP recommendations, buyer personas
- Show how to identify action items (territory adjustments, messaging changes)
- Provide access to analysis scripts and documentation

#### Step 4: Production Validation (Week 8, 1 hour)
```bash
# Run production UAT tests with real data
python scripts/uat/run_phase4_uat.py

# Monitor first production run
tail -f /var/log/cuga-sales/intelligence.log

# Check observability (if configured)
# View traces in OTEL/LangFuse/LangSmith UI
```

**Production Health Checks**:
- ✅ Quarterly analysis completes in <10 minutes for 200 deals
- ✅ Trace_id propagates through all operations
- ✅ Logs are PII-safe (no account names/contacts in logs, only trace_id)
- ✅ Budget enforcement active (warn at 80%, block at 100% if configured)
- ✅ Leadership can access results via shared report directory

---

## Monitoring & Maintenance

### Observability
If observability configured (optional):

**Metrics to Track**:
- `cuga_intelligence_analysis_duration_ms` - Analysis execution time
- `cuga_intelligence_deals_processed` - Number of deals analyzed
- `cuga_intelligence_patterns_detected` - Win/loss patterns found
- `cuga_intelligence_personas_extracted` - Buyer personas identified

**Alerts to Configure**:
- Analysis duration >10 minutes (investigate performance)
- Win rate <40% or >80% (validate data quality)
- Fewer than 20 deals processed (insufficient data for patterns)

**Grafana Dashboard**:
- Panel 1: Win rate trend (quarterly)
- Panel 2: Top industry win patterns (bar chart)
- Panel 3: Top loss reasons (pie chart)
- Panel 4: Buyer persona frequency (stacked bar)
- Panel 5: Analysis execution time (line chart)

### Maintenance Schedule
- **Weekly**: Check analysis completion (first week of quarter)
- **Monthly**: Review observability metrics (if configured)
- **Quarterly**: Audit data quality (validate exports match CRM)
- **Annually**: Review ICP recommendations accuracy (did predictions hold true?)

---

## Rollback Plan

If issues arise in production:

### Immediate Rollback (15 minutes)
```bash
# Stop any running analyses
pkill -f "cuga.modular.tools.sales.intelligence"

# Revert to previous version (if applicable)
cd /opt/cuga-sales
git checkout <previous-tag>
pip install -e .

# Validate rollback
python scripts/uat/run_phase4_uat.py
```

### Data Recovery
- All analysis results saved to `$REPORT_DIR/${QUARTER}_analysis.json`
- Original CRM exports preserved in `$DATA_DIR/${QUARTER}_deals.json`
- No data modification (read-only operations)
- Re-run analysis from saved exports if needed

---

## Success Metrics

### Week 7 (Staging)
- ✅ UAT tests pass (4/4)
- ✅ Q4 data analysis completes successfully
- ✅ Leadership identifies 3+ actionable insights
- ✅ No PII leakage or security concerns

### Week 8 (Production)
- ✅ First quarterly analysis runs successfully
- ✅ Report delivered to leadership on schedule
- ✅ No production incidents or rollbacks
- ✅ Leadership uses insights for Q1 planning

### Long-Term (6 months)
- ✅ 2 quarterly analyses completed (Q4 2025, Q1 2026)
- ✅ 10% improvement in win rate (Q1 2026 vs Q4 2025)
- ✅ ICP refinements implemented (based on recommendations)
- ✅ Leadership requests Phase 2-3 implementation (proof of value)

---

## Known Limitations

### What Phase 4 Does NOT Include
- ❌ Real-time CRM integration (manual exports required)
- ❌ Live dashboard (batch analysis only)
- ❌ SDR/AE workflows (no account scoring, outreach drafting)
- ❌ Territory management (no capacity/coverage modeling)
- ❌ Predictive analytics (descriptive only, no ML models)
- ❌ Automated outreach (no email sending, approval workflows)

### Future Enhancements (Phases 1-3)
- **Phase 1** (5-6 weeks): Territory intelligence, account scoring, opportunity qualification
- **Phase 2** (1-2 weeks): Live CRM integration (HubSpot, Salesforce, Pipedrive)
- **Phase 3** (1-2 weeks): Outreach drafting, quality assessment, template library

---

## Support & Troubleshooting

### Common Issues

**Issue 1: Analysis returns no patterns**
- **Cause**: Insufficient data (fewer than 5 deals for pattern detection)
- **Solution**: Lower `min_deals_for_pattern` to 3, or wait for more data

**Issue 2: Persona extraction returns no personas**
- **Cause**: Won deals missing contact data
- **Solution**: Ensure CRM exports include contact information for won deals

**Issue 3: Analysis takes >10 minutes**
- **Cause**: Processing 500+ deals
- **Solution**: Split into batches (e.g., analyze by quarter or region separately)

**Issue 4: Qualification insights show "N/A"**
- **Cause**: Deals missing `qualification_score` field
- **Solution**: Estimate scores from deal data, or skip qualification insights

### Getting Help
- **Documentation**: `docs/sales/PHASE_4_COMPLETION.md` (technical details)
- **Tests**: Run `pytest tests/sales/test_intelligence.py -v` (validate environment)
- **UAT**: Run `python scripts/uat/run_phase4_uat.py` (end-to-end validation)
- **Logs**: Check trace_id in logs for debugging (PII-safe)

---

## Appendix

### Files Reference
- **Implementation**: `src/cuga/modular/tools/sales/intelligence.py` (649 lines)
- **Unit Tests**: `tests/sales/test_intelligence.py` (470 lines, 14/14 passing)
- **UAT Tests**: `scripts/uat/run_phase4_uat.py` (4/4 passing)
- **Config Validation**: `scripts/deployment/validate_config.py`
- **Status Doc**: `docs/sales/IMPLEMENTATION_STATUS.md` (reality check)
- **Completion Doc**: `docs/sales/PHASE_4_COMPLETION.md` (technical details)

### Deployment Checklist
- [ ] Week 7: Environment setup complete
- [ ] Week 7: UAT tests pass (4/4)
- [ ] Week 7: Q4 data exported and loaded
- [ ] Week 7: Analysis runs successfully
- [ ] Week 7: Leadership review complete (3+ insights identified)
- [ ] Week 7: Production approval received
- [ ] Week 8: Production environment configured
- [ ] Week 8: Quarterly automation scheduled
- [ ] Week 8: User training complete
- [ ] Week 8: First production run successful
- [ ] Week 8: Monitoring/alerting configured (optional)

### Timeline Summary
- **Week 7 (Staging)**: Environment setup (30 min), UAT tests (10 min), Q4 data export (2 hrs), test analysis (1 hr), persona extraction (30 min), leadership review (2 hrs)
- **Week 8 (Production)**: Production setup (1 hr), schedule automation (30 min), user training (1 hr), production validation (1 hr)
- **Total Effort**: ~9 hours over 2 weeks

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-01-03  
**Next Review**: After first production deployment (Week 8)
