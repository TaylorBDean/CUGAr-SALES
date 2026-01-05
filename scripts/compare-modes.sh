#!/bin/bash
# Help users choose between local and production mode

cat << 'EOF'
╔══════════════════════════════════════════════════════════════╗
║              CUGAr-SALES Deployment Modes                    ║
╚══════════════════════════════════════════════════════════════╝

🏠 LOCAL MODE (Simplified)
   • Single process - everything runs together
   • One command: ./scripts/start-local.sh
   • Streamlit UI - simple and fast
   • Perfect for: Solo dev, learning, quick demos
   
🏢 PRODUCTION MODE (Full Stack)
   • Separate backend (FastAPI) + frontend (React)
   • Two commands: ./scripts/start-dev.sh
   • Full-featured React UI with WebSocket streaming
   • Perfect for: Teams, enterprise, production deployment

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Which mode should you use?

├─ Are you working solo or learning?  → LOCAL MODE
├─ Need quick setup for a demo?       → LOCAL MODE
├─ Working with a team?                → PRODUCTION MODE
└─ Deploying to production?            → PRODUCTION MODE

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Commands:

  Local Mode:       ./scripts/start-local.sh
                    cuga local ui
                    cuga local chat

  Production Mode:  ./scripts/start-dev.sh

  Compare:          cuga local compare
  Demo:             cuga local demo

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

For more details, see docs/LOCAL_MODE.md

EOF
