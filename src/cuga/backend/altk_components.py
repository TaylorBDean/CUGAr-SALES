"""Integration wrappers for Agent Lifecycle Toolkit (ALTK).

This module exposes lightweight adapters that allow the core agent pipeline
to opt into ALTK processing without taking a hard dependency on any specific
component at call sites. Each wrapper performs defensive error handling so
that the main flow continues even if a lifecycle stage fails.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Dict, Iterable, List, Optional

from loguru import logger

try:
    from altk.post_tool.silent_review import SilentReviewForJSONDataComponent
    from altk.pre_llm.spotlight import SpotlightComponent
    from altk.pre_response.policy_guard import PolicyGuardComponent
    from altk.pre_tool.refraction import RefractionComponent
except Exception as exc:  # pragma: no cover - optional dependency
    logger.warning("Agent Lifecycle Toolkit components unavailable: {}", exc)
    SilentReviewForJSONDataComponent = None  # type: ignore
    SpotlightComponent = None  # type: ignore
    PolicyGuardComponent = None  # type: ignore
    RefractionComponent = None  # type: ignore


class PromptEnhancer:
    """Wrapper around ALTK Spotlight for pre-LLM prompt improvement."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (SpotlightComponent() if SpotlightComponent else None)

    def run(self, prompt: str) -> str:
        if not self.component:
            return prompt
        try:
            return self.component.process(prompt)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Spotlight enhancement failed: {}", exc)
            return prompt


class ToolCallValidator:
    """Wrapper around ALTK Refraction for tool call validation/correction."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (RefractionComponent() if RefractionComponent else None)

    def run(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        if not self.component:
            return tool_call
        try:
            processed = self.component.process(tool_call)
            return processed if isinstance(processed, dict) else tool_call
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Refraction validation failed: {}", exc)
            return tool_call


def _coerce_to_dicts(payload: Any) -> List[Dict[str, Any]]:
    """Best-effort conversion of mixed tool call payloads into dictionaries."""

    if payload is None:
        return []

    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            logger.warning("Unable to parse tool call string payload; skipping invalid data")
            return []

    if dataclasses.is_dataclass(payload):
        payload = dataclasses.asdict(payload)

    if isinstance(payload, dict):
        return [dict(payload)]

    if hasattr(payload, "model_dump"):
        return [payload.model_dump()]  # type: ignore[no-any-return]

    if hasattr(payload, "dict"):
        return [payload.dict()]  # type: ignore[no-any-return]

    if isinstance(payload, list):
        collected: List[Dict[str, Any]] = []
        for item in payload:
            collected.extend(_coerce_to_dicts(item))
        return collected

    if isinstance(payload, Iterable) and not isinstance(payload, (bytes, str)):
        collected: List[Dict[str, Any]] = []
        for item in payload:
            collected.extend(_coerce_to_dicts(item))
        return collected

    if hasattr(payload, "__dict__"):
        return [dict(payload.__dict__)]

    logger.warning("Unsupported tool call payload type: {}", type(payload))
    return []


def normalize_tool_calls(tool_calls: Optional[Iterable[Any]]) -> Optional[List[Dict[str, Any]]]:
    """Normalize tool calls to a list of dictionaries with safe defaults."""

    if tool_calls is None:
        return None

    normalized: List[Dict[str, Any]] = []
    for idx, call_dict in enumerate(_coerce_to_dicts(tool_calls)):
        sanitized = dict(call_dict)
        sanitized.setdefault("id", str(idx))
        sanitized.setdefault("type", sanitized.get("type", "function") or "function")

        function_payload: Any = sanitized.get("function", {})
        if dataclasses.is_dataclass(function_payload):
            function_payload = dataclasses.asdict(function_payload)
        if hasattr(function_payload, "model_dump"):
            function_payload = function_payload.model_dump()  # type: ignore[assignment]
        if hasattr(function_payload, "dict"):
            function_payload = function_payload.dict()  # type: ignore[assignment]

        if not isinstance(function_payload, dict):
            function_payload = {"name": str(function_payload)} if function_payload is not None else {}

        function_payload.setdefault("arguments", function_payload.get("args", {}))
        sanitized["function"] = function_payload
        normalized.append(sanitized)

    return normalized


class ToolOutputReviewer:
    """Wrapper around ALTK Silent Review for post-tool JSON validation."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (
            SilentReviewForJSONDataComponent() if SilentReviewForJSONDataComponent else None
        )

    def run(self, output: Any) -> Dict[str, Any]:
        """Review tool output and return a structured assessment.

        Returns a dictionary so callers can decide whether to retry or attach
        the feedback to the agent state.
        """

        default_response = {"needs_retry": False, "details": None}
        if not self.component:
            return default_response
        try:
            review = self.component.process(output)
            if isinstance(review, dict):
                return {"needs_retry": review.get("retry", False), "details": review}
            return default_response
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("Silent review failed: {}", exc)
            return default_response


class PolicyGuardEnforcer:
    """Wrapper around ALTK PolicyGuard for pre-response enforcement."""

    def __init__(self, component: Optional[Any] = None) -> None:
        self.component = component or (PolicyGuardComponent() if PolicyGuardComponent else None)

    def run(self, response: str) -> str:
        if not self.component:
            return response
        try:
            return self.component.process(response)
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.warning("PolicyGuard enforcement failed: {}", exc)
            return response


class ALTKLifecycleManager:
    """Coordinator for ALTK components across the agent pipeline."""

    def __init__(
        self,
        prompt_enhancer: Optional[PromptEnhancer] = None,
        tool_validator: Optional[ToolCallValidator] = None,
        tool_reviewer: Optional[ToolOutputReviewer] = None,
        policy_guard: Optional[PolicyGuardEnforcer] = None,
        enabled: bool = False,
    ) -> None:
        self.enabled = enabled
        if not enabled:
            self.prompt_enhancer = None
            self.tool_validator = None
            self.tool_reviewer = None
            self.policy_guard = None
            return

        self.prompt_enhancer = prompt_enhancer or PromptEnhancer()
        self.tool_validator = tool_validator or ToolCallValidator()
        self.tool_reviewer = tool_reviewer or ToolOutputReviewer()
        self.policy_guard = policy_guard or PolicyGuardEnforcer()

    def enhance_state_prompt(self, state: Any) -> Any:
        if not (self.enabled and self.prompt_enhancer):
            return state
        already_enhanced = getattr(state, "_enhanced_prompt_applied", False)
        if already_enhanced:
            return state

        if hasattr(state, "input") and state.input:
            original = state.input
            state.input = self.prompt_enhancer.run(str(state.input))
            logger.debug("Spotlight enhanced input from {} to {}", original, state.input)
        if hasattr(state, "goal") and getattr(state, "goal", None):
            original = state.goal
            state.goal = self.prompt_enhancer.run(str(state.goal))
            logger.debug("Spotlight enhanced goal from {} to {}", original, state.goal)

        setattr(state, "_enhanced_prompt_applied", True)
        return state

    def validate_tool_calls(self, tool_calls: Optional[Iterable[Any]]) -> Optional[List[Dict[str, Any]]]:
        normalized_calls = normalize_tool_calls(tool_calls)
        if not (self.enabled and self.tool_validator and normalized_calls):
            return normalized_calls
        validated: List[Dict[str, Any]] = []
        for call in normalized_calls:
            validated.append(self.tool_validator.run(call))
        return validated

    def review_tool_outputs(self, output: Any) -> Optional[Dict[str, Any]]:
        if not (self.enabled and self.tool_reviewer):
            return None
        return self.tool_reviewer.run(output)

    def enforce_policy(self, response: Optional[str]) -> Optional[str]:
        if not (self.enabled and self.policy_guard and response):
            return response
        return self.policy_guard.run(response)

    @classmethod
    def from_settings(cls, enabled: bool) -> "ALTKLifecycleManager":
        return cls(enabled=enabled)
