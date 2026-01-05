"""
Smoke test for hot-swap adapter system.

Validates:
- Mock adapter loads fixtures successfully
- Factory defaults to mock mode
- Filtering works correctly
- Integration with Phase 4 tools (optional)
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_mock_adapter_import():
    """Test 1: Can import adapter system"""
    print("✓ Test 1: Importing adapter system...")
    
    try:
        from cuga.adapters import create_adapter, AdapterMode, get_adapter_status
        print("  ✓ Imports successful")
        return True
    except ImportError as exc:
        print(f"  ✗ Import failed: {exc}")
        return False


def test_mock_adapter_creation():
    """Test 2: Can create mock adapter"""
    print("\n✓ Test 2: Creating mock adapter...")
    
    try:
        from cuga.adapters import create_adapter, AdapterMode
        
        adapter = create_adapter("ibm_sales_cloud")
        
        if adapter.get_mode() != AdapterMode.MOCK:
            print(f"  ✗ Expected MOCK mode, got {adapter.get_mode()}")
            return False
        
        print(f"  ✓ Adapter created in MOCK mode")
        return True
    except Exception as exc:
        print(f"  ✗ Adapter creation failed: {exc}")
        return False


def test_mock_adapter_fetch_accounts():
    """Test 3: Can fetch accounts from fixtures"""
    print("\n✓ Test 3: Fetching accounts...")
    
    try:
        from cuga.adapters import create_adapter
        
        adapter = create_adapter("ibm_sales_cloud")
        accounts = adapter.fetch_accounts()
        
        if not accounts:
            print("  ✗ No accounts returned")
            return False
        
        if len(accounts) != 5:
            print(f"  ✗ Expected 5 accounts, got {len(accounts)}")
            return False
        
        print(f"  ✓ Fetched {len(accounts)} accounts")
        
        # Verify account structure
        first_account = accounts[0]
        required_fields = ["id", "name", "industry", "territory", "annual_revenue"]
        
        for field in required_fields:
            if field not in first_account:
                print(f"  ✗ Missing field: {field}")
                return False
        
        print(f"  ✓ Account structure valid: {first_account['name']}")
        return True
    except Exception as exc:
        print(f"  ✗ Fetch accounts failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_mock_adapter_fetch_contacts():
    """Test 4: Can fetch contacts from fixtures"""
    print("\n✓ Test 4: Fetching contacts...")
    
    try:
        from cuga.adapters import create_adapter
        
        adapter = create_adapter("ibm_sales_cloud")
        contacts = adapter.fetch_contacts(account_id="ACC-001")
        
        if not contacts:
            print("  ✗ No contacts returned")
            return False
        
        print(f"  ✓ Fetched {len(contacts)} contacts for ACC-001")
        
        # Verify contact structure
        first_contact = contacts[0]
        # IBM fixtures have first_name/last_name, not name
        required_fields = ["id", "account_id", "first_name", "last_name", "title", "email"]
        
        for field in required_fields:
            if field not in first_contact:
                print(f"  ✗ Missing field: {field}")
                return False
        
        print(f"  ✓ Contact structure valid: {first_contact['first_name']} {first_contact['last_name']} ({first_contact['title']})")
        return True
    except Exception as exc:
        print(f"  ✗ Fetch contacts failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_mock_adapter_fetch_opportunities():
    """Test 5: Can fetch opportunities from fixtures"""
    print("\n✓ Test 5: Fetching opportunities...")
    
    try:
        from cuga.adapters import create_adapter
        
        adapter = create_adapter("ibm_sales_cloud")
        opportunities = adapter.fetch_opportunities()
        
        if not opportunities:
            print("  ✗ No opportunities returned")
            return False
        
        print(f"  ✓ Fetched {len(opportunities)} opportunities")
        
        # Verify opportunity structure
        first_opp = opportunities[0]
        required_fields = ["id", "account_id", "name", "stage", "amount"]
        
        for field in required_fields:
            if field not in first_opp:
                print(f"  ✗ Missing field: {field}")
                return False
        
        print(f"  ✓ Opportunity structure valid: {first_opp['name']} (${first_opp['amount']:,})")
        return True
    except Exception as exc:
        print(f"  ✗ Fetch opportunities failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_mock_adapter_filtering():
    """Test 6: Can filter accounts by territory"""
    print("\n✓ Test 6: Testing account filtering...")
    
    try:
        from cuga.adapters import create_adapter
        
        adapter = create_adapter("ibm_sales_cloud")
        
        # Filter by NA-WEST territory (IBM fixtures use NA-WEST, not "West")
        west_accounts = adapter.fetch_accounts(filters={"territory": "NA-WEST"})
        
        if not west_accounts:
            print("  ✗ No NA-WEST accounts returned")
            return False
        
        # Verify all accounts are in NA-WEST territory
        for account in west_accounts:
            if account.get("territory") != "NA-WEST":
                print(f"  ✗ Expected NA-WEST territory, got {account.get('territory')}")
                return False
        
        print(f"  ✓ Filtered to {len(west_accounts)} NA-WEST accounts")
        return True
    except Exception as exc:
        print(f"  ✗ Filtering failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_adapter_status():
    """Test 7: Can get adapter status"""
    print("\n✓ Test 7: Getting adapter status...")
    
    try:
        from cuga.adapters import get_adapter_status
        
        status = get_adapter_status("ibm_sales_cloud")
        
        if status["vendor"] != "ibm_sales_cloud":
            print(f"  ✗ Wrong vendor: {status['vendor']}")
            return False
        
        if status["mode"] != "mock":
            print(f"  ✗ Expected mock mode, got {status['mode']}")
            return False
        
        if not status["configured"]:
            print("  ✗ Mock adapter should always be configured")
            return False
        
        print(f"  ✓ Status: {status['mode']} mode, configured={status['configured']}")
        return True
    except Exception as exc:
        print(f"  ✗ Get status failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_validate_connection():
    """Test 8: Can validate connection"""
    print("\n✓ Test 8: Validating connection...")
    
    try:
        from cuga.adapters import create_adapter
        
        adapter = create_adapter("ibm_sales_cloud")
        is_valid = adapter.validate_connection()
        
        if not is_valid:
            print("  ✗ Mock adapter should always validate successfully")
            return False
        
        print("  ✓ Connection validated")
        return True
    except Exception as exc:
        print(f"  ✗ Validation failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def test_convenience_constructors():
    """Test 9: Can use convenience constructors"""
    print("\n✓ Test 9: Testing convenience constructors...")
    
    try:
        from cuga.adapters.sales.factory import (
            create_ibm_adapter,
            create_salesforce_adapter,
            create_hubspot_adapter,
        )
        
        # Test IBM adapter
        ibm_adapter = create_ibm_adapter()
        accounts = ibm_adapter.fetch_accounts()
        
        if not accounts:
            print("  ✗ IBM adapter failed")
            return False
        
        print(f"  ✓ create_ibm_adapter() works ({len(accounts)} accounts)")
        
        # Test Salesforce adapter (should work even without fixtures)
        sf_adapter = create_salesforce_adapter()
        
        print("  ✓ create_salesforce_adapter() works")
        
        return True
    except Exception as exc:
        print(f"  ✗ Convenience constructors failed: {exc}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all smoke tests"""
    print("=" * 60)
    print("Hot-Swap Adapter System Smoke Test")
    print("=" * 60)
    
    tests = [
        test_mock_adapter_import,
        test_mock_adapter_creation,
        test_mock_adapter_fetch_accounts,
        test_mock_adapter_fetch_contacts,
        test_mock_adapter_fetch_opportunities,
        test_mock_adapter_filtering,
        test_adapter_status,
        test_validate_connection,
        test_convenience_constructors,
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as exc:
            print(f"  ✗ Test crashed: {exc}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"Passed: {passed}/{total}")
    print(f"Failed: {total - passed}/{total}")
    
    if passed == total:
        print("\n✓ All tests passed! System is ready for use.")
        return 0
    else:
        print(f"\n✗ {total - passed} test(s) failed. See errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
