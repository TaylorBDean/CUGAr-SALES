# Sales Agent End-to-End Workflow Guide

**Complete Sales Automation Workflows Using Phases 1-4**

**Date**: 2026-01-03  
**Status**: Production-Ready (78/85 tests passing - 92%)

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Workflow Patterns](#workflow-patterns)
3. [Complete Examples](#complete-examples)
4. [Integration Patterns](#integration-patterns)
5. [Error Handling](#error-handling)
6. [Best Practices](#best-practices)

---

## Quick Start

### Prerequisites

```bash
# Install dependencies
pip install -e .

# Set up environment (optional - for CRM integration)
export HUBSPOT_API_KEY="your_key_here"
# OR
export SALESFORCE_USERNAME="your_username"
export SALESFORCE_PASSWORD="your_password"
export SALESFORCE_SECURITY_TOKEN="your_token"
# OR
export PIPEDRIVE_API_TOKEN="your_token"
```

### Basic Workflow (Offline-Only)

```python
from cuga.modular.tools.sales.territory import define_target_market
from cuga.modular.tools.sales.account_intelligence import get_account_signals
from cuga.modular.tools.sales.qualification import qualify_opportunity
from cuga.modular.tools.sales.outreach import draft_outreach_message
from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns

# 1. Define your territory
territory_result = define_target_market(
    inputs={
        "market_definition": {
            "industries": ["Technology", "Healthcare"],
            "revenue_range": "10M-100M",
            "geography": "North America",
        }
    },
    context={"trace_id": "workflow-001", "profile": "sales"}
)

# 2. Get account signals
signals_result = get_account_signals(
    inputs={"account_id": "acme-tech-123"},
    context={"trace_id": "workflow-001", "profile": "sales"}
)

# 3. Qualify the opportunity
qualification_result = qualify_opportunity(
    inputs={
        "framework": "BANT",
        "criteria": {
            "budget": 50000,
            "authority": "identified",
            "need": "confirmed",
            "timing": "Q1 2026",
        },
        "threshold": 0.7,
    },
    context={"trace_id": "workflow-001", "profile": "sales"}
)

# 4. Draft personalized message
if qualification_result["qualified"]:
    message_result = draft_outreach_message(
        inputs={
            "recipient_context": {
                "name": "Sarah Johnson",
                "title": "VP Sales",
                "company": "Acme Tech",
            },
            "sender_context": {
                "name": "Alex Martinez",
                "title": "Account Executive",
                "company": "CUGAr Solutions",
            },
            "channel": "email",
            "template": "tech_prospecting",
        },
        context={"trace_id": "workflow-001", "profile": "sales"}
    )

# 5. Learn from historical deals (monthly)
analysis_result = analyze_win_loss_patterns(
    inputs={"deals": historical_deals, "min_deals_for_pattern": 5},
    context={"trace_id": "workflow-001", "profile": "sales"}
)
```

---

## Workflow Patterns

### Pattern 1: Territory-Driven Prospecting

**Use Case**: SDR identifies which accounts to prioritize in their territory.

```python
# Step 1: Define territory with ICP
territory_result = define_target_market(
    inputs={
        "market_definition": {
            "industries": ["SaaS", "Cloud Infrastructure"],
            "revenue_range": "10M-50M",
            "geography": "US West Coast",
            "employee_count_range": "50-500",
        }
    },
    context={"trace_id": "territory-001", "profile": "sales"}
)

# Step 2: Score each account in your list
accounts_to_score = [
    {"name": "Acme SaaS", "industry": "SaaS", "revenue": 25_000_000, "employees": 150},
    {"name": "OldCorp", "industry": "Manufacturing", "revenue": 100_000_000, "employees": 2000},
    {"name": "CloudCo", "industry": "Cloud Infrastructure", "revenue": 15_000_000, "employees": 80},
]

scored_accounts = []
for account in accounts_to_score:
    score = score_accounts(
        inputs={
            "accounts": [account],
            "market_definition": territory_result["market_definition"],
        },
        context={"trace_id": "territory-001", "profile": "sales"}
    )
    scored_accounts.append({
        "account": account,
        "score": score["scored_accounts"][0]["icp_score"],
        "recommendation": score["scored_accounts"][0]["recommendation"]
    })

# Step 3: Sort by ICP score and prioritize
scored_accounts.sort(key=lambda x: x["score"], reverse=True)

print("Account Priority List:")
for idx, item in enumerate(scored_accounts, 1):
    account = item["account"]
    print(f"{idx}. {account['name']}: {item['score']:.2f} - {item['recommendation']}")

# Output:
# 1. Acme SaaS: 0.95 - Perfect ICP match
# 2. CloudCo: 0.88 - Strong ICP match  
# 3. OldCorp: 0.22 - Poor ICP match
```

**Next Steps**: Focus on #1 and #2 for prospecting.

---

### Pattern 2: CRM-Enriched Account Research

**Use Case**: AE researches account before discovery call using CRM data + signals.

```python
from cuga.adapters.crm.factory import get_configured_adapter

# Step 1: Fetch account from CRM
adapter = get_configured_adapter()
crm_account = adapter.get_account(
    account_id="001ABC123",
    context={"trace_id": "research-001"}
)

# Step 2: Get real-time signals (hiring, tech stack, funding)
signals_result = get_account_signals(
    inputs={
        "account_id": crm_account["id"],
        "adapter": adapter,  # Optional: Pass adapter for CRM enrichment
    },
    context={"trace_id": "research-001", "profile": "sales"}
)

# Step 3: Analyze buying signals
buying_signals = []
for signal in signals_result["signals"]:
    if signal["type"] in ["expansion_hiring", "recent_funding", "tech_adoption"]:
        buying_signals.append(signal)

# Step 4: Fetch related opportunities
opportunities = adapter.search_opportunities(
    filters={"account_id": crm_account["id"]},
    context={"trace_id": "research-001"}
)

# Step 5: Prepare research summary for discovery call
research_summary = {
    "account_name": crm_account["name"],
    "industry": crm_account["industry"],
    "revenue": crm_account["revenue"],
    "employee_count": crm_account.get("employee_count", "Unknown"),
    "key_signals": [s["description"] for s in buying_signals],
    "active_opportunities": len([o for o in opportunities if o["stage"] != "Closed Lost"]),
    "total_pipeline_value": sum(o["amount"] for o in opportunities if o["stage"] != "Closed Lost"),
}

print("=== Discovery Call Research ===")
print(f"Account: {research_summary['account_name']}")
print(f"Industry: {research_summary['industry']}")
print(f"Size: ${research_summary['revenue']:,} revenue, {research_summary['employee_count']} employees")
print(f"\nBuying Signals:")
for signal in research_summary["key_signals"]:
    print(f"  • {signal}")
print(f"\nActive Pipeline: {research_summary['active_opportunities']} opps, ${research_summary['total_pipeline_value']:,}")
```

**Output**:
```
=== Discovery Call Research ===
Account: Acme SaaS
Industry: Software
Size: $25,000,000 revenue, 150 employees

Buying Signals:
  • Expansion hiring: Posted 5 sales engineering roles in last 30 days
  • Recent funding: Series B $15M announced
  • Tech adoption: Migrating to Kubernetes (based on job postings)

Active Pipeline: 1 opp, $100,000
```

**Next Steps**: Tailor discovery questions around expansion hiring and funding.

---

### Pattern 3: Multi-Stage Qualification Workflow

**Use Case**: Progress opportunity through qualification stages (BANT → MEDDIC → Final Review).

```python
# Stage 1: Initial BANT Qualification (Discovery Call)
bant_result = qualify_opportunity(
    inputs={
        "framework": "BANT",
        "criteria": {
            "budget": 50000,  # Confirmed budget
            "authority": "identified",  # Met VP Sales
            "need": "confirmed",  # Pain points identified
            "timing": "Q1 2026",  # Buying timeline
        },
        "threshold": 0.6,  # Lower threshold for initial stage
    },
    context={"trace_id": "qual-001", "profile": "sales"}
)

print(f"BANT Score: {bant_result['score']:.0%}")
print(f"Qualified: {bant_result['qualified']}")
print(f"Recommendation: {bant_result['recommendation']}")

# If BANT passes, proceed to MEDDIC (deeper qualification)
if bant_result["qualified"]:
    # Stage 2: MEDDIC Qualification (Technical Validation)
    meddic_result = qualify_opportunity(
        inputs={
            "framework": "MEDDIC",
            "criteria": {
                "metrics": "Reduce sales cycle by 30%",
                "economic_buyer": "CFO identified and engaged",
                "decision_criteria": "ROI > 300%, implementation < 90 days",
                "decision_process": "Committee review → CFO approval → Legal",
                "identify_pain": "Manual prospecting costing $500K/year",
                "champion": "VP Sales is internal champion",
            },
            "threshold": 0.75,  # Higher threshold for later stage
        },
        context={"trace_id": "qual-001", "profile": "sales"}
    )
    
    print(f"\nMEDDIC Score: {meddic_result['score']:.0%}")
    print(f"Qualified: {meddic_result['qualified']}")
    print(f"Recommendation: {meddic_result['recommendation']}")
    
    # Stage 3: Final Review Checklist
    if meddic_result["qualified"]:
        final_checks = {
            "budget_confirmed": True,
            "legal_approved": True,
            "champion_active": True,
            "competitor_defeated": True,
            "timeline_confirmed": True,
        }
        
        final_score = sum(final_checks.values()) / len(final_checks)
        
        if final_score >= 0.8:
            print(f"\n✅ APPROVED FOR CLOSING (Final Score: {final_score:.0%})")
            print("Action: Send contract for signature")
        else:
            print(f"\n⚠️  NEEDS ATTENTION (Final Score: {final_score:.0%})")
            print("Action: Address remaining concerns before closing")
```

**Output**:
```
BANT Score: 75%
Qualified: True
Recommendation: Proceed to discovery call

MEDDIC Score: 83%
Qualified: True
Recommendation: Strong opportunity - prioritize

✅ APPROVED FOR CLOSING (Final Score: 100%)
Action: Send contract for signature
```

---

### Pattern 4: Quality-Gated Outreach Campaign

**Use Case**: SDR sends personalized email sequence with automated quality checks.

```python
from cuga.modular.tools.sales.outreach import (
    draft_outreach_message,
    assess_message_quality,
    manage_template_library,
)

# Step 1: Create email sequence templates
templates = [
    {
        "name": "initial_outreach",
        "subject": "{{benefit}} for {{company}}",
        "body": """Hi {{name}},

I noticed {{company}} is {{hiring_signal}}. Many {{industry}} companies we work with face challenges around {{pain_point}}.

Would you be open to a 15-minute call next week to discuss how we've helped similar companies achieve {{benefit}}?

Best,
{{sender_name}}""",
        "channel": "email",
        "tags": ["prospecting", "cold_outreach"],
    },
    {
        "name": "follow_up_1",
        "subject": "Re: {{benefit}} for {{company}}",
        "body": """{{name}},

Following up on my previous email. I'd love to share how {{customer_name}} (similar {{industry}} company) achieved {{customer_result}} in just {{timeframe}}.

Would Tuesday or Wednesday work for a quick call?

Best,
{{sender_name}}""",
        "channel": "email",
        "tags": ["follow_up"],
    },
]

# Create templates in library
for template in templates:
    manage_template_library(
        inputs={"operation": "create", "template": template},
        context={"trace_id": "campaign-001", "profile": "sales"}
    )

# Step 2: Draft personalized messages for each prospect
prospects = [
    {
        "name": "Sarah Johnson",
        "title": "VP Sales",
        "company": "Acme SaaS",
        "industry": "SaaS",
        "hiring_signal": "expanding their sales team (5 new openings)",
        "pain_point": "manual prospecting and qualification",
        "benefit": "30% faster sales cycles",
    },
    # ... more prospects
]

drafted_messages = []
for prospect in prospects:
    # Draft initial message
    draft_result = draft_outreach_message(
        inputs={
            "recipient_context": {
                "name": prospect["name"],
                "title": prospect["title"],
                "company": prospect["company"],
            },
            "sender_context": {
                "name": "Alex Martinez",
                "title": "Account Executive",
                "company": "CUGAr Solutions",
            },
            "template": "initial_outreach",
            "channel": "email",
            "personalization": {
                "benefit": prospect["benefit"],
                "company": prospect["company"],
                "hiring_signal": prospect["hiring_signal"],
                "industry": prospect["industry"],
                "pain_point": prospect["pain_point"],
            },
        },
        context={"trace_id": "campaign-001", "profile": "sales"}
    )
    
    # Step 3: Quality assessment (automated gating)
    quality_result = assess_message_quality(
        inputs={"message": draft_result["message"]},
        context={"trace_id": "campaign-001", "profile": "sales"}
    )
    
    # Step 4: Only queue messages with grade B+ or better
    if quality_result["grade"] in ["A", "B+"]:
        drafted_messages.append({
            "prospect": prospect,
            "message": draft_result["message"],
            "quality_score": quality_result["quality_score"],
            "grade": quality_result["grade"],
            "status": "ready_to_send",
        })
        print(f"✅ {prospect['name']}: {quality_result['grade']} - Ready")
    else:
        # Flag for manual review
        drafted_messages.append({
            "prospect": prospect,
            "message": draft_result["message"],
            "quality_score": quality_result["quality_score"],
            "grade": quality_result["grade"],
            "issues": quality_result["issues"],
            "status": "needs_review",
        })
        print(f"⚠️  {prospect['name']}: {quality_result['grade']} - Needs Review")
        for issue in quality_result["issues"]:
            print(f"    • {issue['description']}")

# Step 5: Send approved messages (manually or via CRM integration)
ready_to_send = [m for m in drafted_messages if m["status"] == "ready_to_send"]
print(f"\n{len(ready_to_send)} messages ready to send")
print(f"{len(drafted_messages) - len(ready_to_send)} messages need review")
```

**Output**:
```
✅ Sarah Johnson: A - Ready
✅ Michael Chen: B+ - Ready
⚠️  David Park: C - Needs Review
    • Message is too long (450 words, should be <300)
    • No clear call to action
    • Low personalization score (0.3)

2 messages ready to send
1 message needs review
```

---

### Pattern 5: Continuous ICP Refinement Loop

**Use Case**: Sales leader reviews quarterly performance and refines ICP based on win/loss analysis.

```python
from cuga.modular.tools.sales.intelligence import (
    analyze_win_loss_patterns,
    extract_buyer_personas,
)

# Step 1: Fetch closed deals from CRM (Q4 2025)
adapter = get_configured_adapter()

won_deals = adapter.search_opportunities(
    filters={"stage": "Closed Won", "close_date_after": "2025-10-01"},
    context={"trace_id": "q4-review", "profile": "sales"}
)

lost_deals = adapter.search_opportunities(
    filters={"stage": "Closed Lost", "close_date_after": "2025-10-01"},
    context={"trace_id": "q4-review", "profile": "sales"}
)

# Enrich with account data
all_deals = []
for opp in won_deals + lost_deals:
    account = adapter.get_account(opp["account_id"], context={"trace_id": "q4-review"})
    all_deals.append({
        "deal_id": opp["id"],
        "outcome": "won" if opp in won_deals else "lost",
        "account": account,
        "deal_value": opp["amount"],
        "sales_cycle_days": opp.get("sales_cycle_days", 45),
        "qualification_score": opp.get("qualification_score", 0.7),
        "loss_reason": opp.get("loss_reason") if opp in lost_deals else None,
    })

# Step 2: Analyze win/loss patterns
analysis_result = analyze_win_loss_patterns(
    inputs={"deals": all_deals, "min_deals_for_pattern": 5, "time_period_days": 90},
    context={"trace_id": "q4-review", "profile": "sales"}
)

# Step 3: Review ICP recommendations
print("=== Q4 2025 Win/Loss Analysis ===\n")
print(f"Total Deals: {analysis_result['summary']['total_deals']}")
print(f"Win Rate: {analysis_result['summary']['win_rate']:.0%}")
print(f"Avg Deal Value (Won): ${analysis_result['summary']['avg_deal_value_won']:,.0f}")
print(f"Avg Sales Cycle (Won): {analysis_result['summary']['avg_sales_cycle_won']:.0f} days\n")

print("Top Win Patterns:")
for pattern in analysis_result["win_patterns"][:3]:
    print(f"  • {pattern['pattern_value']}: {pattern['win_rate']:.0%} win rate ({pattern['deal_count']} deals)")
    print(f"    Confidence: {pattern['confidence']:.2f}")
    print(f"    → {pattern['recommendation']}\n")

print("Top Loss Reasons:")
for loss in analysis_result["loss_patterns"][:3]:
    print(f"  • {loss['loss_reason']}: {loss['percentage']:.0%} of losses ({loss['count']} deals)")
    print(f"    → {loss['recommendation']}\n")

# Step 4: Extract buyer personas
persona_result = extract_buyer_personas(
    inputs={"deals": [d for d in all_deals if d["outcome"] == "won"]},
    context={"trace_id": "q4-review", "profile": "sales"}
)

print("Common Buyer Personas:")
for persona in persona_result["personas"][:3]:
    print(f"  • {persona['title_pattern']}: {persona['occurrence_count']} occurrences")
    print(f"    Typical roles: {', '.join(persona['typical_roles'])}")
    print(f"    → {persona['recommendation']}\n")

# Step 5: Update territory definition based on insights
updated_territory = define_target_market(
    inputs={
        "market_definition": {
            # OLD ICP
            # "industries": ["Technology", "Healthcare", "Finance"],
            # "revenue_range": "10M-100M",
            
            # NEW ICP (based on Q4 analysis)
            "industries": analysis_result["icp_recommendations"][0]["recommended"].split(", "),
            "revenue_range": analysis_result["icp_recommendations"][1]["recommended"],
            "geography": "North America",
            
            # NEW: Add buyer persona targeting
            "target_personas": [p["title_pattern"] for p in persona_result["personas"][:3]],
        }
    },
    context={"trace_id": "q4-review", "profile": "sales"}
)

print("=== Updated ICP for Q1 2026 ===")
print(f"Target Industries: {', '.join(updated_territory['market_definition']['industries'])}")
print(f"Revenue Range: {updated_territory['market_definition']['revenue_range']}")
print(f"Target Personas: {', '.join(updated_territory['market_definition']['target_personas'])}")
```

**Output**:
```
=== Q4 2025 Win/Loss Analysis ===

Total Deals: 50
Win Rate: 64%
Avg Deal Value (Won): $125,000
Avg Sales Cycle (Won): 42 days

Top Win Patterns:
  • Technology: 82% win rate (28 deals)
    Confidence: 0.95
    → Strong fit: Target more Technology accounts

  • 10-50M: 78% win rate (22 deals)
    Confidence: 0.88
    → Sweet spot: Focus on $10-50M revenue range

  • Healthcare: 58% win rate (12 deals)
    Confidence: 0.44
    → Moderate fit: Continue targeting but not primary focus

Top Loss Reasons:
  • price: 39% of losses (7 deals)
    → Consider value-based pricing or early price anchoring

  • timing: 28% of losses (5 deals)
    → Improve timing qualification in discovery calls

  • competitor: 17% of losses (3 deals)
    → Strengthen competitive positioning and differentiation

Common Buyer Personas:
  • VP Sales: 8 occurrences
    Typical roles: champion, influencer
    → Target VP Sales as champions, multi-thread to decision makers

  • CFO: 12 occurrences
    Typical roles: decision_maker
    → Target CFOs as primary decision makers

  • CTO: 5 occurrences
    Typical roles: influencer, decision_maker
    → Target CTOs as influencers in buying process

=== Updated ICP for Q1 2026 ===
Target Industries: Technology, Healthcare
Revenue Range: 10-50M
Target Personas: VP Sales, CFO, CTO
```

**Next Steps**: 
1. Update CRM account scoring rules based on new ICP
2. Train sales team on refined targeting criteria
3. Adjust marketing campaigns to focus on Technology + Healthcare
4. Create persona-specific messaging for VP Sales, CFO, CTO

---

## Integration Patterns

### Pattern A: Territory → Account Intelligence → Qualification

```python
# 1. Define territory
territory_result = define_target_market(
    inputs={"market_definition": {"industries": ["SaaS"], "revenue_range": "10M-50M"}},
    context={"trace_id": "flow-001", "profile": "sales"}
)

# 2. Score account against ICP
score_result = score_accounts(
    inputs={
        "accounts": [{"name": "Acme SaaS", "industry": "SaaS", "revenue": 25_000_000}],
        "market_definition": territory_result["market_definition"],
    },
    context={"trace_id": "flow-001", "profile": "sales"}
)

# 3. If high ICP score, get signals
if score_result["scored_accounts"][0]["icp_score"] >= 0.7:
    signals_result = get_account_signals(
        inputs={"account_id": "acme-saas-123"},
        context={"trace_id": "flow-001", "profile": "sales"}
    )

# 4. If strong signals, qualify opportunity
buying_signals = [s for s in signals_result["signals"] if s["type"] in ["expansion_hiring", "recent_funding"]]
if len(buying_signals) >= 2:
    qualification_result = qualify_opportunity(
        inputs={
            "framework": "BANT",
            "criteria": {"budget": 50000, "authority": "identified", "need": "confirmed", "timing": "Q1 2026"},
            "threshold": 0.7,
        },
        context={"trace_id": "flow-001", "profile": "sales"}
    )
```

### Pattern B: Qualification → Outreach → CRM Update

```python
# 1. Qualify opportunity
qualification_result = qualify_opportunity(
    inputs={
        "framework": "MEDDIC",
        "criteria": {...},
        "threshold": 0.75,
    },
    context={"trace_id": "flow-002", "profile": "sales"}
)

# 2. If qualified, draft personalized message
if qualification_result["qualified"]:
    draft_result = draft_outreach_message(
        inputs={
            "recipient_context": {"name": "Sarah Johnson", "title": "VP Sales", "company": "Acme"},
            "sender_context": {"name": "Alex Martinez", "title": "AE", "company": "CUGAr"},
            "template": "qualified_prospect",
            "channel": "email",
        },
        context={"trace_id": "flow-002", "profile": "sales"}
    )
    
    # 3. Assess quality
    quality_result = assess_message_quality(
        inputs={"message": draft_result["message"]},
        context={"trace_id": "flow-002", "profile": "sales"}
    )
    
    # 4. If quality passes, update CRM with next step
    if quality_result["grade"] in ["A", "B+"]:
        adapter = get_configured_adapter()
        adapter.update_opportunity(
            opportunity_id="opp-123",
            updates={
                "stage": "Qualified",
                "next_step": "Outreach email sent",
                "qualification_score": qualification_result["score"],
            },
            context={"trace_id": "flow-002"}
        )
```

### Pattern C: Win/Loss Analysis → Territory Refinement → Account Scoring

```python
# 1. Analyze Q4 performance
analysis_result = analyze_win_loss_patterns(
    inputs={"deals": q4_deals, "min_deals_for_pattern": 5},
    context={"trace_id": "flow-003", "profile": "sales"}
)

# 2. Extract ICP recommendations
icp_recs = analysis_result["icp_recommendations"]
recommended_industries = icp_recs[0]["recommended"].split(", ")
recommended_revenue = icp_recs[1]["recommended"]

# 3. Update territory with refined ICP
updated_territory = define_target_market(
    inputs={
        "market_definition": {
            "industries": recommended_industries,
            "revenue_range": recommended_revenue,
            "geography": "North America",
        }
    },
    context={"trace_id": "flow-003", "profile": "sales"}
)

# 4. Re-score all accounts against refined ICP
accounts_to_rescore = get_all_accounts_from_crm()
rescore_result = score_accounts(
    inputs={
        "accounts": accounts_to_rescore,
        "market_definition": updated_territory["market_definition"],
    },
    context={"trace_id": "flow-003", "profile": "sales"}
)

# 5. Identify newly prioritized accounts
newly_prioritized = [
    acc for acc in rescore_result["scored_accounts"]
    if acc["icp_score"] >= 0.8 and acc["recommendation"] == "Perfect ICP match"
]
```

---

## Error Handling

### Graceful CRM Fallback

```python
from cuga.adapters.crm.factory import get_configured_adapter

try:
    adapter = get_configured_adapter()
    
    # Try CRM-enriched signal retrieval
    signals_result = get_account_signals(
        inputs={"account_id": "acme-123", "adapter": adapter},
        context={"trace_id": "flow-004", "profile": "sales"}
    )
except Exception as e:
    print(f"CRM unavailable: {e}")
    
    # Fallback to offline signal retrieval
    signals_result = get_account_signals(
        inputs={"account_id": "acme-123"},  # No adapter = offline mode
        context={"trace_id": "flow-004", "profile": "sales"}
    )
    print("Using offline signals only")
```

### Qualification Threshold Tuning

```python
# Try higher threshold first
qualification_result = qualify_opportunity(
    inputs={
        "framework": "BANT",
        "criteria": {...},
        "threshold": 0.8,  # High bar
    },
    context={"trace_id": "flow-005", "profile": "sales"}
)

# If not qualified, try lower threshold with warning
if not qualification_result["qualified"]:
    lower_result = qualify_opportunity(
        inputs={
            "framework": "BANT",
            "criteria": {...},
            "threshold": 0.6,  # Lower bar
        },
        context={"trace_id": "flow-005", "profile": "sales"}
    )
    
    if lower_result["qualified"]:
        print("⚠️  Opportunity qualifies at lower threshold (60%)")
        print("⚠️  Requires additional validation before proceeding")
```

### Message Quality Recovery

```python
# Draft initial message
draft_result = draft_outreach_message(
    inputs={...},
    context={"trace_id": "flow-006", "profile": "sales"}
)

# Assess quality
quality_result = assess_message_quality(
    inputs={"message": draft_result["message"]},
    context={"trace_id": "flow-006", "profile": "sales"}
)

# If quality fails, try different template
if quality_result["grade"] in ["C", "D", "F"]:
    print(f"Initial draft quality: {quality_result['grade']}")
    print("Issues:")
    for issue in quality_result["issues"]:
        print(f"  • {issue['description']}")
    
    # Retry with different template
    redraft_result = draft_outreach_message(
        inputs={
            ...  # Same inputs
            "template": "alternative_template",  # Different template
        },
        context={"trace_id": "flow-006", "profile": "sales"}
    )
    
    # Re-assess
    quality_result_v2 = assess_message_quality(
        inputs={"message": redraft_result["message"]},
        context={"trace_id": "flow-006", "profile": "sales"}
    )
    
    if quality_result_v2["grade"] in ["A", "B+", "B"]:
        print(f"✅ Improved quality: {quality_result_v2['grade']}")
    else:
        print("⚠️  Manual review required")
```

---

## Best Practices

### 1. Always Use trace_id for Request Tracing

```python
# ✅ GOOD: Consistent trace_id across entire workflow
trace_id = f"workflow-{datetime.now().isoformat()}"

territory_result = define_target_market(
    inputs={...},
    context={"trace_id": trace_id, "profile": "sales"}
)

signals_result = get_account_signals(
    inputs={...},
    context={"trace_id": trace_id, "profile": "sales"}  # Same trace_id
)

qualification_result = qualify_opportunity(
    inputs={...},
    context={"trace_id": trace_id, "profile": "sales"}  # Same trace_id
)

# ❌ BAD: Different trace_id per operation (can't correlate logs)
territory_result = define_target_market(
    inputs={...},
    context={"trace_id": "territory-001", "profile": "sales"}
)

signals_result = get_account_signals(
    inputs={...},
    context={"trace_id": "signals-001", "profile": "sales"}  # Different!
)
```

### 2. Implement Progressive Qualification

```python
# ✅ GOOD: Start with loose threshold, tighten as deal progresses
stage_thresholds = {
    "discovery": 0.5,      # Low bar to start conversation
    "qualification": 0.7,  # Medium bar to invest time
    "proposal": 0.85,      # High bar to send proposal
    "negotiation": 0.9,    # Very high bar to close
}

current_stage = "qualification"
qualification_result = qualify_opportunity(
    inputs={
        "framework": "BANT",
        "criteria": {...},
        "threshold": stage_thresholds[current_stage],
    },
    context={"trace_id": trace_id, "profile": "sales"}
)

# ❌ BAD: Same threshold for all stages
qualification_result = qualify_opportunity(
    inputs={
        "framework": "BANT",
        "criteria": {...},
        "threshold": 0.7,  # Fixed threshold, regardless of stage
    },
    context={"trace_id": trace_id, "profile": "sales"}
)
```

### 3. Batch Operations for Performance

```python
# ✅ GOOD: Score all accounts in one call
all_accounts = [
    {"name": "Acme", "industry": "SaaS", "revenue": 25_000_000},
    {"name": "TechCo", "industry": "Cloud", "revenue": 15_000_000},
    {"name": "DataInc", "industry": "Analytics", "revenue": 35_000_000},
]

score_result = score_accounts(
    inputs={
        "accounts": all_accounts,  # Batch scoring
        "market_definition": territory_result["market_definition"],
    },
    context={"trace_id": trace_id, "profile": "sales"}
)

# ❌ BAD: Score accounts one-by-one (slow!)
for account in all_accounts:
    score_result = score_accounts(
        inputs={
            "accounts": [account],  # One at a time
            "market_definition": territory_result["market_definition"],
        },
        context={"trace_id": trace_id, "profile": "sales"}
    )
```

### 4. Handle CRM Failures Gracefully

```python
# ✅ GOOD: Try CRM, fallback to offline
try:
    adapter = get_configured_adapter()
    signals_result = get_account_signals(
        inputs={"account_id": "acme-123", "adapter": adapter},
        context={"trace_id": trace_id, "profile": "sales"}
    )
    enrichment_source = "CRM"
except Exception as e:
    logger.warning(f"CRM unavailable: {e}, falling back to offline mode")
    signals_result = get_account_signals(
        inputs={"account_id": "acme-123"},  # No adapter
        context={"trace_id": trace_id, "profile": "sales"}
    )
    enrichment_source = "Offline"

print(f"Signals retrieved from: {enrichment_source}")

# ❌ BAD: No fallback, fails if CRM is down
adapter = get_configured_adapter()  # Crashes if CRM unavailable
signals_result = get_account_signals(
    inputs={"account_id": "acme-123", "adapter": adapter},
    context={"trace_id": trace_id, "profile": "sales"}
)
```

### 5. Quality-Gate Outreach Messages

```python
# ✅ GOOD: Always assess quality before sending
draft_result = draft_outreach_message(
    inputs={...},
    context={"trace_id": trace_id, "profile": "sales"}
)

quality_result = assess_message_quality(
    inputs={"message": draft_result["message"]},
    context={"trace_id": trace_id, "profile": "sales"}
)

# Only send if quality passes
if quality_result["grade"] in ["A", "B+"]:
    # Send via CRM or email
    send_message(draft_result["message"])
else:
    # Flag for manual review
    queue_for_review(draft_result["message"], quality_result["issues"])

# ❌ BAD: Send without quality check (risky!)
draft_result = draft_outreach_message(
    inputs={...},
    context={"trace_id": trace_id, "profile": "sales"}
)

send_message(draft_result["message"])  # No quality check!
```

### 6. Regular Win/Loss Analysis

```python
# ✅ GOOD: Scheduled monthly analysis to refine ICP
def monthly_icp_review():
    """Run at end of each month"""
    
    # Fetch last 90 days of closed deals
    deals = fetch_closed_deals(days=90)
    
    # Analyze patterns
    analysis_result = analyze_win_loss_patterns(
        inputs={"deals": deals, "min_deals_for_pattern": 5},
        context={"trace_id": f"monthly-review-{datetime.now().strftime('%Y-%m')}", "profile": "sales"}
    )
    
    # Extract personas
    persona_result = extract_buyer_personas(
        inputs={"deals": [d for d in deals if d["outcome"] == "won"]},
        context={"trace_id": f"monthly-review-{datetime.now().strftime('%Y-%m')}", "profile": "sales"}
    )
    
    # Update ICP if confidence is high
    for rec in analysis_result["icp_recommendations"]:
        if rec["confidence"] >= 0.8:
            # Update territory definition
            update_territory_icp(rec)

# ❌ BAD: Never analyze historical performance (static ICP)
# ICP defined once at company founding, never refined
```

---

## Performance Tips

1. **Batch Account Scoring**: Score multiple accounts in one call instead of looping
2. **Cache CRM Data**: Store account/opportunity data locally to reduce API calls
3. **Offline-First**: Use offline signals when CRM enrichment isn't critical
4. **Template Reuse**: Create template library instead of drafting from scratch each time
5. **Incremental Analysis**: Analyze recent deals (last 90 days) instead of full history

---

## Security Reminders

1. **Never Auto-Send**: All messages stay in "draft" status (NO_AUTO_SEND hardcoded)
2. **CRM Credentials**: Store in environment variables (`.env`), never hardcode
3. **PII Redaction**: Tool outputs automatically redact sensitive keys (`secret`, `token`, etc.)
4. **Budget Enforcement**: Respect `AGENT_BUDGET_CEILING` for API-heavy operations
5. **Profile Isolation**: Use `profile: "sales"` in context to isolate memory/observability

---

## Next Steps

### For SDRs
1. Start with **Pattern 1: Territory-Driven Prospecting**
2. Use account scoring to prioritize outreach
3. Implement **Pattern 4: Quality-Gated Outreach** for email sequences

### For AEs
1. Use **Pattern 2: CRM-Enriched Account Research** before discovery calls
2. Implement **Pattern 3: Multi-Stage Qualification** to improve forecast accuracy
3. Regularly review qualification scores to prioritize deals

### For Sales Leaders
1. Run **Pattern 5: Continuous ICP Refinement** quarterly
2. Monitor win rates by industry/revenue to validate strategy
3. Use buyer persona analysis to optimize team hiring profiles
4. Track qualification accuracy to improve forecasting

---

**End of E2E Workflow Guide**
