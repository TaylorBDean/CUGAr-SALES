#!/usr/bin/env bash
# Post-hardening verification script
# Run this after completing any hardening task

set -e

echo "🔍 CUGAr-CORE Hardening Verification"
echo "===================================="
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

function check_command() {
    if command -v "$1" &> /dev/null; then
        echo -e "${GREEN}✓${NC} $1 found"
        return 0
    else
        echo -e "${RED}✗${NC} $1 not found - install with: $2"
        return 1
    fi
}

echo "Checking dependencies..."
check_command "rg" "sudo apt install ripgrep"
check_command "python3" "sudo apt install python3"

echo ""
echo "Running AGENTS.md § 4 guardrail checks..."
echo "----------------------------------------"

# Check 1: Block unsafe eval() outside sandbox
echo -n "Checking for unsafe eval()... "
if rg -n "\beval\s*\(" src/ --glob "!src/cuga/backend/tools_env/code_sandbox/**" --glob "!**test**.py" &> /dev/null; then
    echo -e "${RED}✗ FAIL${NC}"
    echo "  Found eval() outside sandbox (AGENTS.md § 4 violation)"
    rg -n "\beval\s*\(" src/ --glob "!src/cuga/backend/tools_env/code_sandbox/**" --glob "!**test**.py"
    exit 1
else
    echo -e "${GREEN}✓ PASS${NC}"
fi

# Check 2: Block unsafe exec() outside sandbox
echo -n "Checking for unsafe exec()... "
if rg -n "\bexec\s*\(" src/ --glob "!src/cuga/backend/tools_env/code_sandbox/**" --glob "!**test**.py" --glob "!**subprocess**.py" &> /dev/null; then
    echo -e "${RED}✗ FAIL${NC}"
    echo "  Found exec() outside sandbox (AGENTS.md § 4 violation)"
    rg -n "\bexec\s*\(" src/ --glob "!src/cuga/backend/tools_env/code_sandbox/**" --glob "!**test**.py" --glob "!**subprocess**.py"
    exit 1
else
    echo -e "${GREEN}✓ PASS${NC}"
fi

# Check 3: Block raw HTTP calls
echo -n "Checking for raw HTTP calls... "
if rg -n "(httpx\.Client\(|requests\.(get|post)\()" src/ --glob "!src/cuga/security/http_client.py" --glob "!**test**.py" &> /dev/null; then
    echo -e "${RED}✗ FAIL${NC}"
    echo "  Found raw HTTP calls (must use SafeClient per AGENTS.md § Tool Contract)"
    rg -n "(httpx\.Client\(|requests\.(get|post)\()" src/ --glob "!src/cuga/security/http_client.py" --glob "!**test**.py"
    exit 1
else
    echo -e "${GREEN}✓ PASS${NC}"
fi

# Check 4: Block hardcoded secrets
echo -n "Checking for hardcoded secrets... "
if rg -i "(api[_-]?key|password|secret|token)\s*=\s*['\"](?!env|test|mock|example|dummy|fake|\$)[a-zA-Z0-9]{8}" src/ --glob "!**test**.py" --glob "!**fixture**.py" &> /dev/null; then
    echo -e "${YELLOW}⚠ WARNING${NC}"
    echo "  Found potential hardcoded secrets (verify manually)"
    rg -i "(api[_-]?key|password|secret|token)\s*=\s*['\"](?!env|test|mock|example|dummy|fake|\$)[a-zA-Z0-9]{8}" src/ --glob "!**test**.py" --glob "!**fixture**.py" | head -5
else
    echo -e "${GREEN}✓ PASS${NC}"
fi

# Check 5: Block :latest container tags (if docker-compose exists)
if [ -f "ops/docker-compose.proposed.yaml" ]; then
    echo -n "Checking for :latest container tags... "
    if grep -E "image:.*:latest" ops/docker-compose.proposed.yaml &> /dev/null; then
        echo -e "${RED}✗ FAIL${NC}"
        echo "  Found :latest tag (AGENTS.md § 3 violation - must pin versions)"
        grep -E "image:.*:latest" ops/docker-compose.proposed.yaml
        exit 1
    else
        echo -e "${GREEN}✓ PASS${NC}"
    fi
fi

echo ""
echo -e "${GREEN}All guardrail checks passed!${NC}"
echo ""

# Run tests if pytest available
if command -v pytest &> /dev/null; then
    echo "Running guardrails policy tests..."
    echo "---------------------------------"
    pytest tests/unit/test_guardrails_policy.py -xvs --tb=short || {
        echo -e "${RED}✗ Tests failed${NC}"
        exit 1
    }
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${YELLOW}⚠ pytest not found - skipping tests${NC}"
    echo "  Install with: pip install pytest pytest-cov"
fi

echo ""
echo "Additional manual checks:"
echo "  • Run full test suite: pytest --cov=src --cov-fail-under=80"
echo "  • Type check: mypy src"
echo "  • Lint: ruff check ."
echo "  • Pre-commit: pre-commit run --all-files"
