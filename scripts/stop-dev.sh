#!/bin/bash
# Stop CUGAr-SALES development servers

cd "$(dirname "$0")/.."

echo "🛑 Stopping servers..."

if [[ -f .backend.pid ]]; then
  kill $(cat .backend.pid) 2>/dev/null && echo "   ✅ Backend stopped (PID $(cat .backend.pid))" || echo "   ⚠️  Backend not running"
  rm -f .backend.pid
fi

if [[ -f .frontend.pid ]]; then
  kill $(cat .frontend.pid) 2>/dev/null && echo "   ✅ Frontend stopped (PID $(cat .frontend.pid))" || echo "   ⚠️  Frontend not running"
  rm -f .frontend.pid
fi

# Cleanup any lingering processes
lsof -ti:8000 2>/dev/null | xargs kill -9 2>/dev/null || true
lsof -ti:3000 2>/dev/null | xargs kill -9 2>/dev/null || true

echo ""
echo "✅ Servers stopped"
