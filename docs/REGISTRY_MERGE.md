
# 🧩 Registry Merge Semantics

This document explains how agent **tool registries are assembled** from Hydra/OmegaConf YAML fragments using the merge logic in:

```
src/cuga/mcp_v2/registry/config_loader.py
src/cuga/mcp_v2/registry/loader.py
```

The new loader composes `config/registry.yaml` (and optional `server_fragments/`) with Hydra's `compose` API, then builds an immutable
`RegistrySnapshot`. Legacy fragment resolution via `mcp-foundation/scripts/merge_registry.py` remains for older profiles, but the
Hydra flow is the production path for MCP v2.

---

## 📁 Path Resolution

- Hydra composes configs starting from `config/registry.yaml` and any defaults it references (e.g., `server_fragments/local`).
- Defaults are resolved **relative to the config file**; `${oc.env:VAR,default}` expressions pull only from process environment.
- The loader returns the fully resolved registry path so downstream tooling can attribute sources in audit logs.

📌 This keeps builds **profile-portable** and lets optional fragments be skipped safely when absent.

---

## 🧱 Conflict Detection

- Duplicate server names **only fail** when the colliding servers are enabled after env evaluation. Disabled entries do not trip the detector.
- Errors include:
  - The **conflicting server name**
  - Both **source file paths**
- Tool validation now enforces string types for `operation_id`, `method`, and `path`, rejecting mixed/invalid types early.

---

## ✅ YAML Validation

All fragments are parsed by Hydra/OmegaConf. On failure:
- A `RegistryLoadError` is raised with the file name
- Parser context is preserved when available

**Examples of fatal YAML issues**:
- Tabs instead of spaces
- Trailing commas
- Misaligned keys

---

## 🧠 Langflow Templating

Profiles can declare templated Langflow projects like:

```toml
[profiles.trading.langflow_prod_projects]
analytics = "${LF_ANALYTICS_PROJECT_ID}"
trading = "${LF_TRADING_PROJECT_ID}"
```

During registry merge:
- Each mapping produces a `langflow_<project>` entry
- Entries include:
  - **Hardened API key checks**
  - Proxy-based invocation
  - Langflow config setup

🚨 Legacy `langflow_prod.yaml` fragments may co-exist temporarily, but should be **phased out** to remove deprecation warnings.

---

## 🔐 Environment Variable Hardening

- `enabled_env` gates can **override `enabled: false`** when the environment variable is present and truthy.
- `${oc.env:VAR,default}` interpolation applies during Hydra composition—no runtime shell expansion occurs.
- Keep secrets in env; registry YAML must stay free of tokens.

---

## 🛠️ Troubleshooting

| Problem | Resolution |
|--------|------------|
| **❌ Duplicate key error** | Remove or rename conflicting enabled servers. Disabled collisions are ignored by design. |
| **❌ Invalid YAML** | Fix indentation or structure. Look at the file path and error line in traceback. |
| **❌ Missing fragment** | Ensure defaults/fragments exist relative to `config/registry.yaml` or mark them `optional:`. |
| **❌ Tool validation error** | Verify `operation_id`, `method`, and `path` are strings and that one of (`operation_id`) or (`method` + `path`) is present. |

---

## 📘 Related Docs

- `AGENTS.md` – contributor onboarding + pipeline flow
- `TOOLS.md` – how tools are defined and registered
- `SECURITY.md` – safe secret handling in fragments

---

🔁 Return to [Agents.md](../AGENTS.md)
