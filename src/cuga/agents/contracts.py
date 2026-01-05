"""
Agent Input/Output Contracts

Defines canonical contracts for agent requests and responses, eliminating
inconsistent structures across different agent types.

All agents MUST accept AgentRequest and return AgentResponse to enable
clean routing and orchestration without special-casing.

Problem Solved:
- Agents accept different structures (implicit plans, varied metadata)
- No single contract for required inputs, optional metadata
- Inconsistent error vs success responses
- Prevents clean integration in routing/orchestration logic

Key Concepts:
    - AgentRequest: Canonical input structure (goal/task, metadata, context)
    - AgentResponse: Canonical output structure (success/error, result, trace)
    - AgentError: Structured error information
    - RequestMetadata: Standard metadata fields
    - ResponseStatus: Success/error/partial status enum
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Union
from datetime import datetime


class ResponseStatus(str, Enum):
    """Agent response status."""
    
    SUCCESS = "success"          # Task completed successfully
    ERROR = "error"              # Task failed unrecoverably
    PARTIAL = "partial"          # Task partially completed
    PENDING = "pending"          # Task pending (async/background)
    CANCELLED = "cancelled"      # Task cancelled by user/system


class ErrorType(str, Enum):
    """Agent error types."""
    
    VALIDATION = "validation"      # Input validation failed
    EXECUTION = "execution"        # Execution error
    TIMEOUT = "timeout"           # Task timeout
    RESOURCE = "resource"         # Resource unavailable
    PERMISSION = "permission"     # Permission denied
    NETWORK = "network"           # Network error
    UNKNOWN = "unknown"           # Unknown error


@dataclass(frozen=True)
class AgentError:
    """
    Structured error information.
    
    Attributes:
        type: Error type classification
        message: Human-readable error message
        details: Additional error details
        recoverable: Whether error is recoverable
        retry_after: Seconds to wait before retry (if applicable)
        trace_context: Error context for debugging
    """
    
    type: ErrorType
    message: str
    details: Optional[Dict[str, Any]] = None
    recoverable: bool = False
    retry_after: Optional[float] = None
    trace_context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "type": self.type.value,
            "message": self.message,
            "details": self.details or {},
            "recoverable": self.recoverable,
            "retry_after": self.retry_after,
            "trace_context": self.trace_context or {},
        }


@dataclass(frozen=True)
class RequestMetadata:
    """
    Standard metadata for agent requests.
    
    Attributes:
        trace_id: Unique trace identifier (propagated)
        profile: Execution profile
        priority: Request priority (0-10, higher = more urgent)
        timeout_seconds: Maximum execution time
        parent_context: Parent trace context (for nested calls)
        tags: Custom tags for filtering/routing
    """
    
    trace_id: str
    profile: str = "default"
    priority: int = 5
    timeout_seconds: Optional[float] = None
    parent_context: Optional[Dict[str, Any]] = None
    tags: Optional[Dict[str, str]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "trace_id": self.trace_id,
            "profile": self.profile,
            "priority": self.priority,
            "timeout_seconds": self.timeout_seconds,
            "parent_context": self.parent_context or {},
            "tags": self.tags or {},
        }


@dataclass
class AgentRequest:
    """
    Canonical agent input structure.
    
    All agents MUST accept this structure to enable clean routing and
    orchestration without special-casing.
    
    Required Fields:
        - goal: High-level objective (for planning agents)
        - task: Specific task description (for execution agents)
        - metadata: Standard metadata (trace_id, profile, etc.)
    
    Optional Fields:
        - inputs: Agent-specific input data
        - context: Additional context from previous steps
        - constraints: Execution constraints
        - expected_output: Expected output description
    
    Examples:
        >>> # Planning request
        >>> request = AgentRequest(
        ...     goal="Find cheap flights",
        ...     task="Search flights NY to LA",
        ...     metadata=RequestMetadata(trace_id="req-123"),
        ... )
        
        >>> # Execution request
        >>> request = AgentRequest(
        ...     goal="Execute plan",
        ...     task="Call flight search API",
        ...     metadata=RequestMetadata(trace_id="req-123"),
        ...     inputs={"origin": "NY", "destination": "LA"},
        ...     context={"previous_step": "api_selected"},
        ... )
    """
    
    # Required fields
    goal: str  # High-level objective
    task: str  # Specific task description
    metadata: RequestMetadata  # Standard metadata
    
    # Optional fields
    inputs: Optional[Dict[str, Any]] = None  # Agent-specific inputs
    context: Optional[Dict[str, Any]] = None  # Previous step context
    constraints: Optional[Dict[str, Any]] = None  # Execution constraints
    expected_output: Optional[str] = None  # Expected output description
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "goal": self.goal,
            "task": self.task,
            "metadata": self.metadata.to_dict(),
            "inputs": self.inputs or {},
            "context": self.context or {},
            "constraints": self.constraints or {},
            "expected_output": self.expected_output,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentRequest:
        """Create from dictionary representation."""
        metadata_dict = data.get("metadata", {})
        metadata = RequestMetadata(
            trace_id=metadata_dict.get("trace_id", "unknown"),
            profile=metadata_dict.get("profile", "default"),
            priority=metadata_dict.get("priority", 5),
            timeout_seconds=metadata_dict.get("timeout_seconds"),
            parent_context=metadata_dict.get("parent_context"),
            tags=metadata_dict.get("tags"),
        )
        
        return cls(
            goal=data.get("goal", ""),
            task=data.get("task", ""),
            metadata=metadata,
            inputs=data.get("inputs"),
            context=data.get("context"),
            constraints=data.get("constraints"),
            expected_output=data.get("expected_output"),
        )
    
    def validate(self) -> List[str]:
        """
        Validate request structure.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if not self.goal or not self.goal.strip():
            errors.append("goal is required and must not be empty")
        
        if not self.task or not self.task.strip():
            errors.append("task is required and must not be empty")
        
        if not self.metadata.trace_id:
            errors.append("metadata.trace_id is required")
        
        return errors


@dataclass
class AgentResponse:
    """
    Canonical agent output structure.
    
    All agents MUST return this structure to enable clean routing and
    orchestration without special-casing.
    
    Success Response:
        - status: ResponseStatus.SUCCESS
        - result: Agent output data
        - trace: Execution trace events
        - metadata: Response metadata
    
    Error Response:
        - status: ResponseStatus.ERROR
        - error: AgentError with details
        - trace: Partial execution trace
        - metadata: Response metadata
    
    Examples:
        >>> # Success response
        >>> response = AgentResponse(
        ...     status=ResponseStatus.SUCCESS,
        ...     result={"flights": [...]},
        ...     trace=[{"event": "api_called", "duration_ms": 150}],
        ...     metadata={"duration_ms": 200, "tool_count": 2},
        ... )
        
        >>> # Error response
        >>> response = AgentResponse(
        ...     status=ResponseStatus.ERROR,
        ...     error=AgentError(
        ...         type=ErrorType.TIMEOUT,
        ...         message="API call timeout",
        ...         recoverable=True,
        ...         retry_after=5.0,
        ...     ),
        ...     trace=[{"event": "api_timeout"}],
        ... )
    """
    
    # Required fields
    status: ResponseStatus
    
    # Optional fields (one of result or error required based on status)
    result: Optional[Any] = None  # Success result
    error: Optional[AgentError] = None  # Error details
    trace: List[Dict[str, Any]] = field(default_factory=list)  # Execution trace
    metadata: Dict[str, Any] = field(default_factory=dict)  # Response metadata
    
    # Timestamps
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "status": self.status.value,
            "result": self.result,
            "error": self.error.to_dict() if self.error else None,
            "trace": self.trace,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> AgentResponse:
        """Create from dictionary representation."""
        error_data = data.get("error")
        error = None
        if error_data:
            error = AgentError(
                type=ErrorType(error_data.get("type", "unknown")),
                message=error_data.get("message", ""),
                details=error_data.get("details"),
                recoverable=error_data.get("recoverable", False),
                retry_after=error_data.get("retry_after"),
                trace_context=error_data.get("trace_context"),
            )
        
        return cls(
            status=ResponseStatus(data.get("status", "error")),
            result=data.get("result"),
            error=error,
            trace=data.get("trace", []),
            metadata=data.get("metadata", {}),
            timestamp=data.get("timestamp", datetime.utcnow().isoformat()),
        )
    
    def validate(self) -> List[str]:
        """
        Validate response structure.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        if self.status == ResponseStatus.SUCCESS and self.result is None:
            errors.append("result is required for SUCCESS status")
        
        if self.status == ResponseStatus.ERROR and self.error is None:
            errors.append("error is required for ERROR status")
        
        return errors
    
    def is_success(self) -> bool:
        """Check if response indicates success."""
        return self.status == ResponseStatus.SUCCESS
    
    def is_error(self) -> bool:
        """Check if response indicates error."""
        return self.status == ResponseStatus.ERROR
    
    def is_recoverable(self) -> bool:
        """Check if error is recoverable."""
        return self.error is not None and self.error.recoverable


class AgentProtocol(Protocol):
    """
    Canonical protocol for agents with standardized I/O.
    
    All agents MUST implement this protocol to accept AgentRequest and
    return AgentResponse for clean routing/orchestration.
    
    Methods:
        process: Main entry point accepting AgentRequest, returning AgentResponse
    """
    
    async def process(self, request: AgentRequest) -> AgentResponse:
        """
        Process agent request and return response.
        
        Args:
            request: Canonical agent request
            
        Returns:
            Canonical agent response
            
        Raises:
            Should NOT raise - errors returned in AgentResponse.error
        """
        ...


# Convenience constructors

def success_response(
    result: Any,
    trace: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentResponse:
    """
    Create success response.
    
    Args:
        result: Agent result data
        trace: Execution trace events
        metadata: Response metadata
        
    Returns:
        AgentResponse with SUCCESS status
    """
    return AgentResponse(
        status=ResponseStatus.SUCCESS,
        result=result,
        trace=trace or [],
        metadata=metadata or {},
    )


def error_response(
    error_type: ErrorType,
    message: str,
    details: Optional[Dict[str, Any]] = None,
    recoverable: bool = False,
    retry_after: Optional[float] = None,
    trace: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentResponse:
    """
    Create error response.
    
    Args:
        error_type: Error type classification
        message: Human-readable error message
        details: Additional error details
        recoverable: Whether error is recoverable
        retry_after: Seconds to wait before retry
        trace: Partial execution trace
        metadata: Response metadata
        
    Returns:
        AgentResponse with ERROR status
    """
    error = AgentError(
        type=error_type,
        message=message,
        details=details,
        recoverable=recoverable,
        retry_after=retry_after,
    )
    
    return AgentResponse(
        status=ResponseStatus.ERROR,
        error=error,
        trace=trace or [],
        metadata=metadata or {},
    )


def partial_response(
    result: Any,
    remaining_work: str,
    trace: Optional[List[Dict[str, Any]]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AgentResponse:
    """
    Create partial response (task partially completed).
    
    Args:
        result: Partial result data
        remaining_work: Description of remaining work
        trace: Execution trace events
        metadata: Response metadata
        
    Returns:
        AgentResponse with PARTIAL status
    """
    return AgentResponse(
        status=ResponseStatus.PARTIAL,
        result=result,
        trace=trace or [],
        metadata=metadata or {"remaining_work": remaining_work},
    )


# Validation utilities

def validate_request(request: AgentRequest) -> None:
    """
    Validate agent request.
    
    Args:
        request: Agent request to validate
        
    Raises:
        ValueError: If request is invalid
    """
    errors = request.validate()
    if errors:
        raise ValueError(f"Invalid AgentRequest: {', '.join(errors)}")


def validate_response(response: AgentResponse) -> None:
    """
    Validate agent response.
    
    Args:
        response: Agent response to validate
        
    Raises:
        ValueError: If response is invalid
    """
    errors = response.validate()
    if errors:
        raise ValueError(f"Invalid AgentResponse: {', '.join(errors)}")
