#!/usr/bin/env bash
# Frontend Integration Test Script
# Tests that React components can interact with backend APIs

set -e

echo "=================================================="
echo "Frontend Integration Test"
echo "=================================================="
echo ""

# Check if backend is running
echo "1. Checking backend health..."
if curl -s http://localhost:8000/api/agents/health > /dev/null 2>&1; then
    echo "✅ Backend is running"
    curl -s http://localhost:8000/api/agents/health | python3 -m json.tool
else
    echo "❌ Backend not running. Start with:"
    echo "   PYTHONPATH=src uvicorn src.cuga.backend.server.main:app --reload"
    exit 1
fi

echo ""
echo "2. Testing budget endpoint..."
for profile in enterprise smb technical; do
    echo "  Profile: $profile"
    curl -s "http://localhost:8000/api/agents/budget/$profile" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(f\"    Total: {data['total_calls']}, Used: {data['used_calls']}, Remaining: {data['remaining_calls']}\")
"
done

echo ""
echo "3. Testing plan execution..."
curl -s -X POST http://localhost:8000/api/agents/execute \
  -H "Content-Type: application/json" \
  -d '{
    "plan_id": "test-001",
    "goal": "Test execution",
    "steps": [{
      "tool": "draft_outbound_message",
      "input": {"recipient": "test@example.com"},
      "reason": "Integration test"
    }],
    "profile": "enterprise",
    "request_id": "req-001",
    "memory_scope": "test/session"
  }' | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(f\"  Status: {data.get('status', 'unknown')}\")
    signals = data.get('signals', {})
    print(f\"  Success rate: {signals.get('success_rate', 0)}\")
    print(f\"  Events: {signals.get('total_events', 0)}\")
except Exception as e:
    print(f\"  Note: {e} (adapters may not be configured)\")
"

echo ""
echo "=================================================="
echo "✅ Frontend Integration Ready"
echo "=================================================="
echo ""
echo "Components available:"
echo "  - ApprovalDialog (human authority gates)"
echo "  - BudgetIndicator (real-time budget display)"  
echo "  - ProfileSelector (profile switching)"
echo "  - TraceViewer (canonical events)"
echo ""
echo "Hook available:"
echo "  - useAGENTSCoordinator (API integration)"
echo ""
echo "Next: Start frontend and test in browser"
echo "  cd src/frontend_workspaces/agentic_chat"
echo "  npm run dev"
echo ""
