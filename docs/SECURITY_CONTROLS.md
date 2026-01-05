# Security Controls (ASVS snapshot)

- **Input validation (ASVS 5.x)**: Guardrail placeholders added via `src/cuga/guards/input_guard.py` with routing in `routing/guards.yaml`.
- **Output handling (ASVS 7.x)**: Output guard stub captures length metadata; future encoding and redaction to be wired.
- **API/Service controls (ASVS 14.x)**: Tool registry schema validation added in `src/cuga/tools/registry.py` with rate-limit fields.
- **Config & secrets (ASVS 5/13)**: Watsonx provider reads env vars (`WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, `WATSONX_URL`, `AGENT_SETTING_CONFIG`) and clamps deterministic parameters by default.
