#!/usr/bin/env python3
"""
External Data Feed Integration - Setup and Validation Script

Tests connectivity and configuration for all external data sources.
Use this before deploying to production to validate credentials.
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_ibm_sales_cloud():
    """Test IBM Sales Cloud integration."""
    print("\n" + "=" * 60)
    print("IBM Sales Cloud Integration Test")
    print("=" * 60)
    
    # Check environment variables
    required_env = [
        "SALES_IBM_API_ENDPOINT",
        "SALES_IBM_API_KEY",
        "SALES_IBM_TENANT_ID",
    ]
    
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(f"\nTo enable IBM Sales Cloud live mode:")
        print(f"  export SALES_IBM_ADAPTER_MODE=live")
        print(f"  export SALES_IBM_API_ENDPOINT=https://api.ibm.com/sales/v1")
        print(f"  export SALES_IBM_API_KEY=<your-api-key>")
        print(f"  export SALES_IBM_TENANT_ID=<your-tenant-id>")
        return False
    
    # Test adapter creation
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # Set live mode
        os.environ["SALES_IBM_ADAPTER_MODE"] = "live"
        
        adapter = create_adapter("ibm_sales_cloud", trace_id="setup-test")
        
        print(f"\n✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        # Test connection
        print(f"\nTesting connection...")
        is_valid = adapter.validate_connection()
        
        if is_valid:
            print(f"✓ Connection successful")
            
            # Test data fetch
            print(f"\nFetching sample data (limit 5)...")
            accounts = adapter.fetch_accounts({"limit": 5})
            
            print(f"✓ Accounts fetched: {len(accounts)}")
            if accounts:
                sample = accounts[0]
                print(f"\n  Sample Account:")
                print(f"    ID: {sample.get('id')}")
                print(f"    Name: {sample.get('name')}")
                print(f"    Industry: {sample.get('industry')}")
                print(f"    Revenue: ${sample.get('annual_revenue', 0):,.0f}")
            
            return True
        else:
            print(f"✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_salesforce():
    """Test Salesforce integration."""
    print("\n" + "=" * 60)
    print("Salesforce Integration Test")
    print("=" * 60)
    
    required_env = [
        "SALES_SFDC_INSTANCE_URL",
        "SALES_SFDC_CLIENT_ID",
        "SALES_SFDC_CLIENT_SECRET",
        "SALES_SFDC_USERNAME",
        "SALES_SFDC_PASSWORD",
    ]
    
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Salesforce adapter not configured")
        print(f"  Status: SKIP (use mock mode)")
        print(f"  Missing: {', '.join(missing)}")
        print(f"\nTo enable Salesforce live mode:")
        print(f"  export SALES_SALESFORCE_ADAPTER_MODE=live")
        print(f"  export SALES_SFDC_INSTANCE_URL=https://your-instance.salesforce.com")
        print(f"  export SALES_SFDC_CLIENT_ID=<oauth-client-id>")
        print(f"  export SALES_SFDC_CLIENT_SECRET=<oauth-secret>")
        print(f"  export SALES_SFDC_USERNAME=<username>")
        print(f"  export SALES_SFDC_PASSWORD=<password>")
        return None  # Not configured (not a failure)
    
    print("\n✓ Salesforce credentials configured")
    print("  Testing live connection...")
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # Create live adapter
        adapter = create_adapter("salesforce", trace_id="setup-test-sf")
        
        # Validate connection
        if not adapter.validate_connection():
            print("✗ FAIL: Connection validation failed")
            return False
        
        print("✓ Connection successful")
        
        # Fetch sample accounts
        accounts = adapter.fetch_accounts({"limit": 5})
        print(f"✓ Accounts fetched: {len(accounts)}")
        
        if accounts:
            print(f"\nSample account:")
            print(f"  ID: {accounts[0].get('id')}")
            print(f"  Name: {accounts[0].get('name')}")
            print(f"  Industry: {accounts[0].get('industry')}")
        
        return True
    
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_zoominfo():
    """Test ZoomInfo integration."""
    print("\n" + "=" * 60)
    print("ZoomInfo Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_ZOOMINFO_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ ZoomInfo adapter not configured")
        print(f"  Status: SKIP (use mock mode)")
        print(f"  Missing: {', '.join(missing)}")
        print(f"\nTo enable ZoomInfo live mode:")
        print(f"  export SALES_ZOOMINFO_ADAPTER_MODE=live")
        print(f"  export SALES_ZOOMINFO_API_KEY=<your-api-key>")
        return None
    
    print("\n✓ ZoomInfo credentials configured")
    print("  Testing live connection...")
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # Create live adapter
        adapter = create_adapter("zoominfo", trace_id="setup-test-zi")
        
        # Validate connection
        if not adapter.validate_connection():
            print("✗ FAIL: Connection validation failed")
            return False
        
        print("✓ Connection successful")
        
        # Fetch sample companies
        companies = adapter.fetch_accounts({"limit": 5})
        print(f"✓ Companies fetched: {len(companies)}")
        
        if companies:
            print(f"\nSample company:")
            print(f"  ID: {companies[0].get('id')}")
            print(f"  Name: {companies[0].get('name')}")
            print(f"  Industry: {companies[0].get('industry')}")
            print(f"  Employees: {companies[0].get('employee_count')}")
        
        return True
    
    except Exception as e:
        print(f"✗ FAIL: {e}")
        return False


def test_clearbit():
    """Test Clearbit integration."""
    print("\n" + "=" * 60)
    print("Clearbit Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_CLEARBIT_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Clearbit adapter not configured")
        print(f"  Status: SKIP (use mock mode)")
        print(f"  Missing: {', '.join(missing)}")
        print(f"\nTo enable Clearbit live mode:")
        print(f"  export SALES_CLEARBIT_ADAPTER_MODE=live")
        print(f"  export SALES_CLEARBIT_API_KEY=<your-api-key>")
        return None
    
    print("\n✓ Clearbit credentials configured")
    print("  Testing live connection...")
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # Create live adapter
        adapter = create_adapter("clearbit", trace_id="setup-test-cb")
        
        # Validate connection
        if not adapter.validate_connection():
            print("✗ FAIL: Connection validation failed")
            return False
        
        print("✓ Connection successful")
        
        # Test company enrichment
        print(f"\n  Testing company enrichment (stripe.com)...")
        company = adapter.enrich_company("stripe.com")
        
        if company:
            print(f"✓ Company enriched:")
            print(f"  Name: {company.get('name')}")
            print(f"  Industry: {company.get('industry')}")
            print(f"  Employees: {company.get('employees')}")
            print(f"  Location: {company.get('location', {}).get('city')}, {company.get('location', {}).get('state')}")
            
            # Test tech stack
            technologies = company.get("metadata", {}).get("technologies", [])
            if technologies:
                print(f"  Technologies ({len(technologies)}):")
                for tech in technologies[:3]:
                    print(f"    - {tech.get('name')} ({tech.get('category')})")
        else:
            print(f"✗ Company not found")
        
        # Test contact enrichment
        print(f"\n  Testing contact enrichment (sample)...")
        print(f"  Note: Requires valid email for enrichment")
        
        return True
    
    except Exception as e:
        print(f"✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_hubspot():
    """Test HubSpot integration."""
    print("\n" + "=" * 60)
    print("HubSpot Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_HUBSPOT_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ HubSpot adapter not configured")
        print(f"  Status: SKIP (use mock mode)")
        print(f"  Missing: {', '.join(missing)}")
        print(f"\nTo enable HubSpot live mode:")
        print(f"  export SALES_HUBSPOT_ADAPTER_MODE=live")
        print(f"  export SALES_HUBSPOT_API_KEY=<your-api-key>")
        return None
    
    print("\n✓ HubSpot credentials configured")
    print("  Testing live connection...")
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # Create live adapter
        adapter = create_adapter("hubspot", trace_id="setup-test-hs")
        
        # Validate connection
        if not adapter.validate_connection():
            print("✗ FAIL: Connection validation failed")
            return False
        
        print("✓ Connection successful")
        
        # Fetch sample companies
        print(f"\n  Fetching companies (limit 5)...")
        companies = adapter.fetch_accounts({"limit": 5})
        print(f"✓ Companies fetched: {len(companies)}")
        
        if companies:
            company = companies[0]
            print(f"\nSample company:")
            print(f"  ID: {company.get('id')}")
            print(f"  Name: {company.get('name')}")
            print(f"  Domain: {company.get('domain')}")
            print(f"  Industry: {company.get('industry')}")
            print(f"  Employees: {company.get('employee_count')}")
            
            # Test contacts for first company
            print(f"\n  Fetching contacts for {company.get('name')}...")
            contacts = adapter.fetch_contacts(company.get('id'), {"limit": 3})
            print(f"✓ Contacts fetched: {len(contacts)}")
            
            if contacts:
                print(f"    - {contacts[0].get('full_name')} ({contacts[0].get('email')})")
            
            # Test deals for first company
            print(f"\n  Fetching deals for {company.get('name')}...")
            deals = adapter.fetch_opportunities(company.get('id'), {"limit": 5})
            print(f"✓ Deals fetched: {len(deals)}")
            
            if deals:
                deal = deals[0]
                print(f"    - {deal.get('name')}: ${deal.get('amount'):,.2f} ({deal.get('stage')})")
        
        return True
    
    except Exception as e:
        print(f"✗ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mock_adapters():
    """Test that mock adapters work (offline mode)."""
    print("\n" + "=" * 60)
    print("Mock Adapter Test (Offline Mode)")
    print("=" * 60)
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        # Test IBM mock adapter
        adapter = create_adapter("ibm_sales_cloud", trace_id="mock-test")
        accounts = adapter.fetch_accounts()
        
        print(f"\n✓ Mock adapter working")
        print(f"✓ Mode: {adapter.get_mode().value}")
        print(f"✓ Sample accounts loaded: {len(accounts)}")
        
        if accounts:
            sample = accounts[0]
            print(f"\n  Sample Mock Account:")
            print(f"    ID: {sample.get('id')}")
            print(f"    Name: {sample.get('name')}")
            print(f"    Industry: {sample.get('industry')}")
        
        return True
        
    except Exception as e:
        print(f"\n✗ Mock adapter test failed: {e}")
        return False


def test_sixsense():
    """Test 6sense integration."""
    print("\n" + "=" * 60)
    print("6sense Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_SIXSENSE_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(f"\nTo enable 6sense live mode:")
        print(f"  export SALES_SIXSENSE_ADAPTER_MODE=live")
        print(f"  export SALES_SIXSENSE_API_KEY=<your-api-key>")
        return None
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        os.environ["SALES_SIXSENSE_ADAPTER_MODE"] = "live"
        
        adapter = create_adapter("sixsense", trace_id="setup-test")
        print(f"\n✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        print(f"\nTesting connection...")
        is_valid = adapter.validate_connection()
        
        if is_valid:
            print(f"✓ Connection successful")
            
            print(f"\nFetching sample accounts (limit 3)...")
            accounts = adapter.fetch_accounts({"limit": 3})
            print(f"✓ Accounts fetched: {len(accounts)}")
            
            if accounts:
                sample = accounts[0]
                print(f"\n  Sample Account:")
                print(f"    ID: {sample.get('id')}")
                print(f"    Name: {sample.get('name')}")
                print(f"    Intent Score: {sample.get('metadata', {}).get('intent_score', 'N/A')}")
            
            return True
        else:
            print(f"✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


def test_apollo():
    """Test Apollo.io integration."""
    print("\n" + "=" * 60)
    print("Apollo.io Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_APOLLO_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(f"\nTo enable Apollo.io live mode:")
        print(f"  export SALES_APOLLO_ADAPTER_MODE=live")
        print(f"  export SALES_APOLLO_API_KEY=<your-api-key>")
        return None
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        os.environ["SALES_APOLLO_ADAPTER_MODE"] = "live"
        
        adapter = create_adapter("apollo", trace_id="setup-test")
        print(f"\n✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        print(f"\nTesting connection...")
        is_valid = adapter.validate_connection()
        
        if is_valid:
            print(f"✓ Connection successful")
            
            print(f"\nFetching sample companies (limit 3)...")
            accounts = adapter.fetch_accounts({"limit": 3})
            print(f"✓ Companies fetched: {len(accounts)}")
            
            if accounts:
                sample = accounts[0]
                print(f"\n  Sample Company:")
                print(f"    ID: {sample.get('id')}")
                print(f"    Name: {sample.get('name')}")
                print(f"    Domain: {sample.get('domain')}")
            
            return True
        else:
            print(f"✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


def test_pipedrive():
    """Test Pipedrive integration."""
    print("\n" + "=" * 60)
    print("Pipedrive Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_PIPEDRIVE_API_TOKEN"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(f"\nTo enable Pipedrive live mode:")
        print(f"  export SALES_PIPEDRIVE_ADAPTER_MODE=live")
        print(f"  export SALES_PIPEDRIVE_API_TOKEN=<your-api-token>")
        return None
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        os.environ["SALES_PIPEDRIVE_ADAPTER_MODE"] = "live"
        
        adapter = create_adapter("pipedrive", trace_id="setup-test")
        print(f"\n✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        print(f"\nTesting connection...")
        is_valid = adapter.validate_connection()
        
        if is_valid:
            print(f"✓ Connection successful")
            
            print(f"\nFetching sample organizations (limit 3)...")
            accounts = adapter.fetch_accounts({"limit": 3})
            print(f"✓ Organizations fetched: {len(accounts)}")
            
            if accounts:
                sample = accounts[0]
                print(f"\n  Sample Organization:")
                print(f"    ID: {sample.get('id')}")
                print(f"    Name: {sample.get('name')}")
                print(f"    Address: {sample.get('location', {}).get('city', 'N/A')}")
            
            return True
        else:
            print(f"✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


def test_crunchbase():
    """Test Crunchbase integration."""
    print("\n" + "=" * 60)
    print("Crunchbase Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_CRUNCHBASE_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(f"\nTo enable Crunchbase live mode:")
        print(f"  export SALES_CRUNCHBASE_ADAPTER_MODE=live")
        print(f"  export SALES_CRUNCHBASE_API_KEY=<your-api-key>")
        return None
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        os.environ["SALES_CRUNCHBASE_ADAPTER_MODE"] = "live"
        
        adapter = create_adapter("crunchbase", trace_id="setup-test")
        print(f"\n✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        print(f"\nTesting connection...")
        is_valid = adapter.validate_connection()
        
        if is_valid:
            print(f"✓ Connection successful")
            
            print(f"\nFetching sample organizations (limit 3)...")
            accounts = adapter.fetch_accounts({"limit": 3})
            print(f"✓ Organizations fetched: {len(accounts)}")
            
            if accounts:
                sample = accounts[0]
                print(f"\n  Sample Organization:")
                print(f"    ID: {sample.get('id')}")
                print(f"    Name: {sample.get('name')}")
                funding = sample.get('metadata', {}).get('funding_total', 0)
                print(f"    Funding: ${funding:,.0f}" if funding else "    Funding: N/A")
            
            return True
        else:
            print(f"✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


def test_builtwith():
    """Test BuiltWith integration."""
    print("\n" + "=" * 60)
    print("BuiltWith Integration Test")
    print("=" * 60)
    
    required_env = ["SALES_BUILTWITH_API_KEY"]
    missing = [var for var in required_env if not os.getenv(var)]
    
    if missing:
        print(f"\n⚠ Missing environment variables:")
        for var in missing:
            print(f"  - {var}")
        print(f"\nTo enable BuiltWith live mode:")
        print(f"  export SALES_BUILTWITH_ADAPTER_MODE=live")
        print(f"  export SALES_BUILTWITH_API_KEY=<your-api-key>")
        return None
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        os.environ["SALES_BUILTWITH_ADAPTER_MODE"] = "live"
        
        adapter = create_adapter("builtwith", trace_id="setup-test")
        print(f"\n✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Mode: {adapter.get_mode().value}")
        
        print(f"\nTesting connection...")
        is_valid = adapter.validate_connection()
        
        if is_valid:
            print(f"✓ Connection successful")
            
            print(f"\nEnriching sample domain (example.com)...")
            company = adapter.enrich_company("example.com")
            
            if company:
                print(f"✓ Domain enriched successfully")
                print(f"\n  Sample Data:")
                print(f"    Domain: {company.get('domain')}")
                print(f"    Tech Count: {company.get('metadata', {}).get('technology_count', 0)}")
            else:
                print(f"⚠ Domain not found (expected for example.com)")
            
            return True
        else:
            print(f"✗ Connection failed")
            return False
            
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        return False


def check_dependencies():
    """Check required Python packages."""
    print("\n" + "=" * 60)
    print("Dependency Check")
    print("=" * 60)
    
    required_packages = [
        ("httpx", "HTTP client for API calls"),
        ("yaml", "YAML config parsing"),
        ("click", "CLI framework"),
    ]
    
    missing = []
    
    for package, description in required_packages:
        try:
            __import__(package)
            print(f"✓ {package:20} {description}")
        except ImportError:
            print(f"✗ {package:20} {description} (MISSING)")
            missing.append(package)
    
    if missing:
        print(f"\n⚠ Install missing packages:")
        print(f"  pip install {' '.join(missing)}")
        return False
    
    return True


def show_configuration_guide():
    """Show configuration guide for all data sources."""
    print("\n" + "=" * 60)
    print("External Data Feed Configuration Guide")
    print("=" * 60)
    
    print("\n📋 Configuration Priority:")
    print("  1. 🔴 IBM Sales Cloud (CRITICAL - your primary CRM)")
    print("  2. 🟡 Salesforce (HIGH - enterprise standard)")
    print("  3. 🟡 ZoomInfo (HIGH - buying signals)")
    print("  4. 🟢 Clearbit (MEDIUM - enrichment)")
    print("  5. 🟢 HubSpot (MEDIUM - mid-market CRM)")
    print("  6. 🟢 6sense (MEDIUM - predictive intent)")
    print("  7. 🟢 Apollo.io (MEDIUM - contact enrichment)")
    print("  8. 🟢 Pipedrive (MEDIUM - SMB CRM)")
    print("  9. 🔵 Crunchbase (LOW - funding events)")
    print(" 10. 🔵 BuiltWith (LOW - tech tracking)")
    
    print("\n📝 Environment Variable Template:")
    print("\n# IBM Sales Cloud (Phase 1 - CRITICAL)")
    print("export SALES_IBM_ADAPTER_MODE=live")
    print("export SALES_IBM_API_ENDPOINT=https://api.ibm.com/sales/v1")
    print("export SALES_IBM_API_KEY=<get-from-ibm-console>")
    print("export SALES_IBM_TENANT_ID=<your-organization-id>")
    
    print("\n# Salesforce (Phase 2 - HIGH)")
    print("export SALES_SALESFORCE_ADAPTER_MODE=live")
    print("export SALES_SFDC_INSTANCE_URL=https://your-instance.salesforce.com")
    print("export SALES_SFDC_CLIENT_ID=<oauth-app-client-id>")
    print("export SALES_SFDC_CLIENT_SECRET=<oauth-app-secret>")
    print("export SALES_SFDC_USERNAME=<salesforce-username>")
    print("export SALES_SFDC_PASSWORD=<salesforce-password>")
    print("export SALES_SFDC_SECURITY_TOKEN=<security-token>")
    
    print("\n# ZoomInfo (Phase 2 - HIGH)")
    print("export SALES_ZOOMINFO_ADAPTER_MODE=live")
    print("export SALES_ZOOMINFO_API_KEY=<api-key>")
    
    print("\n# Clearbit (Phase 3 - MEDIUM)")
    print("export SALES_CLEARBIT_ADAPTER_MODE=live")
    print("export SALES_CLEARBIT_API_KEY=<api-key>")
    
    print("\n# HubSpot (Phase 3 - MEDIUM)")
    print("export SALES_HUBSPOT_ADAPTER_MODE=live")
    print("export SALES_HUBSPOT_API_KEY=<api-key>")
    
    print("\n# 6sense (Phase 4 - MEDIUM)")
    print("export SALES_SIXSENSE_ADAPTER_MODE=live")
    print("export SALES_SIXSENSE_API_KEY=<api-key>")
    
    print("\n# Apollo.io (Phase 4 - MEDIUM)")
    print("export SALES_APOLLO_ADAPTER_MODE=live")
    print("export SALES_APOLLO_API_KEY=<api-key>")
    
    print("\n# Pipedrive (Phase 4 - MEDIUM)")
    print("export SALES_PIPEDRIVE_ADAPTER_MODE=live")
    print("export SALES_PIPEDRIVE_API_TOKEN=<api-token>")
    
    print("\n# Crunchbase (Phase 4 - LOW)")
    print("export SALES_CRUNCHBASE_ADAPTER_MODE=live")
    print("export SALES_CRUNCHBASE_API_KEY=<api-key>")
    
    print("\n# BuiltWith (Phase 4 - LOW)")
    print("export SALES_BUILTWITH_ADAPTER_MODE=live")
    print("export SALES_BUILTWITH_API_KEY=<api-key>")
    
    print("\n💡 Tips:")
    print("  - Start with IBM Sales Cloud (highest ROI)")
    print("  - Mock mode works offline (no credentials needed)")
    print("  - Toggle mock↔live without code changes")
    print("  - All API calls use SafeClient (10s timeout, auto-retry)")
    print("  - Phase 4 adapters: predictive intent, funding, tech tracking")


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("External Data Feed Setup & Validation")
    print("=" * 60)
    
    # Check dependencies first
    if not check_dependencies():
        print("\n✗ Install missing dependencies before continuing")
        return 1
    
    # Show configuration guide
    show_configuration_guide()
    
    # Run tests
    print("\n" + "=" * 60)
    print("Running Integration Tests")
    print("=" * 60)
    
    results = {
        "Mock Adapters": test_mock_adapters(),
        "IBM Sales Cloud": test_ibm_sales_cloud(),
        "Salesforce": test_salesforce(),
        "ZoomInfo": test_zoominfo(),
        "Clearbit": test_clearbit(),
        "HubSpot": test_hubspot(),
        "6sense": test_sixsense(),
        "Apollo.io": test_apollo(),
        "Pipedrive": test_pipedrive(),
        "Crunchbase": test_crunchbase(),
        "BuiltWith": test_builtwith(),
    }
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    passed = 0
    failed = 0
    skipped = 0
    
    for name, result in results.items():
        if result is True:
            print(f"✓ PASS    {name}")
            passed += 1
        elif result is False:
            print(f"✗ FAIL    {name}")
            failed += 1
        else:
            print(f"⊘ SKIP    {name}")
            skipped += 1
    
    print(f"\nResults: {passed} passed, {failed} failed, {skipped} skipped")
    
    if failed == 0 and passed > 0:
        print("\n✓ Ready for production deployment!")
        return 0
    elif failed > 0:
        print("\n⚠ Fix failed tests before deploying to production")
        return 1
    else:
        print("\n⚠ Configure at least one data source (or use mock mode)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
