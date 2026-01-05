"""Schema validation utilities for the tool registry.

Design: validation uses ``jsonschema`` errors as the single source of truth and
emits structured audit logs with sanitized fields (no payload echoes) so callers
can trace outcomes without leaking sensitive values.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any, Dict, List, Mapping, MutableMapping, Set

_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "servers": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "url"],
                "properties": {
                    "id": {"type": "string"},
                    "url": {"type": "string"},
                    "enabled": {"type": "boolean"},
                    "rate_limit_per_minute": {"type": "integer", "minimum": 1},
                },
            },
        }
    },
}

_AUDIT_OPERATION = "registry_schema_validation"
_AUDIT_RESERVED_EXTRA_KEYS = {"event", "operation", "outcome"}
_AUDIT_CONTEXT_ALLOWED_KEYS = {"actor", "correlation_id", "principal"}


class _SimpleError:
    def __init__(
        self,
        path: list[Any],
        schema_path: list[Any],
        validator: str,
        validator_value: Any,
        schema: Mapping[str, Any] | None = None,
    ) -> None:
        self.path = path
        self.schema_path = schema_path
        self.validator = validator
        self.validator_value = validator_value
        self.schema = schema or {}


class _LightweightValidator:
    """Fallback validator when ``jsonschema`` is unavailable.

    This only implements the subset of Draft7 needed for the registry schema so
    validation and audit logs remain consistent in offline environments.
    """

    def iter_errors(self, payload: Mapping[str, Any]):
        servers = payload.get("servers")
        if servers is None:
            return []
        if not isinstance(servers, list):
            return [
                _SimpleError(
                    ["servers"],
                    ["properties", "servers", "type"],
                    "type",
                    "array",
                    {"type": "array"},
                )
            ]

        errors: list[_SimpleError] = []
        for idx, item in enumerate(servers):
            if not isinstance(item, Mapping):
                errors.append(
                    _SimpleError(
                        ["servers", idx],
                        ["properties", "servers", "items", "type"],
                        "type",
                        "object",
                        {"type": "object"},
                    )
                )
                continue

            for field in ("id", "url"):
                if field not in item or item[field] is None:
                    errors.append(
                        _SimpleError(
                            ["servers", idx],
                            ["properties", "servers", "items", "required"],
                            "required",
                            ["id", "url"],
                            {"required": ["id", "url"]},
                        )
                    )
                    break
        return errors


def get_registry_validator() -> Any:
    if importlib.util.find_spec("jsonschema"):
        from jsonschema import Draft7Validator  # type: ignore

        return Draft7Validator(_SCHEMA)
    return _LightweightValidator()


def _build_audit_extra(
    event: str,
    *,
    outcome: str,
    audit_context: Mapping[str, Any] | None = None,
    details: Mapping[str, Any] | None = None,
    **details_kwargs: Any,
) -> Dict[str, Any]:
    extra: Dict[str, Any] = {"event": event, "operation": _AUDIT_OPERATION, "outcome": outcome}
    if audit_context:
        for key in _AUDIT_CONTEXT_ALLOWED_KEYS:
            value = audit_context.get(key)
            if value:
                extra[key] = value

    combined_details: Dict[str, Any] = {}
    if details:
        combined_details.update(details)
    if details_kwargs:
        combined_details.update(details_kwargs)

    filtered_details: Dict[str, Any] = {}
    if combined_details:
        filtered_details = {k: v for k, v in combined_details.items() if k not in _AUDIT_RESERVED_EXTRA_KEYS}

    if filtered_details:
        extra.update(filtered_details)
    return extra


def _sanitize_error(err: Any) -> MutableMapping[str, Any]:
    path = list(err.path)
    schema_path = list(err.schema_path)
    index = path[1] if len(path) >= 2 and path[0] == "servers" and isinstance(path[1], int) else None
    sanitized: MutableMapping[str, Any] = {
        "path": path,
        "schema_path": schema_path,
        "validator": err.validator,
        "constraint": err.validator_value,
    }
    if index is not None:
        sanitized["index"] = index
    if err.validator == "required" and isinstance(err.validator_value, list):
        sanitized["missing"] = sorted(err.validator_value)
    if err.validator == "type" and isinstance(err.schema, dict) and "type" in err.schema:
        sanitized["expected_type"] = err.schema["type"]
    return sanitized


def _invalid_indices_from_errors(errors: List[Any]) -> Set[int]:
    invalid: Set[int] = set()
    for err in errors:
        if err.path and err.path[0] == "servers" and len(err.path) >= 2 and isinstance(err.path[1], int):
            invalid.add(int(err.path[1]))
    return invalid


def validate_registry_payload(
    payload: Dict[str, Any],
    validator: Any,
    logger: logging.Logger | None = None,
    *,
    audit_context: Mapping[str, Any] | None = None,
    fail_on_validation_error: bool = False,
) -> List[Dict[str, Any]]:
    """Validate registry payload using Draft7 with defensive fallbacks.

    Validation errors are logged with audit metadata. Only structural diagnostics
    are emitted; payload values are never echoed.
    """

    logger = logger or logging.getLogger(__name__)
    audit_context = audit_context or {}
    validation_errors: List[Any] = []

    try:
        validation_errors = list(validator.iter_errors(payload))
    except Exception as exc:  # pragma: no cover - defensive guard
        logger.error(
            "registry_schema_validation_error",
            extra=_build_audit_extra(
                "registry_schema_validation_error",
                outcome="failure",
                audit_context=audit_context,
                error_type=type(exc).__name__,
            ),
        )
        if fail_on_validation_error:
            raise ValueError("Invalid registry schema") from None
        return []

    servers = payload.get("servers", [])
    if not isinstance(servers, list):
        logger.warning(
            "registry_schema_invalid",
            extra=_build_audit_extra(
                "registry_schema_invalid",
                outcome="failure",
                audit_context=audit_context,
                reason="servers_not_list",
            ),
        )
        if fail_on_validation_error:
            raise ValueError("Invalid registry schema") from None
        return []

    invalid_indices: Set[int] = _invalid_indices_from_errors(validation_errors)

    for err in validation_errors:
        sanitized = _sanitize_error(err)
        logger.warning(
            "registry_schema_violation",
            extra=_build_audit_extra(
                "registry_schema_violation",
                outcome="failure",
                audit_context=audit_context,
                **sanitized,
            ),
        )

    filtered: List[Dict[str, Any]] = []
    for idx, raw in enumerate(servers):
        if idx in invalid_indices:
            continue
        if isinstance(raw, dict):
            filtered.append(raw)

    outcome = "success"
    if validation_errors and filtered:
        outcome = "partial"
    elif validation_errors and not filtered:
        outcome = "failure"

    logger.info(
        "registry_schema_validation",
        extra=_build_audit_extra(
            "registry_schema_validation",
            outcome=outcome,
            audit_context=audit_context,
            accepted=len(filtered),
            rejected=len(servers) - len(filtered),
            total=len(servers),
        ),
    )

    if fail_on_validation_error and validation_errors:
        raise ValueError("Invalid registry schema") from None

    return filtered
