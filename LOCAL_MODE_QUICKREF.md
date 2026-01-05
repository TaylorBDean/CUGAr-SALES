# Local Mode Quick Reference

## 🚀 Quick Start

```bash
# Install dependencies
uv pip install -e ".[local]"

# Launch local mode
./scripts/start-local.sh
```

**That's it!** Browser opens to http://localhost:8501

---

## 📋 Command Reference

| Command | Description |
|---------|-------------|
| `./scripts/start-local.sh` | Launch web UI (recommended) |
| `cuga local ui` | Launch web UI (via CLI) |
| `cuga local chat` | Interactive terminal chat |
| `cuga local demo` | Quick verification test |
| `cuga local compare` | Show mode comparison |
| `./scripts/compare-modes.sh` | Visual mode comparison |

---

## 🎯 When to Use Local Mode

✅ **Use Local Mode For:**
- Solo development on your laptop
- Learning CUGAr architecture
- Quick demos to stakeholders
- Testing agent logic
- Rapid prototyping

❌ **Use Production Mode For:**
- Team collaboration
- Production deployments
- Enterprise environments
- Multi-user access
- Horizontal scaling

---

## 🔑 Key Features

| Feature | Local Mode | Production Mode |
|---------|-----------|-----------------|
| Processes | 1 | 2 |
| Ports | 8501 | 8000 + 3000 |
| UI | Streamlit | React |
| Setup | One command | Multi-step |
| CORS | Not needed | Required |
| WebSocket | Not needed | Full support |

---

## 💡 Tips

**Faster Startup:**
```bash
export VECTOR_BACKEND=local  # Skip vector DB
```

**Persistent Memory:**
```bash
export VECTOR_BACKEND=chroma  # Save to disk
```

**Different Profile:**
```bash
export PROFILE=enterprise  # or smb, technical
```

**Custom Port:**
```bash
streamlit run src/cuga/local_ui.py --server.port 8502
```

---

## 🔧 Troubleshooting

**"Streamlit not found"**
```bash
uv pip install -e ".[local]"
```

**"Port already in use"**
```bash
lsof -ti:8501 | xargs kill -9
```

**Agent responses slow**
```bash
export MODEL_NAME=gpt-3.5-turbo  # Faster model
```

---

## 📚 Documentation

- **Full Guide:** [docs/LOCAL_MODE.md](docs/LOCAL_MODE.md)
- **Production Setup:** [QUICK_START.md](QUICK_START.md)
- **Mode Comparison:** `cuga local compare`
- **Architecture:** [AGENTS.md](AGENTS.md)

---

## 🎬 Quick Demo

```bash
# 1. Install
uv pip install -e ".[local]"

# 2. Launch
./scripts/start-local.sh

# 3. Try a query in the UI:
"Find sales leads in Chicago"

# 4. Check execution trace
# Click "Execution Details" to see agent steps
```

---

## 🔄 Switching Modes

**From Local to Production:**
```bash
# Stop local mode (Ctrl+C)
# Start production mode
./scripts/start-dev.sh
```

**Your work carries over:**
- ✅ `.env` configuration
- ✅ Agent logic
- ✅ Memory data
- ✅ Profiles
- ✅ All settings

---

## ❓ FAQ

**Q: Is this production-ready?**  
A: No, use Production Mode for deployments.

**Q: Can multiple people use it?**  
A: No, one user per process.

**Q: Does it have all features?**  
A: Core agent features yes, advanced UI no.

**Q: Which is faster?**  
A: Local has less overhead, Production scales better.

---

## 🆘 Getting Help

1. Check [docs/LOCAL_MODE.md](docs/LOCAL_MODE.md)
2. Run `cuga local compare` to understand modes
3. See [AGENTS.md](AGENTS.md) for guardrails
4. File an issue on GitHub

---

**Made with ❤️ for solo developers who value simplicity**
