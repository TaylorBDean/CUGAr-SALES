"""Langflow Watsonx LLM component wiring the provider."""

from __future__ import annotations

from typing import Any, Dict

try:
    from langflow.custom import custom_component
    from langflow.custom.custom_component.component import Component
except Exception:  # pragma: no cover
    Component = object  # type: ignore
    custom_component = lambda *args, **kwargs: (lambda cls: cls)

from cuga.providers.watsonx_provider import WatsonxProvider


@custom_component(component_type="llm", description="Watsonx Granite provider")
class WatsonxLLMComponent(Component):
    display_name = "Watsonx Granite"
    description = "Deterministic Granite calls with audit trail"

    def build_config(self) -> Dict[str, Any]:  # pragma: no cover - UI metadata
        return {
            "prompt": {"type": "str", "required": True},
            "model_id": {"type": "str", "required": False},
            "seed": {"type": "int", "required": False},
        }

    def __call__(self, prompt: str, model_id: str | None = None, seed: int | None = None) -> Dict[str, Any]:
        provider = WatsonxProvider(model_id=model_id or WatsonxProvider().model_id)
        result = provider.generate(prompt, seed=seed)
        return {"text": result.get("output_text", ""), "usage": result.get("usage", {})}
