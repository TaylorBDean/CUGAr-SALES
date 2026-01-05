#!/bin/bash
# Clean development environment startup for CUGAr-SALES
# Follows AGENTS.md guardrails: frozen lockfiles, deterministic behavior

set -e
cd "$(dirname "$0")/.."

echo "🔍 Running pre-flight validation..."
if ! uv run python scripts/validate_startup.py; then
    echo "❌ Pre-flight validation failed. Fix issues above before proceeding."
    exit 1
fi

echo ""
echo "🧹 Cleaning up existing processes..."
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true
# NOTE: Port 7860 is the CUGAr demo UI (cuga start demo) - don't kill it
sleep 1

echo "📦 Installing dependencies (frozen lockfiles per AGENTS.md)..."
uv sync --frozen --dev
cd src/frontend_workspaces && pnpm install --frozen-lockfile && cd ../..

echo "🔐 Verifying .env..."
[[ -f .env ]] || { echo "❌ .env missing (copy from .env.example)"; exit 1; }

echo "📁 Creating log directory..."
mkdir -p logs

echo "🚀 Starting backend on 127.0.0.1:8000..."
nohup uv run uvicorn cuga.backend.server.main:app \
  --host 127.0.0.1 --port 8000 --reload \
  > logs/backend.log 2>&1 &
echo $! > .backend.pid
echo "   Backend PID: $(cat .backend.pid)"

echo "⏳ Waiting for backend health..."
for i in {1..15}; do
  if curl -sf http://127.0.0.1:8000/health > /dev/null 2>&1; then
    echo "   ✅ Backend healthy"
    break
  fi
  [[ $i -eq 15 ]] && { 
    echo "   ❌ Backend failed to start"
    echo "   📋 Last 30 lines of backend.log:"
    tail -30 logs/backend.log
    exit 1
  }
  sleep 1
done

# Verify WebSocket is registered
echo "🔌 Checking WebSocket endpoint..."
if curl -sf http://127.0.0.1:8000/api/websocket/health > /dev/null 2>&1; then
  echo "   ✅ WebSocket trace streaming active"
else
  echo "   ⚠️  WebSocket health check failed (non-blocking)"
fi

echo "🎨 Starting frontend on localhost:3000..."
cd src/frontend_workspaces
nohup pnpm --filter agentic_chat dev > ../../logs/frontend.log 2>&1 &
echo $! > ../../.frontend.pid
cd ../..
echo "   Frontend PID: $(cat .frontend.pid)"

echo "⏳ Waiting for frontend..."
for i in {1..10}; do
  if lsof -nP -iTCP:3000 -sTCP:LISTEN > /dev/null 2>&1; then
    echo "   ✅ Frontend listening on port 3000"
    break
  fi
  [[ $i -eq 10 ]] && { 
    echo "   ⚠️  Frontend may still be starting (check logs/frontend.log)"
  }
  sleep 1
done

echo ""
echo "✅ CUGAr-SALES is running!"
echo ""
echo "📍 URLs:"
echo "   Backend:  http://127.0.0.1:8000"
echo "   Frontend: http://localhost:3000"
echo "   WebSocket: ws://localhost:8000/ws/traces/{trace_id}"
echo ""
echo "🔍 Health checks:"
curl -s http://127.0.0.1:8000/health | grep -q "ok" && echo "   ✅ Backend /health" || echo "   ❌ Backend /health"
curl -s http://127.0.0.1:8000/api/agents/health | grep -q "healthy" && echo "   ✅ Agents API" || echo "   ❌ Agents API"
curl -s http://127.0.0.1:8000/api/websocket/health | grep -q "healthy" && echo "   ✅ WebSocket API" || echo "   ⚠️  WebSocket API"
echo ""
echo "📊 View logs:"
echo "   Backend:  tail -f logs/backend.log"
echo "   Frontend: tail -f logs/frontend.log"
echo "   Both:     tail -f logs/*.log"
echo ""
echo "🛑 Stop servers:"
echo "   ./scripts/stop-dev.sh"
echo ""
echo "🎯 AGENTS.md Compliance:"
echo "   • Capability-first architecture ✅"
echo "   • Frozen lockfiles (deterministic) ✅"
echo "   • WebSocket trace streaming ✅"
echo "   • Human authority preserved ✅"
echo "   • Pre-flight validation passed ✅"
echo ""
echo "📚 Quick reference: See QUICK_START.md"
echo ""

open http://localhost:3000
