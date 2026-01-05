
# 📦 Embedded Assets in CUGAR

This document outlines how CUGAR embeds static assets — such as the frontend and Chrome extension — directly into the Python backend, enabling portable deployments and reduced file complexity.

---

## 🎯 Why Embedded Assets?

CUGAR embeds:
- Frontend: `frontend-workspaces/frontend/dist`
- Chrome Extension: `frontend-workspaces/extension/releases/chrome-mv3`

✅ Benefits:
- Single-file deployment (no need to ship static files)
- 70%+ compression savings
- Faster server start (no file crawling)
- Works offline or in containerized environments

---

## 🚀 Build & Embed Assets

Run:

```bash
uv run scripts/build_embedded.py
```

This will:
1. Build frontend + extension
2. Compress them into `.zip`
3. Encode in base64
4. Inject into `cuga/backend/server/embedded_assets.py`

---

## ▶️ Run with Embedded Assets

```bash
export USE_EMBEDDED_ASSETS=true
uv run cuga/backend/server/main.py
```

Alternative inline:
```bash
USE_EMBEDDED_ASSETS=1 uv run cuga/backend/server/main.py
```

If disabled or missing:
- Falls back to file system mode automatically

---

## 🔧 Feature Flag

Controlled via the environment variable:

| Variable | Values |
|----------|--------|
| `USE_EMBEDDED_ASSETS` | `true`, `1`, `yes`, `on` (enabled)<br>`false`, `0`, `no`, `off` (disabled) |

Embedded mode is **off by default** for dev speed.

---

## 📁 File Structure

```
cuga/
├── backend/server/
│   ├── main.py
│   └── embedded_assets.py  # auto-generated
scripts/
├── embed_assets.py         # base64 embed logic
└── build_embedded.py       # full build + embed pipeline
```

---

## ⚙️ How It Works

1. **Assets are zipped**
2. **Zips are base64-encoded**
3. **Data embedded into a `.py` file**
4. **At runtime**, decoded to temp dir
5. **Server loads assets from temp path**

---

## 🛠️ Manual Usage

### Embed without Build
```bash
uv run scripts/embed_assets.py
```

### Build Only
```bash
cd frontend-workspaces
pnpm --filter "@carbon/ai-chat-examples-web-components-basic" run build
pnpm --filter extension run release
```

---

## 📊 Size Savings

| Component | Original | Compressed | Reduction |
|----------|----------|------------|-----------|
| Frontend | ~44 MB   | ~9.4 MB    | 78%       |
| Extension | ~12 MB  | ~7.7 MB    | 36%       |
| **Total** | ~56 MB  | ~17 MB     | **70%+**  |

---

## 🔍 Advanced Configuration

### Custom Extraction Path

```python
from cuga.backend.server import embedded_assets
embedded_assets.temp_dir = Path("/custom/path")
```

### Compression Level

Inside `scripts/embed_assets.py`:

```python
zipfile.ZipFile(..., compresslevel=9)
```

---

## 🧹 Cleanup

Assets auto-delete on shutdown.

For manual cleanup:

```python
from cuga.backend.server.embedded_assets import embedded_assets
embedded_assets.cleanup()
```

---

## 🐛 Troubleshooting

| Problem | Fix |
|--------|-----|
| **Assets not found** | Run: `uv run scripts/build_embedded.py` |
| **Extraction failed** | Check temp dir, disk space, permissions |
| **Memory usage too high** | Use file system mode in constrained environments |

---

## ⚖️ Tradeoffs

| Pro | Con |
|-----|-----|
| ✅ Portable deploy | ⚠️ Higher RAM usage |
| ✅ Smaller package | ⚠️ Longer build |
| ✅ No external files | ⚠️ Rebuild needed after changes |

---

## 🔄 Dev Workflow

```bash
# File system mode (dev)
USE_EMBEDDED_ASSETS=false

# Embedded mode (prod)
uv run scripts/build_embedded.py
USE_EMBEDDED_ASSETS=true uv run cuga/backend/server/main.py
```

---

## 📘 Related Docs

- `AGENTS.md` – project and environment routing
- `SECURITY.md` – environment variable protection
- `README.md` – top-level build instructions

---

🔁 Return to [Agents.md](../AGENTS.md)
