#!/bin/bash
# CUGAr Sales Assistant Launcher for macOS/Linux
# Simple one-click startup for sales reps

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   CUGAr Sales Assistant - Local Launcher${NC}"
echo -e "${BLUE}════════════════════════════════════════════════${NC}"
echo ""

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

# Check Python installation
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}✗ Python 3 is not installed${NC}"
    echo "Please install Python 3.9+ from https://www.python.org/"
    exit 1
fi

echo -e "${GREEN}✓ Python found:${NC} $(python3 --version)"

# Check Node.js installation
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js is not installed${NC}"
    echo "Please install Node.js from https://nodejs.org/"
    exit 1
fi

echo -e "${GREEN}✓ Node.js found:${NC} $(node --version)"
echo ""

# First run check
ENV_FILE="$PROJECT_ROOT/.env.sales"
if [ ! -f "$ENV_FILE" ]; then
    echo -e "${YELLOW}⚠ First time setup detected${NC}"
    echo "Launching setup wizard..."
    echo ""
    
    python3 -m cuga.frontend.setup_wizard
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ Setup wizard failed${NC}"
        exit 1
    fi
    
    echo ""
    echo -e "${GREEN}✓ Setup complete!${NC}"
    echo ""
fi

# Install Python dependencies if needed
if [ ! -d "$PROJECT_ROOT/venv" ]; then
    echo -e "${BLUE}Installing Python dependencies...${NC}"
    python3 -m venv venv
    source venv/bin/activate
    pip install -e .
else
    source venv/bin/activate
fi

# Install Node dependencies if needed
FRONTEND_DIR="$PROJECT_ROOT/src/frontend_workspaces/agentic_chat"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo -e "${BLUE}Installing Node dependencies...${NC}"
    cd "$FRONTEND_DIR"
    npm install
    cd "$PROJECT_ROOT"
fi

echo ""
echo -e "${BLUE}Starting CUGAr Sales Assistant...${NC}"
echo ""

# Start backend in background
echo -e "${GREEN}→ Starting backend server (port 8000)...${NC}"
cd "$PROJECT_ROOT"
python3 -m uvicorn cuga.backend.server.main:app \
    --host 127.0.0.1 \
    --port 8000 \
    --log-level info &

BACKEND_PID=$!
echo "Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo -e "${YELLOW}⏳ Waiting for backend to start...${NC}"
sleep 5

# Check if backend is running
if ps -p $BACKEND_PID > /dev/null; then
    echo -e "${GREEN}✓ Backend is running${NC}"
else
    echo -e "${RED}✗ Backend failed to start${NC}"
    exit 1
fi

echo ""

# Start frontend
echo -e "${GREEN}→ Starting frontend (port 3000)...${NC}"
cd "$FRONTEND_DIR"
npm run dev &

FRONTEND_PID=$!
echo "Frontend PID: $FRONTEND_PID"

# Wait for frontend
sleep 3

echo ""
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo -e "${GREEN}   🚀 CUGAr Sales Assistant is ready!${NC}"
echo -e "${GREEN}════════════════════════════════════════════════${NC}"
echo ""
echo -e "  Backend:  ${BLUE}http://localhost:8000${NC}"
echo -e "  Frontend: ${BLUE}http://localhost:3000${NC}"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the application${NC}"
echo ""

# Open browser (macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    sleep 2
    open "http://localhost:3000"
fi

# Open browser (Linux)
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    sleep 2
    xdg-open "http://localhost:3000" 2>/dev/null || true
fi

# Cleanup function
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    
    if [ ! -z "$BACKEND_PID" ]; then
        echo "Stopping backend (PID: $BACKEND_PID)..."
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        echo "Stopping frontend (PID: $FRONTEND_PID)..."
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    echo -e "${GREEN}✓ Stopped${NC}"
    exit 0
}

# Trap Ctrl+C
trap cleanup INT TERM

# Wait for processes
wait
