#!/usr/bin/env python3
"""
Sales registry loader - loads sales_capabilities from registry.yaml
"""

import sys
import yaml
import importlib
from pathlib import Path
from typing import Dict, Any, Callable

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class SalesToolRegistry:
    """Simple registry for sales capabilities."""
    
    def __init__(self, registry_path: str | Path):
        """Load registry from YAML file."""
        self.registry_path = Path(registry_path)
        self.tools: Dict[str, Dict[str, Any]] = {}
        self._load_registry()
    
    def _load_registry(self):
        """Load sales_capabilities section from registry."""
        with open(self.registry_path) as f:
            data = yaml.safe_load(f)
        
        if "sales_capabilities" not in data:
            raise ValueError(f"No sales_capabilities section in {self.registry_path}")
        
        for tool_spec in data["sales_capabilities"]:
            tool_id = tool_spec["id"]
            
            # Dynamically import handler
            module_path = tool_spec["module"]
            handler_name = tool_spec["handler"]
            
            try:
                module = importlib.import_module(module_path)
                handler = getattr(module, handler_name)
                
                self.tools[tool_id] = {
                    "handler": handler,
                    "metadata": tool_spec,
                }
                
            except Exception as e:
                print(f"⚠ Failed to load {tool_id}: {e}")
    
    def has_tool(self, tool_id: str) -> bool:
        """Check if tool exists in registry."""
        return tool_id in self.tools
    
    def get_tool(self, tool_id: str) -> Callable:
        """Get tool handler by ID."""
        if tool_id not in self.tools:
            raise KeyError(f"Tool not found: {tool_id}")
        return self.tools[tool_id]["handler"]
    
    def get_metadata(self, tool_id: str) -> Dict[str, Any]:
        """Get tool metadata."""
        if tool_id not in self.tools:
            raise KeyError(f"Tool not found: {tool_id}")
        return self.tools[tool_id]["metadata"]
    
    def list_tools(self) -> list[str]:
        """List all registered tool IDs."""
        return list(self.tools.keys())
    
    def call_tool(self, tool_id: str, inputs: Dict[str, Any], context: Dict[str, Any]) -> Any:
        """Call a tool by ID."""
        handler = self.get_tool(tool_id)
        return handler(inputs, context)


def create_sales_registry(registry_path: str | Path | None = None) -> SalesToolRegistry:
    """
    Create sales registry from standard location.
    
    Args:
        registry_path: Path to registry.yaml (defaults to docs/mcp/registry.yaml)
    
    Returns:
        SalesToolRegistry instance
    """
    if registry_path is None:
        # Try standard locations (from src/cuga/, need to go up 2 levels)
        possible_paths = [
            Path(__file__).parent.parent.parent / "docs/mcp/registry.yaml",
            Path(__file__).parent.parent.parent / "registry.yaml",
            Path(__file__).parent.parent.parent / "config/registry.yaml",
        ]
        
        for path in possible_paths:
            if path.exists():
                registry_path = path
                break
        else:
            raise FileNotFoundError("Could not find registry.yaml in standard locations")
    
    return SalesToolRegistry(registry_path)


if __name__ == "__main__":
    """Test the sales registry."""
    print("=" * 60)
    print("Sales Tool Registry Test")
    print("=" * 60)
    
    # Create registry
    registry = create_sales_registry()
    
    print(f"\n✓ Registry loaded from: {registry.registry_path}")
    print(f"✓ Tools registered: {len(registry.list_tools())}")
    
    # List all tools
    print("\nRegistered Tools:")
    for tool_id in registry.list_tools():
        metadata = registry.get_metadata(tool_id)
        print(f"  - {tool_id}")
        print(f"    Name: {metadata['name']}")
        print(f"    Module: {metadata['module']}")
        print(f"    Approval: {metadata.get('requires_approval', False)}")
    
    # Test calling a tool
    print("\n=== Testing Tool Execution ===")
    
    result = registry.call_tool(
        "sales.assess_capacity_coverage",
        inputs={
            "territories": [
                {"territory_id": "west-1", "rep_count": 5, "account_count": 450},
                {"territory_id": "east-1", "rep_count": 3, "account_count": 180},
            ],
            "capacity_threshold": 0.85,
        },
        context={"trace_id": "registry-test-001", "profile": "sales"}
    )
    
    print(f"✓ Tool executed successfully")
    print(f"  - Analysis ID: {result['analysis_id']}")
    print(f"  - Overall Capacity: {result['overall_capacity']:.2f}")
    print(f"  - Coverage Gaps: {len(result['coverage_gaps'])}")
    
    print("\n✓ Sales registry fully functional!")
