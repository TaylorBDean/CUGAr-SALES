#!/usr/bin/env python3
"""
Test registry integration with sales capabilities.
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def test_registry_loading():
    """Test that registry can load sales_capabilities section."""
    print("\n=== Testing Registry Loading ===\n")
    
    # Try different registry locations
    registry_paths = [
        Path(__file__).parent.parent / "docs/mcp/registry.yaml",
        Path(__file__).parent.parent / "registry.yaml",
        Path(__file__).parent.parent / "config/registry.yaml",
    ]
    
    for path in registry_paths:
        if path.exists():
            print(f"✓ Found registry: {path}")
            
            # Load and check for sales_capabilities
            import yaml
            with open(path) as f:
                data = yaml.safe_load(f)
            
            if "sales_capabilities" in data:
                print(f"✓ sales_capabilities section found")
                print(f"  - Tools defined: {len(data['sales_capabilities'])}")
                
                for tool in data['sales_capabilities']:
                    print(f"  - {tool['id']}: {tool['name']}")
                
                return True
            else:
                print(f"⚠ No sales_capabilities section in {path}")
        else:
            print(f"✗ Registry not found: {path}")
    
    return False


def test_tool_registry_class():
    """Test if ToolRegistry class can be instantiated."""
    print("\n=== Testing ToolRegistry Class ===\n")
    
    try:
        from cuga.tools.registry import ToolRegistry
        print("✓ ToolRegistry imported from cuga.tools.registry")
        
        # Check if it needs a path argument
        import inspect
        sig = inspect.signature(ToolRegistry.__init__)
        params = list(sig.parameters.keys())
        print(f"  - __init__ parameters: {params}")
        
        if "path" in params:
            print("  - Requires path parameter")
            return "path_required"
        else:
            print("  - No path parameter required")
            return "no_path_required"
            
    except ImportError as e:
        print(f"✗ Failed to import ToolRegistry: {e}")
        
        # Try alternative locations
        try:
            from cuga.agents.registry import ToolRegistry
            print("✓ ToolRegistry imported from cuga.agents.registry")
            return "agents_registry"
        except ImportError:
            try:
                from cuga.modular.tools import ToolRegistry
                print("✓ ToolRegistry imported from cuga.modular.tools")
                return "modular_registry"
            except ImportError:
                print("✗ ToolRegistry not found in any expected location")
                return None


def test_dynamic_tool_loading():
    """Test if we can dynamically import and call tools."""
    print("\n=== Testing Dynamic Tool Loading ===\n")
    
    sales_tools = [
        ("cuga.modular.tools.sales.territory", "simulate_territory_change"),
        ("cuga.modular.tools.sales.territory", "assess_capacity_coverage"),
        ("cuga.modular.tools.sales.account_intelligence", "score_account_fit"),
        ("cuga.modular.tools.sales.qualification", "qualify_opportunity"),
    ]
    
    loaded = []
    failed = []
    
    for module_path, handler_name in sales_tools:
        try:
            import importlib
            module = importlib.import_module(module_path)
            handler = getattr(module, handler_name)
            
            # Verify it's callable
            if callable(handler):
                print(f"✓ {module_path}.{handler_name}")
                loaded.append((module_path, handler_name))
            else:
                print(f"✗ {module_path}.{handler_name} (not callable)")
                failed.append((module_path, handler_name))
                
        except Exception as e:
            print(f"✗ {module_path}.{handler_name}: {e}")
            failed.append((module_path, handler_name))
    
    print(f"\n  Loaded: {len(loaded)}/{len(sales_tools)}")
    return len(loaded) == len(sales_tools)


def test_adapter_fixture_loading():
    """Test if adapter can load fixtures."""
    print("\n=== Testing Adapter Fixture Loading ===\n")
    
    try:
        from cuga.adapters.sales.factory import create_adapter
        
        adapter = create_adapter(vendor="ibm_sales_cloud", trace_id="test-registry")
        
        # Try to fetch accounts
        accounts = adapter.fetch_accounts()
        
        print(f"✓ Adapter created: {adapter.__class__.__name__}")
        print(f"✓ Accounts loaded: {len(accounts)}")
        
        if len(accounts) > 0:
            first_account = accounts[0]
            print(f"  - Sample account: {first_account.get('name', 'N/A')}")
            print(f"  - Fields: {list(first_account.keys())}")
        
        return True
        
    except Exception as e:
        print(f"✗ Adapter fixture loading failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all registry integration tests."""
    print("=" * 60)
    print("Registry Integration Tests")
    print("=" * 60)
    
    results = {
        "registry_loading": test_registry_loading(),
        "tool_registry_class": test_tool_registry_class(),
        "dynamic_loading": test_dynamic_tool_loading(),
        "adapter_fixtures": test_adapter_fixture_loading(),
    }
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    for test_name, result in results.items():
        if isinstance(result, bool):
            status = "✓ PASS" if result else "✗ FAIL"
        else:
            status = f"ℹ INFO: {result}"
        print(f"{status:20} {test_name}")
    
    passed = sum(1 for r in results.values() if r is True)
    total = len([r for r in results.values() if isinstance(r, bool)])
    
    print(f"\nResult: {passed}/{total} tests passed")
    
    if passed == total:
        print("✓ Registry integration ready!")
        return 0
    else:
        print("⚠ Some tests need attention")
        return 1


if __name__ == "__main__":
    sys.exit(main())
