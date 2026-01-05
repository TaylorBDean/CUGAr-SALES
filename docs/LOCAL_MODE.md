# CUGAr-SALES Local Mode

## Overview

Local Mode is a **simplified single-process deployment** of CUGAr-SALES designed for:
- 🏠 Local development
- 🎓 Learning and experimentation  
- 🎬 Quick demos
- 🧪 Testing without infrastructure

Unlike Production Mode (separate FastAPI backend + React frontend), Local Mode runs everything in one process using Streamlit.

## Quick Start

### Option 1: Web UI (Streamlit)

```bash
# Install dependencies
uv pip install -e ".[local]"

# Start local UI
./scripts/start-local.sh
```

Browser opens automatically to `http://localhost:8501`

### Option 2: Terminal Chat

```bash
# Interactive CLI chat (no UI)
cuga local chat
```

### Option 3: Pure CLI

```bash
# One-shot queries
cuga plan "Find sales leads in Chicago"
cuga execute --trace-id <id>
```

## Features

### ✅ What Works in Local Mode

- **Full agent orchestration** - Planning, routing, execution
- **Memory & RAG** - Document ingestion and retrieval
- **All sales tools** - Territory, intelligence, engagement capabilities
- **Trace logging** - Full execution traces for debugging
- **Profile support** - enterprise/smb/technical profiles
- **File uploads** - Add documents to agent memory

### ❌ What's NOT in Local Mode

- **No React UI** - Uses Streamlit instead (simpler but less featured)
- **No WebSocket streaming** - Results appear when complete
- **No multi-user** - Single process, one user at a time
- **No horizontal scaling** - Not for production load

## When to Use Local Mode

### ✅ Good For:
- Solo developers learning the system
- Quick demos and prototypes
- Testing agent logic without infrastructure
- Rapid iteration on tools/prompts
- Running on a laptop without Docker/K8s

### ❌ Not Good For:
- Production deployments
- Team collaboration
- Multi-user access
- High-load scenarios
- Enterprise security requirements

## Architecture Comparison

### Local Mode (Simplified)
```
┌─────────────────────────────────┐
│   Streamlit Process             │
│                                 │
│   ┌─────────────────┐          │
│   │  Streamlit UI   │          │
│   └────────┬────────┘          │
│            │                    │
│   ┌────────▼────────┐          │
│   │  Coordinator    │          │
│   │  Planner        │          │
│   │  Workers        │          │
│   └─────────────────┘          │
└─────────────────────────────────┘
    One process, one port
```

### Production Mode (Full Stack)
```
┌──────────────┐      HTTP/WS      ┌──────────────┐
│   React UI   │◄─────────────────►│ FastAPI API  │
│  (Port 3000) │                    │  (Port 8000) │
└──────────────┘                    └──────┬───────┘
                                           │
                                    ┌──────▼───────┐
                                    │ Coordinator  │
                                    │ Planner      │
                                    │ Workers      ��
                                    └──────────────┘
    Two processes, two ports, network calls
```

## Commands Reference

### Launch Web UI
```bash
# Full command
uv run streamlit run src/cuga/local_ui.py

# Or via script
./scripts/start-local.sh

# Or via CLI
cuga local ui
```

### Interactive Chat
```bash
cuga local chat

# In chat:
You: Find sales leads in Chicago
Assistant: [executes and shows results]

You: /help      # Show commands
You: /clear     # Clear screen  
You: /exit      # Quit
```

### Run Demo
```bash
# Quick verification that everything works
cuga local demo
```

### Compare Modes
```bash
# See feature comparison table
cuga local compare

# Or via script
./scripts/compare-modes.sh
```

### Pure CLI (No UI)
```bash
# Plan only
cuga plan "Analyze territory coverage"

# Query memory
cuga query "product information" --top-k 5

# Ingest documents
cuga ingest docs/*.md
```

## Environment Setup

Local Mode uses the same `.env` file as Production Mode:

```bash
# Required: Choose one LLM provider
OPENAI_API_KEY=sk-...
# OR
WATSONX_API_KEY=...
WATSONX_PROJECT_ID=...

# Optional: Memory backend
VECTOR_BACKEND=local  # or chroma, qdrant, faiss
PROFILE=default       # or enterprise, smb, technical

# Not needed for local mode:
# AGENT_TOKEN (only for production API)
# CORS settings (no separate frontend)
```

## Troubleshooting

### "Streamlit not found"
```bash
uv pip install -e ".[local]"
```

### "Port already in use"
```bash
# Streamlit default port is 8501
# Kill existing process:
lsof -ti:8501 | xargs kill -9

# Or use custom port:
streamlit run src/cuga/local_ui.py --server.port 8502
```

### Memory not persisting
Local mode uses in-memory storage by default. To persist:

```python
# In local_ui.py, change:
backend_name="local"  # In-memory

# To:
backend_name="chroma"  # Persisted to disk
```

### Agent responses are slow
Check your LLM provider settings:

```bash
# Use faster model
export MODEL_NAME=gpt-3.5-turbo  # Instead of gpt-4

# Or use local model
export OPENAI_BASE_URL=http://localhost:11434/v1  # Ollama
```

## Migration Guide

### Switching to Production Mode

When you outgrow Local Mode:

```bash
# 1. Stop local mode (Ctrl+C)

# 2. Start production mode
./scripts/start-dev.sh

# 3. Access React UI
open http://localhost:3000
```

Your `.env`, memory, and configurations work in both modes!

### Using Both Modes

```bash
# Local mode for development (port 8501)
./scripts/start-local.sh &

# Production mode for testing (ports 3000 + 8000)
./scripts/start-dev.sh &

# Different profiles for each
PROFILE=dev cuga local ui          # Local with dev profile
PROFILE=staging ./scripts/start-dev.sh  # Production with staging
```

## FAQ

**Q: Is Local Mode production-ready?**  
A: No. Use Production Mode (FastAPI + React) for production deployments.

**Q: Can multiple people use Local Mode?**  
A: One user per process. For teams, use Production Mode.

**Q: Does Local Mode have all the features?**  
A: Core agent features yes, advanced UI features no (e.g., WebSocket streaming, real-time updates).

**Q: Which mode is faster?**  
A: Local Mode has less overhead (no HTTP), but Production Mode can scale horizontally.

**Q: Can I contribute to Local Mode?**  
A: Yes! See [CONTRIBUTING.md](../CONTRIBUTING.md). Local Mode lives in `src/cuga/local_ui.py` and `src/cuga/cli_local.py`.

**Q: Do I need Docker for Local Mode?**  
A: No. Local Mode runs directly on your machine with just Python dependencies.

**Q: Can I use Local Mode without a GPU?**  
A: Yes. Local Mode works fine on CPU-only machines.

## Performance Tips

### For Faster Startup
```bash
# Use local memory backend (no vector DB)
export VECTOR_BACKEND=local

# Skip heavy imports by using CLI mode
cuga local chat  # Lighter than Streamlit UI
```

### For Better Memory
```bash
# Use persistent vector store
export VECTOR_BACKEND=chroma

# Ingest documents once, reuse
cuga ingest docs/*.md
```

### For Development
```bash
# Enable hot reload
streamlit run src/cuga/local_ui.py --server.runOnSave true

# Disable watcher for stability
streamlit run src/cuga/local_ui.py --server.fileWatcherType none
```

## See Also

- [QUICK_START.md](../QUICK_START.md) - Production mode setup
- [AGENTS.md](../AGENTS.md) - Agent architecture and guardrails
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System design
- [CONTRIBUTING.md](../CONTRIBUTING.md) - Development guidelines
