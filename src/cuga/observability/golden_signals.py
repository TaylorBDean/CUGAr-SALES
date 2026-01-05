"""
Golden Signals Tracking for CUGAR Agent System

Tracks and computes the four golden signals plus agent-specific metrics:
1. Success Rate: % of successful executions
2. Latency: Tool execution and end-to-end latency percentiles
3. Traffic: Request rate and throughput
4. Errors: Tool error rate and error distribution

Agent-specific signals:
- Mean steps per task
- Tool error rate by tool
- Approval wait time (p50, p95, p99)
- Budget utilization

All metrics are computed from structured events and exportable to Prometheus/OTEL.
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import statistics


@dataclass
class LatencyHistogram:
    """Track latency percentiles with rolling window."""
    
    samples: List[float] = field(default_factory=list)
    max_samples: int = 1000
    
    def add(self, value: float) -> None:
        """Add latency sample."""
        self.samples.append(value)
        if len(self.samples) > self.max_samples:
            self.samples.pop(0)
    
    def percentile(self, p: float) -> float:
        """Calculate percentile (0-100)."""
        if not self.samples:
            return 0.0
        return statistics.quantiles(self.samples, n=100)[int(p) - 1] if len(self.samples) > 1 else self.samples[0]
    
    def mean(self) -> float:
        """Calculate mean latency."""
        return statistics.mean(self.samples) if self.samples else 0.0
    
    def clear(self) -> None:
        """Clear all samples."""
        self.samples.clear()


@dataclass
class Counter:
    """Simple counter with reset capability."""
    
    value: int = 0
    
    def increment(self, delta: int = 1) -> None:
        """Increment counter."""
        self.value += delta
    
    def get(self) -> int:
        """Get current value."""
        return self.value
    
    def reset(self) -> int:
        """Reset and return previous value."""
        prev = self.value
        self.value = 0
        return prev


@dataclass
class GoldenSignals:
    """
    Track golden signals and agent-specific metrics.
    
    Metrics are computed from structured events and exportable
    to Prometheus, OTEL, Grafana, etc.
    """
    
    # Success rate tracking
    total_requests: Counter = field(default_factory=Counter)
    successful_requests: Counter = field(default_factory=Counter)
    failed_requests: Counter = field(default_factory=Counter)
    
    # Latency tracking
    end_to_end_latency: LatencyHistogram = field(default_factory=LatencyHistogram)
    tool_latency: Dict[str, LatencyHistogram] = field(default_factory=lambda: defaultdict(LatencyHistogram))
    planning_latency: LatencyHistogram = field(default_factory=LatencyHistogram)
    routing_latency: LatencyHistogram = field(default_factory=LatencyHistogram)
    
    # Steps tracking
    steps_per_task: List[int] = field(default_factory=list)
    max_steps_samples: int = 1000
    
    # Tool error tracking
    tool_calls: Counter = field(default_factory=Counter)
    tool_errors: Counter = field(default_factory=Counter)
    tool_errors_by_tool: Dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    tool_errors_by_type: Dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    
    # Approval tracking
    approval_requests: Counter = field(default_factory=Counter)
    approval_wait_times: LatencyHistogram = field(default_factory=LatencyHistogram)
    approval_timeouts: Counter = field(default_factory=Counter)
    
    # Budget tracking
    budget_warnings: Counter = field(default_factory=Counter)
    budget_exceeded: Counter = field(default_factory=Counter)
    budget_utilization: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    
    # Traffic tracking
    requests_by_profile: Dict[str, Counter] = field(default_factory=lambda: defaultdict(Counter))
    
    # Timestamp for rate calculation
    _start_time: float = field(default_factory=time.time)
    
    def record_request_start(self, profile: str = "default") -> None:
        """Record request start."""
        self.total_requests.increment()
        self.requests_by_profile[profile].increment()
    
    def record_request_success(self, duration_ms: float) -> None:
        """Record successful request completion."""
        self.successful_requests.increment()
        self.end_to_end_latency.add(duration_ms)
    
    def record_request_failure(self, duration_ms: float) -> None:
        """Record failed request."""
        self.failed_requests.increment()
        self.end_to_end_latency.add(duration_ms)
    
    def record_plan_created(self, steps_count: int, duration_ms: float) -> None:
        """Record plan creation."""
        self.planning_latency.add(duration_ms)
        self.steps_per_task.append(steps_count)
        if len(self.steps_per_task) > self.max_steps_samples:
            self.steps_per_task.pop(0)
    
    def record_route_decision(self, duration_ms: float) -> None:
        """Record routing decision."""
        self.routing_latency.add(duration_ms)
    
    def record_tool_call_start(self, tool_name: str) -> None:
        """Record tool call start."""
        self.tool_calls.increment()
    
    def record_tool_call_complete(self, tool_name: str, duration_ms: float) -> None:
        """Record tool call completion."""
        self.tool_latency[tool_name].add(duration_ms)
    
    def record_tool_call_error(
        self,
        tool_name: str,
        error_type: str,
        duration_ms: float,
    ) -> None:
        """Record tool call error."""
        self.tool_errors.increment()
        self.tool_errors_by_tool[tool_name].increment()
        self.tool_errors_by_type[error_type].increment()
        self.tool_latency[tool_name].add(duration_ms)
    
    def record_approval_requested(self) -> None:
        """Record approval request."""
        self.approval_requests.increment()
    
    def record_approval_received(self, wait_time_ms: float) -> None:
        """Record approval decision."""
        self.approval_wait_times.add(wait_time_ms)
    
    def record_approval_timeout(self) -> None:
        """Record approval timeout."""
        self.approval_timeouts.increment()
    
    def record_budget_warning(self, budget_type: str, utilization_pct: float) -> None:
        """Record budget warning."""
        self.budget_warnings.increment()
        self.budget_utilization[budget_type].append(utilization_pct)
    
    def record_budget_exceeded(self, budget_type: str, utilization_pct: float) -> None:
        """Record budget exceeded."""
        self.budget_exceeded.increment()
        self.budget_utilization[budget_type].append(utilization_pct)
    
    def success_rate(self) -> float:
        """Calculate success rate (0-100)."""
        total = self.total_requests.get()
        if total == 0:
            return 0.0
        return (self.successful_requests.get() / total) * 100
    
    def error_rate(self) -> float:
        """Calculate error rate (0-100)."""
        total = self.total_requests.get()
        if total == 0:
            return 0.0
        return (self.failed_requests.get() / total) * 100
    
    def tool_error_rate(self) -> float:
        """Calculate tool error rate (0-100)."""
        total_calls = self.tool_calls.get()
        if total_calls == 0:
            return 0.0
        return (self.tool_errors.get() / total_calls) * 100
    
    def mean_steps_per_task(self) -> float:
        """Calculate mean steps per task."""
        if not self.steps_per_task:
            return 0.0
        return statistics.mean(self.steps_per_task)
    
    def requests_per_second(self) -> float:
        """Calculate requests per second since start."""
        elapsed = time.time() - self._start_time
        if elapsed == 0:
            return 0.0
        return self.total_requests.get() / elapsed
    
    def to_prometheus_format(self) -> str:
        """
        Export metrics in Prometheus text format.
        
        Returns:
            Prometheus-compatible metric export
        """
        lines = [
            "# HELP cuga_requests_total Total number of requests",
            "# TYPE cuga_requests_total counter",
            f"cuga_requests_total {self.total_requests.get()}",
            "",
            "# HELP cuga_requests_success_total Successful requests",
            "# TYPE cuga_requests_success_total counter",
            f"cuga_requests_success_total {self.successful_requests.get()}",
            "",
            "# HELP cuga_requests_failed_total Failed requests",
            "# TYPE cuga_requests_failed_total counter",
            f"cuga_requests_failed_total {self.failed_requests.get()}",
            "",
            "# HELP cuga_success_rate Request success rate percentage",
            "# TYPE cuga_success_rate gauge",
            f"cuga_success_rate {self.success_rate():.2f}",
            "",
            "# HELP cuga_latency_ms End-to-end latency in milliseconds",
            "# TYPE cuga_latency_ms summary",
            f'cuga_latency_ms{{quantile="0.5"}} {self.end_to_end_latency.percentile(50):.2f}',
            f'cuga_latency_ms{{quantile="0.95"}} {self.end_to_end_latency.percentile(95):.2f}',
            f'cuga_latency_ms{{quantile="0.99"}} {self.end_to_end_latency.percentile(99):.2f}',
            f"cuga_latency_ms_sum {sum(self.end_to_end_latency.samples):.2f}",
            f"cuga_latency_ms_count {len(self.end_to_end_latency.samples)}",
            "",
            "# HELP cuga_steps_per_task Mean steps per task",
            "# TYPE cuga_steps_per_task gauge",
            f"cuga_steps_per_task {self.mean_steps_per_task():.2f}",
            "",
            "# HELP cuga_tool_calls_total Total tool calls",
            "# TYPE cuga_tool_calls_total counter",
            f"cuga_tool_calls_total {self.tool_calls.get()}",
            "",
            "# HELP cuga_tool_errors_total Total tool errors",
            "# TYPE cuga_tool_errors_total counter",
            f"cuga_tool_errors_total {self.tool_errors.get()}",
            "",
            "# HELP cuga_tool_error_rate Tool error rate percentage",
            "# TYPE cuga_tool_error_rate gauge",
            f"cuga_tool_error_rate {self.tool_error_rate():.2f}",
            "",
            "# HELP cuga_approval_requests_total Approval requests",
            "# TYPE cuga_approval_requests_total counter",
            f"cuga_approval_requests_total {self.approval_requests.get()}",
            "",
            "# HELP cuga_approval_wait_ms Approval wait time in milliseconds",
            "# TYPE cuga_approval_wait_ms summary",
            f'cuga_approval_wait_ms{{quantile="0.5"}} {self.approval_wait_times.percentile(50):.2f}',
            f'cuga_approval_wait_ms{{quantile="0.95"}} {self.approval_wait_times.percentile(95):.2f}',
            f'cuga_approval_wait_ms{{quantile="0.99"}} {self.approval_wait_times.percentile(99):.2f}',
            "",
            "# HELP cuga_budget_warnings_total Budget warnings",
            "# TYPE cuga_budget_warnings_total counter",
            f"cuga_budget_warnings_total {self.budget_warnings.get()}",
            "",
            "# HELP cuga_budget_exceeded_total Budget exceeded events",
            "# TYPE cuga_budget_exceeded_total counter",
            f"cuga_budget_exceeded_total {self.budget_exceeded.get()}",
            "",
        ]
        
        # Per-tool metrics
        for tool_name, hist in self.tool_latency.items():
            lines.extend([
                f"# HELP cuga_tool_latency_ms_{tool_name} Latency for {tool_name}",
                f"# TYPE cuga_tool_latency_ms_{tool_name} summary",
                f'cuga_tool_latency_ms_{tool_name}{{quantile="0.5"}} {hist.percentile(50):.2f}',
                f'cuga_tool_latency_ms_{tool_name}{{quantile="0.95"}} {hist.percentile(95):.2f}',
                "",
            ])
        
        return "\n".join(lines)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Export metrics as dictionary for JSON/OTEL export.
        
        Returns:
            Dictionary with all metric values
        """
        return {
            "success_rate": self.success_rate(),
            "error_rate": self.error_rate(),
            "tool_error_rate": self.tool_error_rate(),
            "mean_steps_per_task": self.mean_steps_per_task(),
            "requests_per_second": self.requests_per_second(),
            "total_requests": self.total_requests.get(),
            "successful_requests": self.successful_requests.get(),
            "failed_requests": self.failed_requests.get(),
            "tool_calls": self.tool_calls.get(),
            "tool_errors": self.tool_errors.get(),
            "latency": {
                "end_to_end": {
                    "p50": self.end_to_end_latency.percentile(50),
                    "p95": self.end_to_end_latency.percentile(95),
                    "p99": self.end_to_end_latency.percentile(99),
                    "mean": self.end_to_end_latency.mean(),
                },
                "planning": {
                    "p50": self.planning_latency.percentile(50),
                    "p95": self.planning_latency.percentile(95),
                    "mean": self.planning_latency.mean(),
                },
                "routing": {
                    "p50": self.routing_latency.percentile(50),
                    "p95": self.routing_latency.percentile(95),
                    "mean": self.routing_latency.mean(),
                },
                "tools": {
                    tool: {
                        "p50": hist.percentile(50),
                        "p95": hist.percentile(95),
                        "mean": hist.mean(),
                    }
                    for tool, hist in self.tool_latency.items()
                },
            },
            "approval": {
                "requests": self.approval_requests.get(),
                "timeouts": self.approval_timeouts.get(),
                "wait_time": {
                    "p50": self.approval_wait_times.percentile(50),
                    "p95": self.approval_wait_times.percentile(95),
                    "p99": self.approval_wait_times.percentile(99),
                    "mean": self.approval_wait_times.mean(),
                },
            },
            "budget": {
                "warnings": self.budget_warnings.get(),
                "exceeded": self.budget_exceeded.get(),
                "utilization": {
                    budget_type: statistics.mean(values) if values else 0.0
                    for budget_type, values in self.budget_utilization.items()
                },
            },
        }
    
    def reset(self) -> None:
        """Reset all metrics (useful for testing or periodic resets)."""
        self.total_requests.reset()
        self.successful_requests.reset()
        self.failed_requests.reset()
        self.end_to_end_latency.clear()
        self.tool_latency.clear()
        self.planning_latency.clear()
        self.routing_latency.clear()
        self.steps_per_task.clear()
        self.tool_calls.reset()
        self.tool_errors.reset()
        self.tool_errors_by_tool.clear()
        self.tool_errors_by_type.clear()
        self.approval_requests.reset()
        self.approval_wait_times.clear()
        self.approval_timeouts.reset()
        self.budget_warnings.reset()
        self.budget_exceeded.reset()
        self.budget_utilization.clear()
        self.requests_by_profile.clear()
        self._start_time = time.time()
