"""Watsonx provider with deterministic defaults and structured auditing."""

from __future__ import annotations

import importlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Type

_pydantic_spec = importlib.util.find_spec("pydantic")
if _pydantic_spec:
    pydantic = importlib.import_module("pydantic")
    BaseModel = pydantic.BaseModel
    ValidationError = pydantic.ValidationError
else:  # pragma: no cover - soft dependency fallback

    class BaseModel:  # type: ignore
        @classmethod
        def model_validate(cls, value: Any) -> Any:
            return value

        @classmethod
        def model_json_schema(cls) -> Dict[str, Any]:
            return {"properties": {}, "required": []}

    class ValidationError(Exception): ...


_watsonx_spec = importlib.util.find_spec("ibm_watsonx_ai")
if _watsonx_spec:
    _foundation_spec = importlib.util.find_spec("ibm_watsonx_ai.foundation_models")
    if _foundation_spec:
        Model = importlib.import_module("ibm_watsonx_ai.foundation_models").Model  # type: ignore
    else:  # pragma: no cover
        Model = None  # type: ignore
else:  # pragma: no cover - defensive import guard
    Model = None  # type: ignore

# Granite 4.0 default model (stable, deterministic)
# Available models: granite-4-h-small, granite-4-h-micro, granite-4-h-tiny
# See: https://www.ibm.com/docs/en/watsonx-as-a-service for model catalog
DEFAULT_MODEL = os.getenv("MODEL_NAME", "granite-4-h-small")
DEFAULT_CONFIG_PATH = Path(os.getenv("AGENT_SETTING_CONFIG", "settings.watsonx.toml"))


@dataclass
class WatsonxProvider:
    """Granite 4.0 provider with deterministic defaults and structured auditing.
    
    Granite 4.0 Models:
        - granite-4-h-small: Balanced performance (default)
        - granite-4-h-micro: Lightweight, fast inference
        - granite-4-h-tiny: Minimal resource usage
    
    Required Environment Variables:
        - WATSONX_API_KEY: IBM Cloud API key
        - WATSONX_PROJECT_ID: Watsonx project ID
        - WATSONX_URL: Watsonx API endpoint (optional, defaults to cloud)
    
    Deterministic Configuration:
        - temperature=0.0 (stable, reproducible outputs)
        - decoding_method="greedy" (deterministic token selection)
        - seed parameter available for full reproducibility
    """

    model_id: str = DEFAULT_MODEL
    decoding_method: str = "greedy"
    temperature: float = 0.0
    max_new_tokens: int = 256
    repetition_penalty: float = 1.0
    project_id: Optional[str] = field(default_factory=lambda: os.getenv("WATSONX_PROJECT_ID"))
    api_key: Optional[str] = field(default_factory=lambda: os.getenv("WATSONX_API_KEY"))
    url: Optional[str] = field(default_factory=lambda: os.getenv("WATSONX_URL"))
    audit_path: Path | str = field(default_factory=lambda: Path("logs/audit/model_calls.jsonl"))
    actor_id: str = "system"
    client: Any | None = None

    def __post_init__(self) -> None:
        self.max_new_tokens = min(max(self.max_new_tokens, 16), 2048)
        self.audit_path = Path(self.audit_path)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        self._validate_environment()

    def _validate_environment(self) -> None:
        """Validate required environment variables for Watsonx API access.
        
        Raises:
            RuntimeError: If required credentials are missing with helpful error message.
        """
        missing = []
        if not self.api_key:
            missing.append("WATSONX_API_KEY")
        if not self.project_id:
            missing.append("WATSONX_PROJECT_ID")
        
        if missing:
            raise RuntimeError(
                f"Missing required Watsonx credentials: {', '.join(missing)}. "
                f"Set these environment variables or pass them to WatsonxProvider constructor. "
                f"See docs/configuration/ENVIRONMENT_MODES.md for setup instructions."
            )

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "decoding_method": self.decoding_method,
            "temperature": self.temperature,
            "max_new_tokens": self.max_new_tokens,
            "repetition_penalty": self.repetition_penalty,
        }

    def _build_client(self) -> Any:
        if self.client is not None:
            return self.client
        if Model is None:
            raise RuntimeError("ibm-watsonx-ai is not installed")
        # Credentials validated in __post_init__
        return Model(
            model_id=self.model_id,
            params=self.parameters,
            credentials={"apikey": self.api_key},
            project_id=self.project_id,
            url=self.url,
        )

    def generate(self, prompt: str, *, seed: int | None = None) -> Dict[str, Any]:
        # Credentials validated in __post_init__
        payload = {
            "prompt": prompt,
            "model_id": self.model_id,
            "parameters": self.parameters,
            "seed": seed,
        }

        if self.client is None and Model is None:
            token_usage = {"input_tokens": len(prompt)}
            response: Dict[str, Any] = {
                "output_text": prompt,
                "usage": token_usage,
                "token_usage": token_usage,
            }
        else:
            client = self._build_client()
            response = client.generate_text(prompt=prompt, seed=seed)
            if "token_usage" not in response and "usage" in response:
                response["token_usage"] = response.get("usage")

        payload["token_usage"] = response.get("token_usage")
        return self._write_audit_and_return(payload, response)

    def function_call(
        self,
        functions: Iterable[Type[BaseModel]],
        prompt: str,
        *,
        fail_on_validation_error: bool = True,
    ) -> Dict[str, Any]:
        """Validate Watsonx function-call schemas before generation.

        Args:
            functions: Iterable of Pydantic models describing callable functions.
            prompt: Prompt to send to the model.
            fail_on_validation_error: When True (default), raise on validation issues
                before invoking the model. Set to False to return validation errors
                while still generating a response (legacy behavior).
        """

        errors: list[str] = []
        for fn_model in functions:
            try:
                schema = fn_model.model_json_schema()
                props = schema.get("properties", {})
                required = schema.get("required", [])
                if not isinstance(props, dict) or not props:
                    errors.append(f"Model {fn_model.__name__} has no properties.")
                if any(req not in props for req in required):
                    errors.append(f"Model {fn_model.__name__} has invalid required fields: {required}")
            except ValidationError as exc:  # pragma: no cover
                errors.append(f"Invalid Pydantic model {fn_model.__name__}: {exc}")
            except Exception as exc:  # pragma: no cover
                errors.append(f"Invalid Pydantic model {fn_model.__name__}: {exc}")

        if errors and fail_on_validation_error:
            raise ValueError("; ".join(errors))

        response = self.generate(prompt)
        return {"response": response, "validation": errors}

    def to_langchain(self) -> Any:
        """Return a lightweight adapter that mimics a LangChain LLM."""

        provider = self

        class _LCWrapper:
            def __call__(self, prompt: str, **_: Any) -> str:
                return provider.generate(prompt).get("output_text", "")

        return _LCWrapper()

    def _write_audit_and_return(self, payload: Dict[str, Any], response: Dict[str, Any]) -> Dict[str, Any]:
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "actor": self.actor_id or "system",
            "model_id": self.model_id,
            "parameters": self.parameters,
            "request": {"prompt": payload.get("prompt"), "seed": payload.get("seed")},
            "response_meta": {"token_usage": payload.get("token_usage")},
            "outcome": {"status": "success"},
        }
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")

        combined = dict(response)
        combined["audit"] = record
        return combined


__all__ = ["WatsonxProvider", "DEFAULT_MODEL", "DEFAULT_CONFIG_PATH"]
