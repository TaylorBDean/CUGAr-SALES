# Tool Registry Loader

`RegistryLoader` now parses registry files by extension to avoid masking YAML/JSON errors. YAML (`.yaml`/`.yml`) and JSON files are read with optional dependencies (`pyyaml`, `jsonschema`) detected via importlib and skipped when absent.

- When JSON Schema support is present, payloads are validated against the registry schema before constructing `RegistryServer` instances.
- Empty or malformed payloads default to an empty registry rather than raising during optional parsing, keeping offline tests deterministic.
- Ensure the file extension matches the content type; schema validation only runs when a payload is present.
- Validation emits structured audit logs (event + operation + outcome) and redacts payload values. A strict mode (`fail_on_validation_error=True`) can be passed to `RegistryLoader` to raise a sanitized `ValueError` when violations are detected.
