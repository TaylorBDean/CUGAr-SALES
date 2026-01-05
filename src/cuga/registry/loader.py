from __future__ import annotations

import copy
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List

try:
    import yaml
except Exception:
    yaml = None

from cuga.observability import InMemoryTracer

ALLOWED_SANDBOXES = {"py-slim", "py-full", "node-slim", "node-full", "orchestrator"}
DEFAULT_BUDGET_POLICY = "warn"
REQUIRED_ENV_DEFAULTS = {
    "AGENT_BUDGET_CEILING": "${AGENT_BUDGET_CEILING:-100}",
    "AGENT_ESCALATION_MAX": "${AGENT_ESCALATION_MAX:-2}",
    "AGENT_BUDGET_POLICY": "${AGENT_BUDGET_POLICY:-warn}",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "${OTEL_EXPORTER_OTLP_ENDPOINT:-}",
    "OTEL_SERVICE_NAME": "${OTEL_SERVICE_NAME:-cuga}",
    "LANGFUSE_PUBLIC_KEY": "${LANGFUSE_PUBLIC_KEY:-}",
    "LANGFUSE_SECRET_KEY": "${LANGFUSE_SECRET_KEY:-}",
    "TRACELOOP_API_KEY": "${TRACELOOP_API_KEY:-}",
}


@dataclass(order=True)
class RegistryEntry:
    sort_index: tuple = field(init=False, repr=False)
    id: str
    ref: str
    sandbox: str
    enabled: bool = True
    tier: int = 1
    env: Dict[str, Any] = field(default_factory=dict)
    mounts: List[str] = field(default_factory=list)
    scopes: List[str] = field(default_factory=list)
    budget_policy: str = DEFAULT_BUDGET_POLICY

    def __post_init__(self) -> None:
        self.sort_index = (self.tier, self.id)


class Registry:
    def __init__(self, path: Path, tracer: InMemoryTracer | None = None) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self.tracer = tracer or InMemoryTracer()
        self._entries = self._load(self.path.read_text())

    @staticmethod
    def _load(content: str) -> List[RegistryEntry]:
        data = _safe_load(content)
        defaults = data.get("defaults", {})
        entries: List[RegistryEntry] = []
        for raw in data.get("entries", []):
            merged = _merge_with_defaults(copy.deepcopy(defaults), raw)
            if merged.get("tier") == 2 and "enabled" not in raw:
                merged["enabled"] = False
            _validate_entry(merged)
            entry = RegistryEntry(
                id=merged["id"],
                ref=merged["ref"],
                sandbox=merged.get("sandbox", "py-slim"),
                enabled=merged.get("enabled", True),
                tier=merged.get("tier", 1),
                env=merged.get("env", {}),
                mounts=merged.get("mounts", []),
                scopes=merged.get("scopes", []),
                budget_policy=merged.get("budget_policy", DEFAULT_BUDGET_POLICY),
            )
            entries.append(entry)
        return sorted(entries)

    @property
    def entries(self) -> List[RegistryEntry]:
        with self._lock:
            return list(self._entries)

    def hot_reload(self, content: str) -> None:
        new_entries = self._load(content)
        with self._lock:
            self._entries = new_entries
            self.tracer.start_span("registry.reload", trace_id="hot-reload").end(count=len(new_entries))

    def get_enabled(self) -> List[RegistryEntry]:
        return [e for e in self.entries if e.enabled]

    def pick(self, scope: str) -> Iterable[RegistryEntry]:
        for entry in self.get_enabled():
            if scope in entry.scopes:
                yield entry


def _safe_load(content: str) -> Dict[str, Any]:
    if yaml:
        return yaml.safe_load(content) or {}
    try:
        from omegaconf import OmegaConf

        return OmegaConf.to_container(OmegaConf.create(content), resolve=True) or {}
    except Exception:
        pass
    return _fallback_yaml_parse(content)


def _fallback_yaml_parse(content: str) -> Dict[str, Any]:
    tokens: List[tuple[int, str]] = []
    for raw_line in content.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        tokens.append((indent, raw_line.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        result: Dict[str, Any] = {}
        sequence: List[Any] | None = None
        i = index
        while i < len(tokens):
            current_indent, text = tokens[i]
            if current_indent < indent:
                break
            if text.startswith("- "):
                if sequence is None:
                    sequence = []
                item, i = parse_sequence_item(i, current_indent)
                sequence.append(item)
                continue
            if ":" not in text:
                i += 1
                continue
            key, raw_val = text.split(":", 1)
            key = key.strip()
            val = raw_val.strip()
            if not val:
                child, i = parse_block(i + 1, current_indent + 2)
                result[key] = child
            else:
                result[key] = _coerce_scalar(val)
                i += 1
        return (sequence if sequence is not None else result), i

    def parse_sequence_item(index: int, indent: int) -> tuple[Any, int]:
        current_indent, text = tokens[index]
        assert text.startswith("- ")
        body = text[2:].strip()
        item_indent = current_indent + 2
        i = index + 1
        if not body:
            value, i = parse_block(i, item_indent)
            return value, i
        if ":" in body:
            key, raw_val = body.split(":", 1)
            key = key.strip()
            val = raw_val.strip()
            mapping: Dict[str, Any] = {}
            if val:
                mapping[key] = _coerce_scalar(val)
            else:
                child, i = parse_block(i, item_indent)
                mapping[key] = child
            while i < len(tokens):
                next_indent, next_text = tokens[i]
                if next_indent < item_indent or (
                    next_text.startswith("- ") and next_indent == current_indent
                ):
                    break
                if ":" not in next_text:
                    i += 1
                    continue
                sub_key, sub_raw_val = next_text.split(":", 1)
                sub_key = sub_key.strip()
                sub_val = sub_raw_val.strip()
                if not sub_val:
                    child, i = parse_block(i + 1, next_indent + 2)
                    mapping[sub_key] = child
                else:
                    mapping[sub_key] = _coerce_scalar(sub_val)
                    i += 1
            return mapping, i
        return _coerce_scalar(body), i

    parsed, _ = parse_block(0, 0)
    if not isinstance(parsed, dict):
        return {}
    parsed.setdefault("defaults", {"tier": 1, "enabled": True})
    parsed.setdefault("entries", [])
    return parsed


def _coerce_scalar(value: str) -> Any:
    if value.startswith("{") and value.endswith("}"):
        mapping: Dict[str, Any] = {}
        inner = value.strip("{} ")
        for part in inner.split(","):
            if not part.strip() or ":" not in part:
                continue
            key, val = part.split(":", 1)
            mapping[key.strip()] = _coerce_scalar(val.strip())
        return mapping
    if value.startswith("[") and value.endswith("]"):
        return [_coerce_scalar(v.strip()) for v in value.strip("[] ").split(",") if v.strip()]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    if value.isdigit():
        return int(value)
    try:
        return float(value)
    except ValueError:
        return value


def _merge_with_defaults(defaults: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    merged = copy.deepcopy(defaults)
    merged.update(raw)
    merged["env"] = {**REQUIRED_ENV_DEFAULTS, **defaults.get("env", {}), **raw.get("env", {})}
    merged["mounts"] = raw.get("mounts", defaults.get("mounts", [])) or []
    merged["scopes"] = raw.get("scopes", defaults.get("scopes", [])) or []
    merged.setdefault("budget_policy", defaults.get("budget_policy", DEFAULT_BUDGET_POLICY))
    merged.setdefault("sandbox", defaults.get("sandbox", "py-slim"))
    merged.setdefault("tier", defaults.get("tier", 1))
    merged.setdefault("enabled", defaults.get("enabled", True))
    return merged


def _validate_entry(entry: Dict[str, Any]) -> None:
    sandbox = entry.get("sandbox")
    if sandbox not in ALLOWED_SANDBOXES:
        raise ValueError(f"Unsupported sandbox profile: {sandbox}")
    budget_policy = entry.get("budget_policy", DEFAULT_BUDGET_POLICY)
    if budget_policy not in {"warn", "block"}:
        raise ValueError(f"Invalid budget policy: {budget_policy}")
    scopes = entry.get("scopes", []) or []
    mounts = entry.get("mounts", []) or []
    if "exec" in scopes and not any(mount.startswith("/workdir") for mount in mounts):
        raise ValueError("Exec sandboxes must pin /workdir mounts")
    entry["mounts"] = list(dict.fromkeys(mounts))
