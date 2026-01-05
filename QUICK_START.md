<div align="center">
  <img src="docs/image/CUGAr.png" alt="CUGAr Logo" width="500"/>
</div>

# 🚀 Cugar Agent - Quick Start Guide

Welcome to Cugar Agent! This guide will get you up and running in minutes.

## 📋 Table of Contents

- [Immediate Onboarding](#immediate-onboarding)
- [5-Minute Setup](#5-minute-setup)
- [Configuration Guide](#configuration-guide)
- [Essential Commands](#essential-commands)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

---

## Immediate Onboarding

### What is Cugar Agent?

Cugar Agent is a security-first, offline-capable agentic orchestration framework with:
- **Multi-agent orchestration**: Planner, Worker, and Coordinator agents with LangGraph integration
- **MCP tool integration**: Model Context Protocol servers for extensible tool execution
- **Unified configuration**: Single source of truth with explicit precedence and validation
- **Memory & RAG**: Vector embeddings with Chroma/FAISS for context-aware responses
- **Enterprise observability**: OpenTelemetry, LangFuse, and LangSmith integration

### Prerequisites

Before you begin, ensure you have:

- **Python** 3.11+ (required for tomllib support)
- **Git** installed
- A terminal/command line interface
- API keys for LLM providers (watsonx.ai, OpenAI, Anthropic, Azure, Groq, or Ollama)

### Key Resources

- 📖 [Full Documentation](./docs)
- 🏗️ [Architecture Guide](./ARCHITECTURE.md)
- � [Configuration Reference](./docs/configuration/CONFIG_RESOLUTION.md)
- 🔐 [Security Controls](./docs/SECURITY_CONTROLS.md)
- �🐛 [Report Issues](https://github.com/TylrDn/cugar-agent/issues)
- 💬 [Discussions & Support](https://github.com/TylrDn/cugar-agent/discussions)
- 📝 [Changelog](./CHANGELOG.md)

---

## 5-Minute Setup

### Step 1: Clone the Repository (1 min)

```bash
git clone https://github.com/TylrDn/cugar-agent.git
cd cugar-agent
```

### Step 2: Install Dependencies (2 min)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Or install in development mode
pip install -e .

# Verify installation
python -c "import cuga; print(f'✅ Cugar Agent {cuga.__version__} installed')"
```

### Step 3: Configuration (1 min)

```bash
# Copy the example environment file
cp .env.example .env

# Set your LLM provider API key (choose one)
nano .env  # Add one of:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# WATSONX_API_KEY=...
# AZURE_OPENAI_API_KEY=...
```

**Minimum required configuration:**
```bash
# .env
OPENAI_API_KEY=sk-your-api-key-here
CUGA_PROFILE=demo_power
```

### Step 4: Verify Installation (1 min)

```bash
# Run a simple query
python -m cuga.main "List files in the current directory"

# Or use the CLI
cuga-agent query "What is the weather today?"

# Check configuration
cuga-agent config show
```

✅ **You're ready to go!**

---

## Configuration Guide

### Configuration Structure

Cugar Agent uses a unified configuration system with explicit precedence:

```
config/
├── registry.yaml          # Tool registry (canonical)
├── guards.yaml            # Routing guards
└── defaults/
    ├── models/*.yaml      # Model configurations
    └── backend.yaml       # Backend settings

configs/
├── agent.demo.yaml        # Agent configurations
├── memory.yaml            # Memory configurations
└── observability.yaml     # Observability configurations

.env                       # Environment overrides (highest precedence)
```

### Configuration Precedence

Values are resolved in this order (highest to lowest):

1. **CLI Arguments** (`--profile production`)
2. **Environment Variables** (`PROFILE=production`)
3. **.env Files** (`.env` > `.env.mcp` > `.env.example`)
4. **YAML Configs** (`configs/*.yaml`, `config/registry.yaml`)
5. **TOML Configs** (`settings.toml`, `eval_config.toml`)
6. **Configuration Defaults** (`config/defaults/*.yaml`)
7. **Hardcoded Defaults** (in source code)

### Example: Using ConfigResolver

```python
from cuga.config import ConfigResolver, YAMLSource, EnvSource

# Create resolver
resolver = ConfigResolver()
resolver.add_source(EnvSource(prefixes=["CUGA_", "AGENT_"]))
resolver.add_source(YAMLSource("config/registry.yaml"))
resolver.resolve()

# Get value with provenance
model = resolver.get("llm.model")
print(model)  # ConfigValue(value="granite-4-h-small", layer=ENV, ...)

# Validate all configuration
errors = resolver.validate_all(fail_fast=True)  # Raises on first error
```

### Migrating Scattered Configs

If you have existing configuration files, use the migration script:

```bash
# Preview changes (dry-run mode)
python scripts/migrate_config.py --dry-run

# Apply migration with backups
python scripts/migrate_config.py

# Restore from backup if needed
cp -r backups/config_backup_YYYYMMDD_HHMMSS/* .
```

See [Configuration Resolution Guide](./docs/configuration/CONFIG_RESOLUTION.md) for complete documentation.

---

## Essential Commands

### Basic Operations

```bash
# Run agent with a query
cuga-agent query "Analyze this codebase"

# Start web UI (if installed)
cuga-agent serve --port 8000

# Check system health
cuga-agent health

# View current configuration
cuga-agent config show

# Validate configuration
cuga-agent config validate
```

### Development Commands

```bash
# Run in development mode with debug logging
DEBUG=cuga:* python -m cuga.main "your query"

# Run tests
pytest tests/ -v

# Run tests with coverage
pytest tests/ --cov=src/cuga --cov-report=html

# Lint code
ruff check src/

# Format code
ruff format src/

# Type check
mypy src/cuga/
```

### Configuration & Debugging

```bash
# Show configuration with provenance
python -c "
from cuga.config import ConfigResolver, YAMLSource
resolver = ConfigResolver()
resolver.add_source(YAMLSource('config/registry.yaml'))
resolver.resolve()
print(resolver.dump())
"

# Validate tool registry
python -c "
from cuga.config import ConfigValidator
import yaml
with open('config/registry.yaml') as f:
    ConfigValidator.validate_registry(yaml.safe_load(f))
print('✅ Registry valid')
"

# Enable trace logging
export CUGA_LOG_LEVEL=DEBUG
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318

# View recent logs
tail -f logs/cuga.log
```

---

## Common Workflows

### Workflow 1: Running Your First Query

```bash
# 1. Ensure configuration is set
cat .env | grep API_KEY

# 2. Run a simple query
python -m cuga.main "List all Python files in this directory"

# 3. Check the response and trace logs
cat logs/cuga.log | tail -20

# 4. Try a more complex query
python -m cuga.main "Analyze the architecture of this project"
```

### Workflow 2: Adding Custom Tools

```bash
# 1. Create a new tool module
mkdir -p src/cuga/modular/tools/my_tools
touch src/cuga/modular/tools/my_tools/__init__.py
touch src/cuga/modular/tools/my_tools/custom_tool.py

# 2. Implement your tool (follow allowlist: cuga.modular.tools.*)
cat > src/cuga/modular/tools/my_tools/custom_tool.py << 'EOF'
def my_tool_handler(inputs: dict, context: dict) -> dict:
    """Custom tool implementation."""
    return {"result": "success", "data": inputs}
EOF

# 3. Register in config/registry.yaml
cat >> config/registry.yaml << 'EOF'
tools:
  my_custom_tool:
    module: "cuga.modular.tools.my_tools.custom_tool"
    handler: "my_tool_handler"
    description: "My custom tool for doing X"
    sandbox_profile: "py_slim"
    mounts:
      - "/workdir:/workdir:ro"
EOF

# 4. Validate registry
python scripts/migrate_config.py --dry-run

# 5. Test your tool
python -c "
from cuga.modular.tools.my_tools.custom_tool import my_tool_handler
result = my_tool_handler({'test': 'data'}, {'profile': 'demo'})
print(result)
"
```

### Workflow 3: Setting Up Memory & RAG

```bash
# 1. Configure memory backend in configs/memory.yaml
cat > configs/memory.yaml << 'EOF'
backend: faiss
embedding_model: all-MiniLM-L6-v2
retention_days: 30
persist_directory: ./memory/embeddings
EOF

# 2. Initialize memory store
python -c "
from cuga.memory import VectorMemory
memory = VectorMemory.from_config('configs/memory.yaml')
memory.initialize()
print('✅ Memory initialized')
"

# 3. Add documents to memory
python -c "
from cuga.memory import VectorMemory
memory = VectorMemory.from_config('configs/memory.yaml')
memory.add_documents([
    {'content': 'Key fact 1', 'metadata': {'source': 'docs'}},
    {'content': 'Key fact 2', 'metadata': {'source': 'docs'}},
])
print('✅ Documents added')
"

# 4. Query with memory context
python -m cuga.main --memory-enabled "What are the key facts?"
```

### Workflow 4: Debugging Configuration Issues

```bash
# 1. Check configuration precedence
python -c "
from cuga.config import ConfigResolver, EnvSource, YAMLSource
resolver = ConfigResolver()
resolver.add_source(EnvSource())
resolver.add_source(YAMLSource('configs/agent.demo.yaml'))
resolver.resolve()

# Show where each value came from
for key in ['llm.model', 'llm.temperature', 'agent.timeout']:
    print(resolver.get_provenance(key))
"

# 2. Validate all configuration
python -c "
from cuga.config import ConfigResolver, YAMLSource
resolver = ConfigResolver()
resolver.add_source(YAMLSource('config/registry.yaml'))
resolver.resolve()

errors = resolver.validate_all(fail_fast=False)
if errors:
    for section, error_list in errors.items():
        print(f'❌ {section}: {error_list}')
else:
    print('✅ All configuration valid')
"

# 3. Check for common issues
python scripts/verify_guardrails.py --base main

# 4. Review audit logs
grep "CONFIG" logs/cuga.log | tail -50
```

# 5. Check logs for specific module
DEBUG=cugar-agent:database cugar-agent start
```

### Workflow 4: Updating & Upgrading

```bash
# Check for updates
cugar-agent update --check

# Update to latest version
npm update cugar-agent  # or pip install --upgrade cugar-agent

# Update dependencies
npm update  # or pip install --upgrade -r requirements.txt

# Verify upgrade
cugar-agent --version
```

### Workflow 5: Deploying to Production

```bash
# 1. Build the project
npm run build  # or python setup.py build

# 2. Run tests
npm test  # or pytest

# 3. Create environment file
cp .env.example .env.production

# 4. Configure for production
# Edit .env.production with production settings

# 5. Start with production config
NODE_ENV=production npm start

# 6. Verify deployment
curl https://your-production-url/health
```

---

## Troubleshooting

### Common Issues & Solutions

#### ❌ **Issue: "Module not found" error**

**Solution:**
```bash
# Reinstall dependencies
rm -rf node_modules package-lock.json
npm install

# Or for Python
pip install --force-reinstall -r requirements.txt
```

#### ❌ **Issue: Port already in use**

**Solution:**
```bash
# Find what's using the port (replace 3000 with your port)
lsof -i :3000  # macOS/Linux
netstat -ano | findstr :3000  # Windows

# Kill the process or change port in .env
PORT=3001 cugar-agent start
```

#### ❌ **Issue: Environment variables not loading**

**Solution:**
```bash
# Verify .env file exists
ls -la .env

# Check file is readable
cat .env

# Ensure correct format (KEY=VALUE)
# Try with explicit path
source .env && cugar-agent start  # Linux/macOS
```

#### ❌ **Issue: Configuration validation fails**

**Solution:**
```bash
# Validate configuration
cugar-agent config validate

# Check required environment variables
cugar-agent config show --required

# Review example configuration
cat .env.example

# Compare your config with example
diff .env .env.example
```

#### ❌ **Issue: Connection/Network errors**

**Solution:**
```bash
# Test connectivity
ping your-service-url

# Check firewall settings
sudo ufw status  # Linux

# Verify API endpoints
cugar-agent health-check --verbose

# Test with verbose logging
DEBUG=cugar-agent:* cugar-agent start --verbose
```

#### ❌ **Issue: Agent crashes on startup**

**Solution:**
```bash
# 1. Check logs for errors
cugar-agent logs --all

# 2. Verify all required services are running
cugar-agent status --all

# 3. Clear cache and restart
rm -rf .cache
cugar-agent start

# 4. Reset to default config (backup first!)
cp .env .env.backup
cp .env.example .env
cugar-agent start
```

#### ❌ **Issue: Tests failing locally**

**Solution:**
```bash
# Clear test cache
npm test -- --clearCache  # or pytest --cache-clear

# Run tests with verbose output
npm test -- --verbose  # or pytest -v

# Run specific test file
npm test -- src/__tests__/specific.test.js

# Check test environment setup
cat .env.test
```

### Getting More Help

- **Check logs:** `cugar-agent logs --tail 100`
- **Enable debug mode:** `DEBUG=cugar-agent:* cugar-agent start`
- **Review documentation:** See `/docs` folder
- **Search issues:** https://github.com/TylrDn/cugar-agent/issues
- **Ask in discussions:** https://github.com/TylrDn/cugar-agent/discussions
- **Report bugs:** Create a new issue with:
  - Your OS and Node/Python version
  - Steps to reproduce
  - Full error logs
  - Configuration (without secrets)

---

## Next Steps

1. ✅ Complete the 5-Minute Setup above
2. 📖 Read the [full documentation](./docs)
3. 🔧 Explore the [examples](./examples) folder
4. 🚀 Try a [common workflow](#common-workflows)
5. 💡 Check out [best practices](./docs/BEST_PRACTICES.md)

---

## Quick Links

| Resource | Link |
|----------|------|
| GitHub Repository | https://github.com/TylrDn/cugar-agent |
| Documentation | [./docs](./docs) |
| Examples | [./examples](./examples) |
| Issues | https://github.com/TylrDn/cugar-agent/issues |
| Discussions | https://github.com/TylrDn/cugar-agent/discussions |
| License | [./LICENSE](./LICENSE) |

---

**Happy coding! 🎉 If you have feedback on this guide, please [let us know](https://github.com/TylrDn/cugar-agent/discussions).**
