#!/usr/bin/env python3
"""
Quick E2E test for sales agent execution.
Validates the critical path: Tools → Adapters → Registry
"""

import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_territory_planning():
    """Test territory capacity assessment workflow."""
    print("\n=== Test 1: Territory Planning ===")
    
    try:
        from cuga.modular.tools.sales.territory import assess_capacity_coverage
        
        inputs = {
            "territories": [
                {
                    "territory_id": "west-1",
                    "rep_count": 5,
                    "account_count": 450,
                    "region": "west",
                },
                {
                    "territory_id": "east-1",
                    "rep_count": 3,
                    "account_count": 180,
                    "region": "east",
                },
            ],
            "capacity_threshold": 0.85,
        }
        context = {
            "trace_id": "test-territory-001",
            "profile": "sales",
        }
        
        result = assess_capacity_coverage(inputs, context)
        
        print(f"✓ Analysis ID: {result['analysis_id']}")
        print(f"✓ Overall Capacity: {result['overall_capacity']:.2f}")
        print(f"✓ Coverage Gaps: {len(result['coverage_gaps'])}")
        
        return True
    except Exception as e:
        print(f"✗ Territory planning failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_account_intelligence():
    """Test account scoring workflow."""
    print("\n=== Test 2: Account Intelligence ===")
    
    try:
        from cuga.modular.tools.sales.account_intelligence import score_account_fit
        
        # score_account_fit expects "account" dict, not "account_id"
        inputs = {
            "account": {
                "account_id": "acme_corp",
                "revenue": 50000000,
                "employee_count": 2000,
                "industry": "technology",
                "region": "north_america",
            },
            "icp_criteria": {
                "min_revenue": 10000000,
                "max_employee_count": 5000,
                "target_industries": ["technology", "manufacturing"],
            },
        }
        context = {
            "trace_id": "test-account-001",
            "profile": "sales",
        }
        
        result = score_account_fit(inputs, context)
        
        print(f"✓ Account: {result['account_id']}")
        print(f"✓ Fit Score: {result['fit_score']:.2f}")
        print(f"✓ Recommendation: {result['recommendation']}")
        
        return True
    except Exception as e:
        print(f"✗ Account intelligence failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_qualification():
    """Test opportunity qualification workflow."""
    print("\n=== Test 3: Opportunity Qualification ===")
    
    try:
        from cuga.modular.tools.sales.qualification import qualify_opportunity
        
        inputs = {
            "opportunity_id": "opp-12345",
            "criteria": {
                "budget": True,
                "authority": True,
                "need": True,
                "timing": False,
            },
        }
        context = {
            "trace_id": "test-qual-001",
            "profile": "sales",
        }
        
        result = qualify_opportunity(inputs, context)
        
        print(f"✓ Opportunity: {result['opportunity_id']}")
        print(f"✓ Qualification Score: {result['qualification_score']:.2f}")
        print(f"✓ Qualified: {result['qualified']}")
        print(f"✓ Gaps: {len(result['gaps'])}")
        
        return True
    except Exception as e:
        print(f"✗ Qualification failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_adapter_integration():
    """Test hot-swap adapter integration."""
    print("\n=== Test 4: Adapter Integration ===")
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # create_adapter only takes vendor and trace_id
        adapter = create_adapter(vendor="ibm_sales_cloud", trace_id="test-adapter-001")
        
        accounts = adapter.fetch_accounts()
        print(f"✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Accounts fetched: {len(accounts)}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        # Test filtering
        tech_accounts = adapter.fetch_accounts(filters={"industry": "technology"})
        print(f"✓ Filtered accounts: {len(tech_accounts)}")
        
        return True
    except Exception as e:
        print(f"✗ Adapter integration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_tool_imports():
    """Test that all sales tools can be imported."""
    print("\n=== Test 5: Tool Imports ===")
    
    try:
        from cuga.modular.tools.sales import (
            simulate_territory_change,
            assess_capacity_coverage,
            normalize_account_record,
            score_account_fit,
            retrieve_account_signals,
            qualify_opportunity,
            assess_deal_risk,
            analyze_win_loss_patterns,
            extract_buyer_personas,
            draft_outbound_message,
            assess_message_quality,
        )
        
        tools = [
            "simulate_territory_change",
            "assess_capacity_coverage",
            "normalize_account_record",
            "score_account_fit",
            "retrieve_account_signals",
            "qualify_opportunity",
            "assess_deal_risk",
            "analyze_win_loss_patterns",
            "extract_buyer_personas",
            "draft_outbound_message",
            "assess_message_quality",
        ]
        
        print(f"✓ All {len(tools)} sales tools imported successfully")
        
        for tool in tools:
            print(f"  - {tool}")
        
        return True
    except Exception as e:
        print(f"✗ Tool imports failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all E2E tests."""
    print("=" * 60)
    print("Sales Agent E2E Test Suite")
    print("=" * 60)
    
    tests = [
        ("Territory Planning", test_territory_planning),
        ("Account Intelligence", test_account_intelligence),
        ("Opportunity Qualification", test_qualification),
        ("Adapter Integration", test_adapter_integration),
        ("Tool Imports", test_tool_imports),
    ]
    
    results = []
    for name, test_fn in tests:
        try:
            success = test_fn()
            results.append((name, success))
        except Exception as e:
            print(f"\n✗ {name} crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    
    for name, success in results:
        status = "✓ PASS" if success else "✗ FAIL"
        print(f"{status:8} {name}")
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ All E2E tests passing! Ready for full execution.")
        return 0
    else:
        print("✗ Some tests failed. Check output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
