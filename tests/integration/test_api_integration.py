#!/usr/bin/env python3
"""Test script for AGENTS.md API endpoints."""

import asyncio
import uuid
from typing import Dict, Any

# Test without external dependencies
def test_models():
    """Test that Pydantic models can be imported and instantiated."""
    try:
        from cuga.backend.api.models import (
            PlanExecutionRequest,
            PlanStepRequest,
            ToolBudgetRequest,
        )
        
        # Create a sample request
        step = PlanStepRequest(
            tool="draft_outbound_message",
            input={"recipient": "alice@example.com", "intent": "introduce"},
            reason="User requested",
            metadata={"domain": "engagement"},
        )
        
        request = PlanExecutionRequest(
            plan_id=str(uuid.uuid4()),
            goal="Draft outbound message",
            steps=[step],
            profile="enterprise",
            request_id=str(uuid.uuid4()),
            memory_scope="test/session",
        )
        
        print("✅ Pydantic models instantiated successfully")
        print(f"   Plan ID: {request.plan_id}")
        print(f"   Goal: {request.goal}")
        print(f"   Profile: {request.profile}")
        print(f"   Steps: {len(request.steps)}")
        return True
    
    except Exception as e:
        print(f"❌ Model test failed: {e}")
        return False


def test_coordinator_import():
    """Test that AGENTSCoordinator can be imported."""
    try:
        from cuga.orchestrator import AGENTSCoordinator
        
        coordinator = AGENTSCoordinator(profile="enterprise")
        budget = coordinator.get_budget_utilization()
        
        print("✅ AGENTSCoordinator imported and initialized")
        print(f"   Profile: enterprise")
        print(f"   Total calls: {budget['total_calls']}")
        print(f"   Used calls: {budget['used_calls']}")
        return True
    
    except Exception as e:
        print(f"❌ Coordinator import test failed: {e}")
        return False


def test_route_structure():
    """Test that route definitions are valid."""
    try:
        # This will work even without FastAPI installed in test env
        import sys
        import os
        
        # Read the routes file and check structure
        routes_file = os.path.join(
            os.path.dirname(__file__),
            "src/cuga/backend/api/routes/agents.py"
        )
        
        with open(routes_file, 'r') as f:
            content = f.read()
        
        # Check for required endpoints
        required_endpoints = [
            '@router.post("/execute"',
            '@router.post("/approve"',
            '@router.get("/budget/{profile}"',
            '@router.get("/trace/{trace_id}"',
            '@router.get("/health"',
        ]
        
        missing = []
        for endpoint in required_endpoints:
            if endpoint not in content:
                missing.append(endpoint)
        
        if missing:
            print(f"❌ Missing endpoints: {missing}")
            return False
        
        print("✅ All required endpoints defined")
        print(f"   POST /api/agents/execute")
        print(f"   POST /api/agents/approve")
        print(f"   GET /api/agents/budget/{{profile}}")
        print(f"   GET /api/agents/trace/{{trace_id}}")
        print(f"   GET /api/agents/health")
        return True
    
    except Exception as e:
        print(f"❌ Route structure test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("AGENTS.md API Integration Test")
    print("=" * 60)
    print()
    
    results = []
    
    print("Test 1: Pydantic Models")
    print("-" * 60)
    results.append(test_models())
    print()
    
    print("Test 2: AGENTSCoordinator Import")
    print("-" * 60)
    results.append(test_coordinator_import())
    print()
    
    print("Test 3: Route Structure")
    print("-" * 60)
    results.append(test_route_structure())
    print()
    
    print("=" * 60)
    if all(results):
        print("✅ All tests passed! API integration ready.")
        print()
        print("Next steps:")
        print("  1. Start server: uvicorn src.cuga.backend.server.main:app --reload")
        print("  2. Test endpoints: curl http://localhost:8000/api/agents/health")
        print("  3. Check Swagger docs: http://localhost:8000/docs")
        return 0
    else:
        print(f"❌ {sum(not r for r in results)} test(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
