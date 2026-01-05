#!/usr/bin/env python3
"""
Phase 4 Intelligence UAT Tests

Tests the ACTUAL implemented capabilities (Phase 4 only).

Usage:
    python scripts/uat/run_phase4_uat.py
"""

import sys
import os
from typing import Tuple


# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def test_win_loss_analysis_basic() -> Tuple[bool, str]:
    """UAT Test 1: Basic Win/Loss Analysis."""
    try:
        from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns
        
        # Create test deals
        test_deals = [
            {
                "deal_id": "001",
                "outcome": "won",
                "account": {"name": "TechWin1", "industry": "Technology", "revenue": 25_000_000},
                "deal_value": 100_000,
                "sales_cycle_days": 45,
                "qualification_score": 0.85,
            },
            {
                "deal_id": "002",
                "outcome": "won",
                "account": {"name": "TechWin2", "industry": "Technology", "revenue": 30_000_000},
                "deal_value": 120_000,
                "sales_cycle_days": 40,
                "qualification_score": 0.90,
            },
            {
                "deal_id": "003",
                "outcome": "won",
                "account": {"name": "TechWin3", "industry": "Technology", "revenue": 20_000_000},
                "deal_value": 90_000,
                "sales_cycle_days": 50,
                "qualification_score": 0.80,
            },
            {
                "deal_id": "004",
                "outcome": "lost",
                "account": {"name": "MfgLoss1", "industry": "Manufacturing", "revenue": 50_000_000},
                "deal_value": 75_000,
                "sales_cycle_days": 60,
                "qualification_score": 0.50,
                "loss_reason": "price",
            },
            {
                "deal_id": "005",
                "outcome": "lost",
                "account": {"name": "MfgLoss2", "industry": "Manufacturing", "revenue": 45_000_000},
                "deal_value": 65_000,
                "sales_cycle_days": 65,
                "qualification_score": 0.45,
                "loss_reason": "timing",
            },
        ]
        
        # Analyze patterns
        analysis_result = analyze_win_loss_patterns(
            inputs={"deals": test_deals, "min_deals_for_pattern": 3},
            context={"trace_id": "uat-001", "profile": "sales"}
        )
        
        # Validate results
        if "summary" not in analysis_result:
            return False, "Missing 'summary' in result"
        if "win_rate" not in analysis_result["summary"]:
            return False, "Missing 'win_rate' in summary"
        
        win_rate = analysis_result["summary"]["win_rate"]
        won_count = analysis_result["summary"]["won_count"]
        lost_count = analysis_result["summary"]["lost_count"]
        
        if won_count != 3 or lost_count != 2:
            return False, f"Expected 3 won, 2 lost; got {won_count} won, {lost_count} lost"
        
        if not (0.55 <= win_rate <= 0.65):  # Should be 60% (3/5)
            return False, f"Expected ~60% win rate, got {win_rate:.0%}"
        
        return True, f"Win rate: {win_rate:.0%} ({won_count} won, {lost_count} lost)"
        
    except Exception as e:
        return False, f"Error: {e}"


def test_industry_pattern_detection() -> Tuple[bool, str]:
    """UAT Test 2: Industry Pattern Detection."""
    try:
        from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns
        
        # Create deals with clear industry pattern (Technology wins, Manufacturing loses)
        test_deals = [
            # Technology wins (4/4 = 100%)
            {"deal_id": "T1", "outcome": "won", "account": {"name": "Tech1", "industry": "Technology", "revenue": 20000000}, "deal_value": 100000, "sales_cycle_days": 45, "qualification_score": 0.85},
            {"deal_id": "T2", "outcome": "won", "account": {"name": "Tech2", "industry": "Technology", "revenue": 25000000}, "deal_value": 110000, "sales_cycle_days": 40, "qualification_score": 0.88},
            {"deal_id": "T3", "outcome": "won", "account": {"name": "Tech3", "industry": "Technology", "revenue": 30000000}, "deal_value": 120000, "sales_cycle_days": 42, "qualification_score": 0.90},
            {"deal_id": "T4", "outcome": "won", "account": {"name": "Tech4", "industry": "Technology", "revenue": 22000000}, "deal_value": 105000, "sales_cycle_days": 44, "qualification_score": 0.87},
            
            # Manufacturing losses (0/3 = 0%)
            {"deal_id": "M1", "outcome": "lost", "account": {"name": "Mfg1", "industry": "Manufacturing", "revenue": 50000000}, "deal_value": 80000, "sales_cycle_days": 60, "qualification_score": 0.55, "loss_reason": "price"},
            {"deal_id": "M2", "outcome": "lost", "account": {"name": "Mfg2", "industry": "Manufacturing", "revenue": 45000000}, "deal_value": 75000, "sales_cycle_days": 65, "qualification_score": 0.50, "loss_reason": "timing"},
            {"deal_id": "M3", "outcome": "lost", "account": {"name": "Mfg3", "industry": "Manufacturing", "revenue": 48000000}, "deal_value": 70000, "sales_cycle_days": 62, "qualification_score": 0.52, "loss_reason": "competitor"},
        ]
        
        analysis_result = analyze_win_loss_patterns(
            inputs={"deals": test_deals, "min_deals_for_pattern": 3},
            context={"trace_id": "uat-002", "profile": "sales"}
        )
        
        # Check for industry patterns
        if "win_patterns" not in analysis_result:
            return False, "Missing 'win_patterns' in result"
        
        # Find Technology pattern
        tech_pattern = next((p for p in analysis_result["win_patterns"] if p.get("pattern_value") == "Technology"), None)
        if not tech_pattern:
            return False, "Technology pattern not detected"
        
        if tech_pattern["win_rate"] != 1.0:  # Should be 100%
            return False, f"Technology win rate should be 100%, got {tech_pattern['win_rate']:.0%}"
        
        return True, f"Technology: {tech_pattern['win_rate']:.0%} win rate, confidence: {tech_pattern['confidence']:.2f}"
        
    except Exception as e:
        return False, f"Error: {e}"


def test_buyer_persona_extraction() -> Tuple[bool, str]:
    """UAT Test 3: Buyer Persona Extraction."""
    try:
        from cuga.modular.tools.sales.intelligence import extract_buyer_personas
        
        # Create won deals with clear persona patterns
        won_deals = [
            {
                "deal_id": "001",
                "outcome": "won",
                "contacts": [
                    {"name": "John Doe", "title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                    {"name": "Jane Smith", "title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
            {
                "deal_id": "002",
                "outcome": "won",
                "contacts": [
                    {"name": "Bob Johnson", "title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                    {"name": "Alice Williams", "title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
            {
                "deal_id": "003",
                "outcome": "won",
                "contacts": [
                    {"name": "Charlie Brown", "title": "VP Sales", "department": "Sales", "role": "champion", "seniority": "VP"},
                    {"name": "Diana Prince", "title": "CFO", "department": "Finance", "role": "decision_maker", "seniority": "C-level"},
                ]
            },
        ]
        
        persona_result = extract_buyer_personas(
            inputs={"deals": won_deals, "min_occurrences": 3},
            context={"trace_id": "uat-003", "profile": "sales"}
        )
        
        # Validate results
        if "personas" not in persona_result:
            return False, "Missing 'personas' in result"
        
        # Find VP Sales persona (should appear 3 times)
        vp_sales_persona = next((p for p in persona_result["personas"] if "VP Sales" in p.get("title_pattern", "")), None)
        if not vp_sales_persona:
            return False, "VP Sales persona not detected"
        
        if vp_sales_persona["occurrence_count"] != 3:
            return False, f"VP Sales should appear 3 times, got {vp_sales_persona['occurrence_count']}"
        
        # Find CFO persona (should appear 3 times)
        cfo_persona = next((p for p in persona_result["personas"] if "CFO" in p.get("title_pattern", "")), None)
        if not cfo_persona:
            return False, "CFO persona not detected"
        
        if cfo_persona["occurrence_count"] != 3:
            return False, f"CFO should appear 3 times, got {cfo_persona['occurrence_count']}"
        
        return True, f"Detected {len(persona_result['personas'])} personas (VP Sales: 3x, CFO: 3x)"
        
    except Exception as e:
        return False, f"Error: {e}"


def test_icp_recommendations() -> Tuple[bool, str]:
    """UAT Test 4: ICP Recommendations from Win Patterns."""
    try:
        from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns
        
        # Create deals with clear ICP signals
        test_deals = [
            # Technology + 10-50M wins (5/5)
            {"deal_id": "W1", "outcome": "won", "account": {"name": "TechA", "industry": "Technology", "revenue": 25000000}, "deal_value": 100000, "sales_cycle_days": 45, "qualification_score": 0.85},
            {"deal_id": "W2", "outcome": "won", "account": {"name": "TechB", "industry": "Technology", "revenue": 30000000}, "deal_value": 110000, "sales_cycle_days": 40, "qualification_score": 0.88},
            {"deal_id": "W3", "outcome": "won", "account": {"name": "TechC", "industry": "Technology", "revenue": 35000000}, "deal_value": 120000, "sales_cycle_days": 42, "qualification_score": 0.90},
            {"deal_id": "W4", "outcome": "won", "account": {"name": "TechD", "industry": "Technology", "revenue": 40000000}, "deal_value": 115000, "sales_cycle_days": 44, "qualification_score": 0.87},
            {"deal_id": "W5", "outcome": "won", "account": {"name": "TechE", "industry": "Technology", "revenue": 45000000}, "deal_value": 125000, "sales_cycle_days": 43, "qualification_score": 0.89},
            
            # Manufacturing + 100M+ losses (3/3)
            {"deal_id": "L1", "outcome": "lost", "account": {"name": "MfgX", "industry": "Manufacturing", "revenue": 120000000}, "deal_value": 80000, "sales_cycle_days": 60, "qualification_score": 0.55, "loss_reason": "price"},
            {"deal_id": "L2", "outcome": "lost", "account": {"name": "MfgY", "industry": "Manufacturing", "revenue": 150000000}, "deal_value": 75000, "sales_cycle_days": 65, "qualification_score": 0.50, "loss_reason": "timing"},
            {"deal_id": "L3", "outcome": "lost", "account": {"name": "MfgZ", "industry": "Manufacturing", "revenue": 180000000}, "deal_value": 70000, "sales_cycle_days": 62, "qualification_score": 0.52, "loss_reason": "competitor"},
        ]
        
        analysis_result = analyze_win_loss_patterns(
            inputs={"deals": test_deals, "min_deals_for_pattern": 3},
            context={"trace_id": "uat-004", "profile": "sales"}
        )
        
        # Check for ICP recommendations
        if "icp_recommendations" not in analysis_result:
            return False, "Missing 'icp_recommendations' in result"
        
        icp_recs = analysis_result["icp_recommendations"]
        if len(icp_recs) == 0:
            return False, "No ICP recommendations generated"
        
        # Should recommend Technology industry
        industry_rec = next((r for r in icp_recs if r.get("attribute") == "target_industries"), None)
        if not industry_rec:
            return False, "No industry recommendation found"
        
        if "Technology" not in industry_rec.get("recommended", ""):
            return False, f"Expected Technology recommendation, got: {industry_rec.get('recommended')}"
        
        return True, f"ICP recommendations: {len(icp_recs)} attributes (includes Technology targeting)"
        
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Run Phase 4 Intelligence UAT tests."""
    print("=" * 60)
    print("CUGAr Sales Agent - Phase 4 Intelligence UAT")
    print("=" * 60)
    print()
    print("Testing ACTUAL implemented capabilities (Phase 4 only)")
    print()
    
    tests = [
        ("Basic Win/Loss Analysis", test_win_loss_analysis_basic),
        ("Industry Pattern Detection", test_industry_pattern_detection),
        ("Buyer Persona Extraction", test_buyer_persona_extraction),
        ("ICP Recommendations", test_icp_recommendations),
    ]
    
    results = []
    
    for idx, (name, test_func) in enumerate(tests, 1):
        print(f"{idx}. Testing: {name}")
        print("-" * 40)
        
        success, message = test_func()
        results.append((name, success, message))
        
        if success:
            print(f"✅ PASSED: {message}")
        else:
            print(f"❌ FAILED: {message}")
        print()
    
    # Summary
    print("=" * 60)
    passed = sum(1 for _, success, _ in results if success)
    total = len(results)
    
    print(f"Phase 4 UAT Results: {passed}/{total} passed ({passed/total*100:.0f}%)")
    print()
    
    if passed == total:
        print("✅ All Phase 4 UAT tests passed - Ready for production deployment")
        print()
        print("Deployment scope:")
        print("  • Phase 4 Intelligence ONLY (win/loss analysis, buyer personas)")
        print("  • For sales leaders (quarterly ICP reviews)")
        print("  • Standalone capability (no dependency on Phases 1-3)")
        print()
        print("Next steps:")
        print("  1. Deploy to staging (Week 7)")
        print("  2. Sales leaders test with real Q4 2025 data")
        print("  3. Production deployment for leadership use")
        print("  4. Plan Phases 1-3 implementation (future sprints)")
        return 0
    else:
        print("❌ Some Phase 4 UAT tests failed - Fix issues before deployment")
        print()
        print("Failed tests:")
        for name, success, message in results:
            if not success:
                print(f"  • {name}: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
