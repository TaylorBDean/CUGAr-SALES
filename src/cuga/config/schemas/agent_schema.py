"""Agent configuration schema."""

from typing import Optional, Literal
from pydantic import BaseModel, Field, field_validator


class AgentLLMConfig(BaseModel):
    """LLM configuration for agent."""
    
    provider: Literal["watsonx", "openai", "anthropic", "azure", "groq", "ollama"]
    model: str = Field(..., min_length=1)
    temperature: float = Field(0.0, ge=0.0, le=2.0, description="Sampling temperature (0.0 = deterministic)")
    max_tokens: int = Field(8192, ge=1, le=128000, description="Max tokens to generate")
    top_p: Optional[float] = Field(None, ge=0.0, le=1.0, description="Nucleus sampling threshold")
    api_key: Optional[str] = Field(None, description="API key (should come from env)")
    
    @field_validator("api_key")
    @classmethod
    def warn_about_hardcoded_key(cls, v: Optional[str]) -> Optional[str]:
        """Warn if API key hardcoded (security risk)."""
        if v and not v.startswith("${"):
            import warnings
            warnings.warn(
                "API key appears hardcoded in config. Use environment variable instead "
                "(e.g., api_key: ${OPENAI_API_KEY})",
                UserWarning
            )
        return v
    
    @field_validator("temperature")
    @classmethod
    def validate_deterministic_default(cls, v: float, info) -> float:
        """Validate temperature follows deterministic-first philosophy."""
        provider = info.data.get("provider")
        if provider == "watsonx" and v > 0.0:
            import warnings
            warnings.warn(
                f"Temperature {v} > 0.0 for watsonx provider. "
                f"AGENTS.md recommends temperature=0.0 for deterministic behavior.",
                UserWarning
            )
        return v
    
    model_config = {"extra": "forbid"}


class AgentConfig(BaseModel):
    """Agent configuration with lifecycle and execution settings."""
    
    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: Literal["planner", "worker", "coordinator"] = Field(..., description="Agent role type")
    llm: AgentLLMConfig
    max_retries: int = Field(3, ge=0, le=10, description="Max retry attempts on failure")
    timeout_seconds: int = Field(300, ge=1, le=3600, description="Execution timeout")
    memory_enabled: bool = Field(True, description="Enable vector memory for this agent")
    profile: str = Field("default", description="Security/execution profile")
    
    @field_validator("name")
    @classmethod
    def validate_name_convention(cls, v: str) -> str:
        """Validate agent name follows snake_case convention."""
        if v.startswith("_"):
            raise ValueError("Agent name cannot start with underscore")
        if len(v) < 3:
            raise ValueError("Agent name must be at least 3 characters")
        return v
    
    @field_validator("timeout_seconds")
    @classmethod
    def validate_reasonable_timeout(cls, v: int) -> int:
        """Warn about unreasonably short/long timeouts."""
        if v < 30:
            import warnings
            warnings.warn(
                f"Timeout {v}s is very short. Most agent operations need >30s.",
                UserWarning
            )
        return v
    
    model_config = {"extra": "forbid"}


class MemoryConfig(BaseModel):
    """Memory system configuration."""
    
    backend: Literal["local", "faiss", "chroma", "qdrant"] = "local"
    profile: str = "default"
    embedder: Literal["hashing", "openai", "watsonx"] = "hashing"
    retention_days: Optional[int] = Field(None, ge=1, description="Delete entries older than N days")
    max_entries_per_profile: Optional[int] = Field(None, ge=100, description="Max entries per profile")
    
    model_config = {"extra": "forbid"}


class ObservabilityConfig(BaseModel):
    """Observability and tracing configuration."""
    
    enabled: bool = True
    emitter: Literal["base", "langfuse", "openinference", "otel"] = "base"
    trace_sampling_rate: float = Field(1.0, ge=0.0, le=1.0, description="Fraction of traces to sample")
    redact_secrets: bool = Field(True, description="Redact secret/token/password keys")
    
    model_config = {"extra": "forbid"}
