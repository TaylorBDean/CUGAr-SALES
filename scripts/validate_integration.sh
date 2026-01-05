#!/bin/bash
# Integration validation script - verifies all refactoring is correct

set -e

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         CUGAr-SALES Integration Validation                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILURES=0

# Check 1: Frontend defaults to port 8000
echo "🔍 Checking frontend default port..."
if grep -q "return 'http://localhost:8000'" src/frontend_workspaces/agentic_chat/src/constants.ts; then
    echo -e "${GREEN}✅ Frontend correctly defaults to port 8000${NC}"
else
    echo -e "${RED}❌ Frontend does not default to port 8000${NC}"
    FAILURES=$((FAILURES + 1))
fi

# Check 2: Start script comment about port 7860
echo "🔍 Checking start-dev.sh preserves Langflow..."
if grep -q "Port 7860 is the CUGAr demo UI" scripts/start-dev.sh; then
    echo -e "${GREEN}✅ start-dev.sh correctly preserves port 7860${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: Port 7860 comment not found in start-dev.sh${NC}"
fi

# Check 3: Documentation files exist
echo "🔍 Checking documentation files..."
DOCS=(
    "docs/DEPLOYMENT_MODES.md"
    "INTEGRATION_REFACTORING_COMPLETE.md"
    "INTEGRATION_HARDENING_PLAN.md"
    "PORT_7860_ISSUE.md"
)

for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo -e "${GREEN}✅ $doc exists${NC}"
    else
        echo -e "${RED}❌ $doc missing${NC}"
        FAILURES=$((FAILURES + 1))
    fi
done

# Check 4: PORT_7860_ISSUE.md has correct content
echo "🔍 Checking PORT_7860_ISSUE.md content..."
if grep -q "intentional Demo UI" PORT_7860_ISSUE.md; then
    echo -e "${GREEN}✅ PORT_7860_ISSUE.md correctly describes Langflow${NC}"
else
    echo -e "${RED}❌ PORT_7860_ISSUE.md missing correct description${NC}"
    FAILURES=$((FAILURES + 1))
fi

# Check 5: QUICK_START.md updated
echo "🔍 Checking QUICK_START.md..."
if grep -q "Port 7860.*intentionally NOT killed" QUICK_START.md; then
    echo -e "${GREEN}✅ QUICK_START.md correctly explains port 7860${NC}"
else
    echo -e "${YELLOW}⚠️  Warning: QUICK_START.md may need port 7860 note${NC}"
fi

# Check 6: settings.toml has demo port
echo "🔍 Checking settings.toml configuration..."
if grep -q "demo = 7860" src/cuga/settings.toml; then
    echo -e "${GREEN}✅ settings.toml correctly defines demo port${NC}"
else
    echo -e "${RED}❌ settings.toml missing demo port definition${NC}"
    FAILURES=$((FAILURES + 1))
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo ""

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}✨ ALL CHECKS PASSED - Integration is ready!${NC}"
    echo ""
    echo "Ready to launch:"
    echo "  ./scripts/start-dev.sh"
    echo ""
    exit 0
else
    echo -e "${RED}❌ $FAILURES check(s) failed${NC}"
    echo ""
    echo "Please review the issues above before launching."
    exit 1
fi
