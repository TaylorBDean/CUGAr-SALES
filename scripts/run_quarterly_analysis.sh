#!/bin/bash
# Quarterly ICP Analysis Automation
# Usage: ./scripts/run_quarterly_analysis.sh

set -e  # Exit on error

QUARTER=$(date +%Y-Q%q)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DATA_DIR="${DATA_DIR:-$PROJECT_ROOT/data/sales}"
REPORT_DIR="${REPORT_DIR:-$PROJECT_ROOT/reports/sales}"

echo "=========================================="
echo "CUGAr Sales Intelligence - Quarterly Analysis"
echo "Quarter: $QUARTER"
echo "=========================================="
echo ""

# Create directories if they don't exist
mkdir -p "$DATA_DIR"
mkdir -p "$REPORT_DIR"

# Step 1: Manual data export reminder
echo "Step 1: Data Export"
echo "-------------------"
echo "MANUAL ACTION REQUIRED:"
echo "  1. Log into your CRM (HubSpot/Salesforce/Pipedrive)"
echo "  2. Export closed deals for $QUARTER with fields:"
echo "     - Deal ID, Outcome (Won/Lost)"
echo "     - Account: Name, Industry, Revenue"
echo "     - Deal Value, Sales Cycle (days), Qualification Score"
echo "     - Loss Reason (for lost deals)"
echo "     - Contacts: Name, Title, Department, Role, Seniority (for won deals)"
echo "  3. Save as: $DATA_DIR/${QUARTER}_deals.json"
echo ""
echo "Press Enter when export is complete..."
read

# Validate data file exists
if [ ! -f "$DATA_DIR/${QUARTER}_deals.json" ]; then
    echo "❌ Error: Data file not found: $DATA_DIR/${QUARTER}_deals.json"
    exit 1
fi

echo "✅ Data file found"
echo ""

# Step 2: Run analysis
echo "Step 2: Running Analysis"
echo "------------------------"

cd "$PROJECT_ROOT"

python3 << EOF
import json
import sys
from datetime import datetime

# Add src to path
sys.path.insert(0, "$PROJECT_ROOT/src")

from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns, extract_buyer_personas

print("Loading deals from $DATA_DIR/${QUARTER}_deals.json...")

# Load data
try:
    with open("$DATA_DIR/${QUARTER}_deals.json") as f:
        deals = json.load(f)
    print(f"✅ Loaded {len(deals)} deals")
except Exception as e:
    print(f"❌ Error loading data: {e}")
    sys.exit(1)

print("")
print("Analyzing win/loss patterns...")

# Win/loss analysis
try:
    analysis = analyze_win_loss_patterns(
        inputs={"deals": deals, "min_deals_for_pattern": 5},
        context={"trace_id": "${QUARTER}-analysis", "profile": "sales"}
    )
    print(f"✅ Analysis complete")
    print(f"   Win Rate: {analysis['summary']['win_rate']:.0%} ({analysis['summary']['won_count']} won, {analysis['summary']['lost_count']} lost)")
    print(f"   Avg Deal Value: \${analysis['summary']['avg_deal_value']:,.0f}")
    print(f"   Avg Sales Cycle: {analysis['summary']['avg_sales_cycle']:.0f} days")
except Exception as e:
    print(f"❌ Analysis failed: {e}")
    sys.exit(1)

print("")
print("Extracting buyer personas...")

# Buyer personas
try:
    won_deals = [d for d in deals if d.get("outcome") == "won"]
    if len(won_deals) >= 3:
        personas = extract_buyer_personas(
            inputs={"deals": won_deals, "min_occurrences": 3},
            context={"trace_id": "${QUARTER}-personas", "profile": "sales"}
        )
        print(f"✅ Extracted {len(personas['personas'])} buyer personas")
    else:
        print(f"⚠️  Insufficient won deals ({len(won_deals)}) for persona extraction (need 3+)")
        personas = {"personas": [], "decision_maker_patterns": {}}
except Exception as e:
    print(f"❌ Persona extraction failed: {e}")
    personas = {"personas": [], "decision_maker_patterns": {}}

print("")
print("Saving results...")

# Save results
try:
    results = {
        "quarter": "$QUARTER",
        "timestamp": datetime.now().isoformat(),
        "deals_analyzed": len(deals),
        "analysis": analysis,
        "personas": personas
    }
    
    output_file = "$REPORT_DIR/${QUARTER}_analysis.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✅ Results saved: {output_file}")
except Exception as e:
    print(f"❌ Error saving results: {e}")
    sys.exit(1)

print("")
print("=" * 50)
print("Analysis Summary")
print("=" * 50)

# Summary report
print(f"Win Rate: {analysis['summary']['win_rate']:.0%}")
print(f"Total Deals: {analysis['summary']['total_deals']}")
print(f"Won: {analysis['summary']['won_count']}, Lost: {analysis['summary']['lost_count']}")
print(f"Avg Deal Value (Won): \${analysis['summary']['avg_deal_value']:,.0f}")
print(f"Avg Sales Cycle: {analysis['summary']['avg_sales_cycle']:.0f} days")

if analysis.get('win_patterns'):
    print("")
    print("Top Win Patterns:")
    for pattern in analysis['win_patterns'][:3]:
        print(f"  • {pattern['pattern_value']}: {pattern['win_rate']:.0%} win rate (confidence: {pattern['confidence']:.2f})")
        print(f"    → {pattern['recommendation']}")

if analysis.get('loss_patterns'):
    print("")
    print("Top Loss Reasons:")
    for pattern in analysis['loss_patterns'][:3]:
        print(f"  • {pattern['reason']}: {pattern['percentage']:.0%} of losses")
        print(f"    → {pattern['recommendation']}")

if analysis.get('icp_recommendations'):
    print("")
    print("ICP Recommendations:")
    for rec in analysis['icp_recommendations'][:3]:
        print(f"  • {rec['attribute']}: {rec['recommended']}")
        print(f"    Rationale: {rec['rationale']}")

if personas.get('personas'):
    print("")
    print("Top Buyer Personas:")
    for persona in personas['personas'][:3]:
        print(f"  • {persona['title_pattern']} ({persona['occurrence_count']}x)")
        print(f"    Roles: {', '.join(persona['typical_roles'])}")
        print(f"    → {persona['recommendation']}")

print("")
print("=" * 50)
print(f"✅ Quarterly Analysis Complete: $QUARTER")
print("=" * 50)

EOF

ANALYSIS_EXIT_CODE=$?

if [ $ANALYSIS_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "Next Steps:"
    echo "  1. Review results: $REPORT_DIR/${QUARTER}_analysis.json"
    echo "  2. Share insights with sales leadership"
    echo "  3. Update ICP targeting for next quarter"
    echo "  4. Adjust qualification criteria if recommended"
    exit 0
else
    echo ""
    echo "❌ Analysis failed with exit code: $ANALYSIS_EXIT_CODE"
    echo "Check logs above for details"
    exit 1
fi
