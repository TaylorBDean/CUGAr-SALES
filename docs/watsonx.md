# Watsonx Provider Notes

CUGA ships a lightweight watsonx provider tuned for deterministic defaults. Calls default to `ibm/granite-3-3-8b-instruct` with greedy decoding, zero temperature, and bounded token limits. Credentials are validated before any SDK interaction; missing `WATSONX_API_KEY`, `WATSONX_PROJECT_ID`, or `WATSONX_URL` now surface a clear runtime error instead of opaque SDK failures.

## Audit trail
- Every generation writes JSONL to `logs/audit/model_calls.jsonl` (path overridable per provider) with ISO-8601 UTC timestamps.
- Fields include actor (defaults to `system`), model id, parameters, prompt/seed preview, token usage, and an explicit `outcome.status`.
- Audit logging is offline-safe and runs even when the SDK is not installed; responses are echoed for deterministic tests.

## Validation helpers
- `function_call` inspects Pydantic v2 `model_json_schema()` without instantiation, flagging missing properties or mismatched required fields.
- Validation errors are returned alongside the model response to keep CLI and Langflow demos stable without network calls.
