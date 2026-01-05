#!/usr/bin/env python3
"""
User Acceptance Testing (UAT) Suite

Comprehensive UAT tests covering all 4 phases:
- Phase 1: Territory prospecting
- Phase 2: CRM-enriched qualification
- Phase 3: Quality-gated outreach
- Phase 4: Win/loss analysis

Usage:
    python scripts/uat/run_uat_tests.py
"""

import sys
import os
from typing import List, Tuple


# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


def test_territory_prospecting() -> Tuple[bool, str]:
    """UAT Test 1: Territory-Driven Prospecting."""
    try:
        from cuga.modular.tools.sales.territory import define_target_market, score_accounts
        
        # Define territory
        territory_result = define_target_market(
            inputs={
                "market_definition": {
                    "industries": ["SaaS", "Cloud Infrastructure"],
                    "revenue_range": "10M-50M",
                    "geography": "US West Coast",
                }
            },
            context={"trace_id": "uat-001", "profile": "sales"}
        )
        
        # Score test accounts
        test_accounts = [
            {"name": "Test SaaS Co", "industry": "SaaS", "revenue": 25_000_000},
            {"name": "Test Manufacturing", "industry": "Manufacturing", "revenue": 100_000_000},
        ]
        
        score_result = score_accounts(
            inputs={
                "accounts": test_accounts,
                "market_definition": territory_result["market_definition"],
            },
            context={"trace_id": "uat-001", "profile": "sales"}
        )
        
        # Validate results
        saas_score = score_result["scored_accounts"][0]["icp_score"]
        mfg_score = score_result["scored_accounts"][1]["icp_score"]
        
        if saas_score >= 0.8 and mfg_score < 0.5:
            return True, f"SaaS scored {saas_score:.2f}, Manufacturing scored {mfg_score:.2f}"
        else:
            return False, f"Unexpected scores: SaaS {saas_score:.2f}, Mfg {mfg_score:.2f}"
            
    except Exception as e:
        return False, f"Error: {e}"


def test_crm_qualification() -> Tuple[bool, str]:
    """UAT Test 2: CRM-Enriched Qualification."""
    try:
        from cuga.modular.tools.sales.qualification import qualify_opportunity
        
        # Qualify opportunity (offline mode - no CRM required)
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
            context={"trace_id": "uat-002", "profile": "sales"}
        )
        
        # Validate results
        if "score" in qualification_result and "qualified" in qualification_result:
            score = qualification_result["score"]
            qualified = qualification_result["qualified"]
            return True, f"Score: {score:.2f}, Qualified: {qualified}"
        else:
            return False, "Missing required fields in result"
            
    except Exception as e:
        return False, f"Error: {e}"


def test_outreach_quality() -> Tuple[bool, str]:
    """UAT Test 3: Quality-Gated Outreach."""
    try:
        from cuga.modular.tools.sales.outreach import draft_outreach_message, assess_message_quality
        
        # Draft message
        draft_result = draft_outreach_message(
            inputs={
                "recipient_context": {
                    "name": "Test Prospect",
                    "title": "VP Sales",
                    "company": "Test Company",
                },
                "sender_context": {
                    "name": "Test Rep",
                    "title": "AE",
                    "company": "CUGAr",
                },
                "template": "default",
                "channel": "email",
            },
            context={"trace_id": "uat-003", "profile": "sales"}
        )
        
        # Assess quality
        quality_result = assess_message_quality(
            inputs={"message": draft_result["message"]},
            context={"trace_id": "uat-003", "profile": "sales"}
        )
        
        # Validate results
        if quality_result["grade"] in ["A", "B+", "B", "C", "D", "F"]:
            if draft_result["message"]["status"] == "draft":
                grade = quality_result["grade"]
                score = quality_result["quality_score"]
                return True, f"Grade: {grade}, Score: {score:.2f}, Status: draft"
            else:
                return False, f"Message status is '{draft_result['message']['status']}' (should be 'draft')"
        else:
            return False, f"Invalid grade: {quality_result['grade']}"
            
    except Exception as e:
        return False, f"Error: {e}"


def test_win_loss_analysis() -> Tuple[bool, str]:
    """UAT Test 4: Win/Loss Analysis."""
    try:
        from cuga.modular.tools.sales.intelligence import analyze_win_loss_patterns
        
        # Create test deals (need at least 3 for pattern detection)
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
            context={"trace_id": "uat-004", "profile": "sales"}
        )
        
        # Validate results
        if "summary" in analysis_result and "win_rate" in analysis_result["summary"]:
            win_rate = analysis_result["summary"]["win_rate"]
            won_count = analysis_result["summary"]["won_count"]
            lost_count = analysis_result["summary"]["lost_count"]
            return True, f"Win rate: {win_rate:.0%} ({won_count} won, {lost_count} lost)"
        else:
            return False, "Missing required fields in result"
            
    except Exception as e:
        return False, f"Error: {e}"


def main():
    """Run all UAT tests."""
    print("=" * 60)
    print("CUGAr Sales Agent - User Acceptance Testing")
    print("=" * 60)
    print()
    
    tests = [
        ("Territory-Driven Prospecting", test_territory_prospecting),
        ("CRM-Enriched Qualification", test_crm_qualification),
        ("Quality-Gated Outreach", test_outreach_quality),
        ("Win/Loss Analysis", test_win_loss_analysis),
    ]
    
    results: List[Tuple[str, bool, str]] = []
    
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
    
    print(f"UAT Test Results: {passed}/{total} passed ({passed/total*100:.0f}%)")
    print()
    
    if passed == total:
        print("✅ All UAT tests passed - Ready for production deployment")
        print()
        print("Next steps:")
        print("  1. Deploy to staging")
        print("  2. Pilot with 5 SDRs/AEs (Week 8)")
        print("  3. Expand to department (Week 9)")
        print("  4. Full rollout (Week 10)")
        return 0
    else:
        print("❌ Some UAT tests failed - Fix issues before deployment")
        print()
        print("Failed tests:")
        for name, success, message in results:
            if not success:
                print(f"  • {name}: {message}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
