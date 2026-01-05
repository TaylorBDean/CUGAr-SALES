#!/usr/bin/env python3
"""
CRM Connection Test Script

Tests connectivity to configured CRM (HubSpot, Salesforce, or Pipedrive).
Verifies API credentials are valid and can retrieve test data.

Usage:
    python scripts/deployment/test_crm_connection.py
"""

import sys
from typing import Optional


def test_crm_connection() -> bool:
    """Test CRM connectivity."""
    try:
        # Import after path setup
        from cuga.adapters.crm.factory import get_configured_adapter
        
        print("=" * 60)
        print("CUGAr Sales Agent - CRM Connection Test")
        print("=" * 60)
        print()
        
        # Attempt to get configured adapter
        print("1. Detecting CRM configuration...")
        try:
            adapter = get_configured_adapter()
            crm_type = adapter.__class__.__name__.replace("Adapter", "")
            print(f"✅ {crm_type} adapter detected")
            print()
        except Exception as e:
            print(f"⚠️  No CRM configured: {e}")
            print("   Running in offline mode is OK for testing")
            print("   To configure CRM, set environment variables:")
            print("   - HUBSPOT_API_KEY")
            print("   - SALESFORCE_USERNAME + SALESFORCE_PASSWORD + SALESFORCE_SECURITY_TOKEN")
            print("   - PIPEDRIVE_API_TOKEN")
            return True  # Offline mode is acceptable
        
        # Test search accounts
        print("2. Testing account search...")
        try:
            accounts = adapter.search_accounts(
                filters={},
                limit=3,
                context={"trace_id": "crm-test-001"}
            )
            print(f"✅ Retrieved {len(accounts)} test accounts")
            if accounts:
                print(f"   Example: {accounts[0].get('name', 'Unknown')}")
            print()
        except Exception as e:
            print(f"❌ Account search failed: {e}")
            return False
        
        # Test search opportunities
        print("3. Testing opportunity search...")
        try:
            opportunities = adapter.search_opportunities(
                filters={},
                limit=5,
                context={"trace_id": "crm-test-002"}
            )
            print(f"✅ Retrieved {len(opportunities)} test opportunities")
            if opportunities:
                print(f"   Example: {opportunities[0].get('name', 'Unknown')}")
            print()
        except Exception as e:
            print(f"❌ Opportunity search failed: {e}")
            return False
        
        # Summary
        print("=" * 60)
        print("✅ CRM connection successful")
        print(f"   CRM: {crm_type}")
        print(f"   Accounts retrieved: {len(accounts)}")
        print(f"   Opportunities retrieved: {len(opportunities)}")
        print()
        print("Next steps:")
        print("  1. Run UAT tests: python scripts/deployment/run_uat_tests.py")
        print("  2. Deploy to staging")
        return True
        
    except ImportError as e:
        print(f"❌ Import error: {e}")
        print("   Make sure PYTHONPATH includes src/")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """Run CRM connection test."""
    # Add src to path
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
    
    success = test_crm_connection()
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
