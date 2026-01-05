# Langflow Components

CUGA guard components now target Langflow >= 1.7 using the `lfx.*` import surface. Each guard component declares a unique `component_type` and `display_name` to avoid registration collisions:

- `guard_input` → **CUGA Input Guard**
- `guard_tool` → **CUGA Tool Guard**
- `guard_output` → **CUGA Output Guard**
- `guard_orchestrator` → **CUGA Guard Orchestrator**

Components remain importable without Langflow installed thanks to lightweight stubs; optional dependencies are discovered via `importlib.util.find_spec` rather than hard imports. Outputs are simple `Data` payloads that keep CLI and demo flows deterministic and offline-safe.
