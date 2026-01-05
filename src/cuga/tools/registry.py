"""Tool registry with schema validation and extension-aware loading."""

from __future__ import annotations

import importlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, Iterable, List

from .models import RegistryServer
from .schema import get_registry_validator, validate_registry_payload


class RegistryLoader:
    def __init__(
        self,
        path: Path,
        *,
        logger: logging.Logger | None = None,
        audit_context: dict[str, str] | None = None,
        fail_on_validation_error: bool = False,
    ) -> None:
        self.path = path
        self.logger = logger or logging.getLogger(__name__)
        self.audit_context = audit_context or {}
        self.fail_on_validation_error = fail_on_validation_error

    def _load(self) -> List[RegistryServer]:
        payload: Dict[str, Any] = {}

        if self.path.exists():
            content = self.path.read_text(encoding="utf-8")
            suffix = self.path.suffix.lower()

            if suffix in (".yaml", ".yml"):
                yaml_spec = importlib.util.find_spec("yaml")
                if yaml_spec:
                    yaml = importlib.import_module("yaml")
                    payload = yaml.safe_load(content) or {}
                else:
                    payload = self._fallback_yaml_load(content)
            elif suffix == ".json":
                try:
                    payload = json.loads(content) or {}
                except json.JSONDecodeError:  # pragma: no cover
                    payload = {}

        validator = get_registry_validator()
        servers_payload = validate_registry_payload(
            payload,
            validator,
            logger=self.logger,
            audit_context=self.audit_context,
            fail_on_validation_error=self.fail_on_validation_error,
        )

        servers: List[RegistryServer] = []
        for raw in servers_payload:
            servers.append(
                RegistryServer(
                    id=raw["id"],
                    url=raw["url"],
                    enabled=raw.get("enabled", True),
                    rate_limit_per_minute=raw.get("rate_limit_per_minute", 60),
                )
            )
        return servers

    @staticmethod
    def _fallback_yaml_load(content: str) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        current_key: str | None = None
        items: list[Dict[str, Any]] = []
        current_item: Dict[str, Any] = {}

        for line in content.splitlines():
            if not line.strip():
                continue
            if not line.startswith(" "):
                if current_item:
                    items.append(current_item)
                    current_item = {}
                key, _, value = line.partition(":")
                if value.strip():
                    payload[key.strip()] = value.strip()
                else:
                    current_key = key.strip()
            else:
                stripped = line.strip()
                if stripped.startswith("-"):
                    if current_item:
                        items.append(current_item)
                    current_item = {}
                    stripped = stripped.lstrip("-").strip()
                    if stripped:
                        k, _, v = stripped.partition(":")
                        current_item[k.strip()] = v.strip()
                else:
                    k, _, v = stripped.partition(":")
                    current_item[k.strip()] = v.strip()

        if current_item:
            items.append(current_item)
        if current_key and items:
            payload[current_key] = items
        return payload


class ToolRegistry:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.data = RegistryLoader(self.path)._load()

    def enabled(self) -> Iterable[RegistryServer]:
        return [s for s in self.data if s.enabled]


__all__ = ["RegistryLoader", "ToolRegistry", "RegistryServer"]
