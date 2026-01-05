#!/usr/bin/env python3
"""
Quick Integration Verification Script
Tests all components can be imported and initialized
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_orchestrator():
    """Test orchestrator components."""
    try:
        from cuga.orchestrator import (
            AGENTSCoordinator,
            TraceEmitter,
            BudgetEnforcer,
            ApprovalManager,
            ProfileLoader,
        )
        
        coordinator = AGENTSCoordinator(profile="enterprise")
        budget = coordinator.get_budget_utilization()
        
        print("✅ Orchestrator: AGENTSCoordinator initialized")
        print(f"   - Profile: enterprise")
        print(f"   - Budget limit: {budget['total']['limit']} calls")
        return True
    except Exception as e:
        print(f"❌ Orchestrator: {e}")
        return False


def test_backend_api():
    """Test backend API components."""
    try:
        from cuga.backend.api.models import (
            PlanExecutionRequest,
            PlanStepRequest,
            BudgetInfoResponse,
        )
        from cuga.backend.api.routes import agents_router
        
        print("✅ Backend API: Models and routes imported")
        print(f"   - Router prefix: {agents_router.prefix}")
        print(f"   - Endpoints: {len(agents_router.routes)}")
        return True
    except Exception as e:
        print(f"❌ Backend API: {e}")
        return False


def test_websocket():
    """Test WebSocket components."""
    try:
        from cuga.backend.api.websocket import (
            traces_router,
            get_trace_manager,
            TraceConnectionManager,
        )
        
        manager = get_trace_manager()
        
        print("✅ WebSocket: Components imported")
        print(f"   - Manager type: {type(manager).__name__}")
        print(f"   - Router available: Yes")
        return True
    except Exception as e:
        print(f"❌ WebSocket: {e}")
        return False


def test_file_structure():
    """Test file structure is correct."""
    required_files = [
        "src/cuga/orchestrator/coordinator.py",
        "src/cuga/backend/api/models/agent_requests.py",
        "src/cuga/backend/api/routes/agents.py",
        "src/cuga/backend/api/websocket/traces.py",
        "src/frontend_workspaces/agentic_chat/src/hooks/useAGENTSCoordinator.ts",
        "src/frontend_workspaces/agentic_chat/src/hooks/useTraceStream.ts",
        "tests/integration/test_coordinator_integration.py",
    ]
    
    project_root = Path(__file__).parent
    missing = []
    
    for file_path in required_files:
        full_path = project_root / file_path
        if not full_path.exists():
            missing.append(file_path)
    
    if missing:
        print(f"❌ File Structure: {len(missing)} files missing")
        for f in missing:
            print(f"   - {f}")
        return False
    else:
        print("✅ File Structure: All required files present")
        print(f"   - Verified: {len(required_files)} files")
        return True


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("CUGAr Integration Verification")
    print("=" * 60)
    print()
    
    results = {
        "File Structure": test_file_structure(),
        "Orchestrator": test_orchestrator(),
        "Backend API": test_backend_api(),
        "WebSocket": test_websocket(),
    }
    
    print()
    print("=" * 60)
    print("Summary")
    print("=" * 60)
    
    for component, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {component}")
    
    print()
    
    if all(results.values()):
        print("🎉 All components verified successfully!")
        print()
        print("Next steps:")
        print("  1. Run: ./STARTUP_GUIDE.sh")
        print("  2. Start backend in Terminal 1")
        print("  3. Start frontend in Terminal 2")
        print("  4. Test at http://localhost:5173")
        return 0
    else:
        print(f"⚠️  {sum(not v for v in results.values())} component(s) failed verification")
        return 1


if __name__ == "__main__":
    sys.exit(main())
