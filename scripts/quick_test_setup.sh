#!/bin/bash
# Quick setup script for running adapter tests only (no full install)
# This bypasses LangChain dependency resolution issues

set -e

echo "🚀 Quick Test Environment Setup"
echo "================================"
echo ""

# Check if we're already in a venv
if [[ -n "$VIRTUAL_ENV" ]]; then
    echo "⚠️  Already in a virtual environment: $VIRTUAL_ENV"
    echo "   Deactivate first with: deactivate"
    exit 1
fi

# Create test-only venv
echo "📦 Creating test-only virtual environment..."
python3 -m venv .venv-test

# Activate
echo "🔧 Activating environment..."
source .venv-test/bin/activate

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip setuptools wheel --quiet

# Install minimal test dependencies with constraints
echo "📥 Installing test dependencies (using constraints)..."
pip install -c constraints-test.txt \
    pytest \
    pytest-asyncio \
    pytest-mock \
    httpx \
    tenacity \
    loguru \
    pyyaml \
    click \
    --quiet

# Install cuga package in editable mode (no dependencies)
echo "📦 Installing cuga package (editable, no deps)..."
pip install --no-deps -e . --quiet

echo ""
echo "✅ Test environment ready!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next steps:"
echo ""
echo "  1. Activate environment:"
echo "     source .venv-test/bin/activate"
echo ""
echo "  2. Run adapter tests:"
echo "     PYTHONPATH=src pytest tests/adapters/ -v"
echo ""
echo "  3. Run integration tests:"
echo "     PYTHONPATH=src pytest tests/adapters/test_hotswap_integration.py -v"
echo ""
echo "  4. Run specific adapter:"
echo "     PYTHONPATH=src pytest tests/adapters/test_sixsense_live.py -v"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "💡 This environment includes ONLY test dependencies"
echo "   (no LangChain, no orchestration - fast & conflict-free)"
echo ""
