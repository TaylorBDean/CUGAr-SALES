#!/bin/bash
# Simple single-process mode for local development

set -e
cd "$(dirname "$0")/.."

echo "🎯 Starting CUGAr-SALES in Local Mode"
echo ""
echo "Features:"
echo "  ✅ Single process (no separate backend)"
echo "  ✅ Built-in Streamlit UI"
echo "  ✅ Perfect for local dev/demos"
echo ""

# Check if streamlit is installed
if ! uv run python -c "import streamlit" 2>/dev/null; then
    echo "📦 Installing local mode dependencies..."
    uv pip install -e ".[local]"
fi

# Launch local UI
echo "🚀 Launching UI..."
echo ""
echo "Tip: Use Ctrl+C to stop"
echo ""
uv run streamlit run src/cuga/local_ui.py
