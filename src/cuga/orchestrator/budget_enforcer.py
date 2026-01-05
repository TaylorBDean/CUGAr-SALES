"""
Tool budget enforcement per AGENTS.md PlannerAgent requirements.
Implements deterministic budget tracking and canonical event emission.
"""
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)


@dataclass
class ToolBudget:
    """
    Budget constraints per AGENTS.md budget requirements.
    
    Per AGENTS.md:
    - PlannerAgent MUST attach a ToolBudget to every plan
    - Budgets track total_calls, calls_per_domain, calls_per_tool
    - Budget warnings/exceeded are canonical trace events
    """
    total_calls: int = 100
    calls_per_domain: Dict[str, int] = field(default_factory=dict)
    calls_per_tool: Dict[str, int] = field(default_factory=dict)
    
    # Warning thresholds (percentage)
    warning_threshold: float = 0.8  # Warn at 80%
    
    def __post_init__(self):
        """Validate budget constraints."""
        if self.total_calls <= 0:
            raise ValueError("total_calls must be positive")
        if self.warning_threshold <= 0 or self.warning_threshold >= 1:
            raise ValueError("warning_threshold must be between 0 and 1")


class BudgetEnforcer:
    """
    Enforces tool budgets per AGENTS.md PlannerAgent requirements.
    
    Per AGENTS.md:
    - Deterministic budget tracking
    - Canonical event emission (budget_warning, budget_exceeded)
    - Graceful degradation when budget exhausted
    """
    
    def __init__(self, budget: ToolBudget, trace_emitter=None):
        """
        Initialize budget enforcer.
        
        Args:
            budget: ToolBudget constraints
            trace_emitter: Optional TraceEmitter for canonical events
        """
        self.budget = budget
        self.trace_emitter = trace_emitter
        self.usage = {
            "total": 0,
            "by_domain": {},
            "by_tool": {}
        }
        self._warnings_emitted = set()
    
    def check_budget(
        self, 
        tool_name: str, 
        domain: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if tool call is within budget.
        
        Per AGENTS.md:
        - Returns (allowed, reason)
        - Emits budget_warning at threshold
        - Emits budget_exceeded when limit reached
        
        Args:
            tool_name: Name of tool to check
            domain: Domain of tool (from registry metadata)
        
        Returns:
            (allowed, reason): Tuple of (bool, Optional[str])
                - (True, None) if within budget
                - (False, reason) if budget exceeded
        """
        # Check total budget
        if self.usage["total"] >= self.budget.total_calls:
            self._emit_budget_event(
                "budget_exceeded",
                {"budget_type": "total", "limit": self.budget.total_calls}
            )
            return False, "budget_exceeded:total"
        
        # Check domain budget
        domain_limit = self.budget.calls_per_domain.get(domain)
        if domain_limit:
            domain_usage = self.usage["by_domain"].get(domain, 0)
            if domain_usage >= domain_limit:
                self._emit_budget_event(
                    "budget_exceeded",
                    {"budget_type": "domain", "domain": domain, "limit": domain_limit}
                )
                return False, f"budget_exceeded:domain:{domain}"
        
        # Check tool budget
        tool_limit = self.budget.calls_per_tool.get(tool_name)
        if tool_limit:
            tool_usage = self.usage["by_tool"].get(tool_name, 0)
            if tool_usage >= tool_limit:
                self._emit_budget_event(
                    "budget_exceeded",
                    {"budget_type": "tool", "tool": tool_name, "limit": tool_limit}
                )
                return False, f"budget_exceeded:tool:{tool_name}"
        
        # Check for warnings
        self._check_warnings(tool_name, domain)
        
        return True, None
    
    def record_usage(self, tool_name: str, domain: str) -> None:
        """
        Record tool usage against budget.
        
        Per AGENTS.md:
        - Deterministic usage tracking
        - Supports partial-result recovery
        """
        self.usage["total"] += 1
        self.usage["by_domain"][domain] = self.usage["by_domain"].get(domain, 0) + 1
        self.usage["by_tool"][tool_name] = self.usage["by_tool"].get(tool_name, 0) + 1
        
        logger.debug(
            f"Budget usage recorded: {tool_name} (domain: {domain})",
            extra={"total": self.usage["total"], "limit": self.budget.total_calls}
        )
    
    def get_utilization(self) -> Dict[str, Any]:
        """
        Return budget utilization for UI display.
        
        Returns format matching frontend BudgetIndicator expectations.
        """
        return {
            "total": {
                "used": self.usage["total"],
                "limit": self.budget.total_calls,
                "percentage": (self.usage["total"] / self.budget.total_calls) * 100
            },
            "by_domain": {
                domain: {
                    "used": self.usage["by_domain"].get(domain, 0),
                    "limit": limit,
                    "percentage": (self.usage["by_domain"].get(domain, 0) / limit) * 100
                }
                for domain, limit in self.budget.calls_per_domain.items()
            }
        }
    
    def _check_warnings(self, tool_name: str, domain: str) -> None:
        """Emit budget_warning canonical events at threshold."""
        # Check total budget warning (including current call)
        total_pct = (self.usage["total"] + 1) / self.budget.total_calls
        
        if total_pct >= self.budget.warning_threshold:
            warning_key = f"total:{self.budget.total_calls}"
            if warning_key not in self._warnings_emitted:
                self._emit_budget_event(
                    "budget_warning",
                    {"budget_type": "total", "utilization": total_pct}
                )
                self._warnings_emitted.add(warning_key)
    
    def _emit_budget_event(self, event: str, details: Dict[str, Any]) -> None:
        """Emit canonical budget event if trace_emitter available."""
        if self.trace_emitter:
            self.trace_emitter.emit(event, details, status="warning")
