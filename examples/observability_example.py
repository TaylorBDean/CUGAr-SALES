"""
Example: CUGAR Agent Observability Integration

Demonstrates how to integrate observability into agent execution with:
- Structured event emission
- Golden signal tracking
- OTEL export
- Metrics endpoint

Run:
    python examples/observability_example.py
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List

from cuga.observability import (
    ObservabilityCollector,
    PlanEvent,
    RouteEvent,
    ToolCallEvent,
    BudgetEvent,
    ApprovalEvent,
    OTELExporter,
    ConsoleExporter,
    get_collector,
    set_collector,
)


def simulate_agent_execution(
    goal: str,
    tools: List[str],
    trace_id: str,
) -> Dict[str, Any]:
    """
    Simulate agent execution with observability.
    
    Args:
        goal: User goal/intent
        tools: List of tools to execute
        trace_id: Trace identifier
    
    Returns:
        Execution result with metrics
    """
    collector = get_collector()
    
    # Start trace
    collector.start_trace(trace_id, {"goal": goal})
    print(f"🔍 Starting trace: {trace_id}")
    
    # === PLANNING PHASE ===
    print(f"\n📋 Planning: {goal}")
    plan_start = time.time()
    
    # Simulate planning
    time.sleep(0.1)
    
    plan_duration = (time.time() - plan_start) * 1000
    plan_event = PlanEvent.create(
        trace_id=trace_id,
        goal=goal,
        steps_count=len(tools),
        tools_selected=tools,
        duration_ms=plan_duration,
    )
    collector.emit_event(plan_event)
    print(f"✅ Plan created: {len(tools)} steps in {plan_duration:.2f}ms")
    
    # === ROUTING PHASE ===
    print(f"\n🔀 Routing decision")
    route_start = time.time()
    
    # Simulate routing
    time.sleep(0.05)
    
    route_duration = (time.time() - route_start) * 1000
    route_event = RouteEvent.create(
        trace_id=trace_id,
        agent_selected="primary_agent",
        routing_policy="capability_based",
        alternatives_considered=["fallback_agent"],
        reasoning="Primary agent has all required capabilities",
    )
    collector.emit_event(route_event)
    print(f"✅ Routed to: primary_agent in {route_duration:.2f}ms")
    
    # === TOOL EXECUTION PHASE ===
    print(f"\n🔧 Executing tools")
    budget_spent = 0.0
    budget_ceiling = 100.0
    
    for i, tool in enumerate(tools):
        print(f"\n  Tool {i+1}/{len(tools)}: {tool}")
        
        # Tool call start
        start_event = ToolCallEvent.start(
            trace_id=trace_id,
            tool_name=tool,
            tool_params={"index": i, "goal": goal},
        )
        collector.emit_event(start_event)
        
        tool_start = time.time()
        
        # Simulate tool execution
        time.sleep(0.2)
        
        tool_duration = (time.time() - tool_start) * 1000
        
        # Simulate budget tracking
        tool_cost = 15.0 + (i * 10.0)
        budget_spent += tool_cost
        
        if budget_spent > budget_ceiling * 0.8 and budget_spent < budget_ceiling:
            # Budget warning
            warning_event = BudgetEvent.warning(
                trace_id=trace_id,
                budget_type="cost",
                spent=budget_spent,
                ceiling=budget_ceiling,
                threshold=budget_ceiling * 0.8,
            )
            collector.emit_event(warning_event)
            print(f"  ⚠️  Budget warning: {budget_spent:.2f}/{budget_ceiling:.2f}")
        
        # Simulate occasional errors
        if i == 2:  # Simulate error on third tool
            error_event = ToolCallEvent.error(
                trace_id=trace_id,
                tool_name=tool,
                error_type="timeout",
                error_message="Tool execution timed out",
                duration_ms=tool_duration,
            )
            collector.emit_event(error_event)
            print(f"  ❌ Tool failed: timeout after {tool_duration:.2f}ms")
        else:
            # Tool call complete
            complete_event = ToolCallEvent.complete(
                trace_id=trace_id,
                tool_name=tool,
                duration_ms=tool_duration,
                result_size=1024,
            )
            collector.emit_event(complete_event)
            print(f"  ✅ Tool completed in {tool_duration:.2f}ms")
    
    # === APPROVAL SIMULATION (for risky action) ===
    if "delete" in goal.lower() or "modify" in goal.lower():
        print(f"\n⏸️  Requesting approval for risky action")
        
        approval_request = ApprovalEvent.requested(
            trace_id=trace_id,
            action_description=f"Execute: {goal}",
            risk_level="medium",
            timeout_seconds=30,
        )
        collector.emit_event(approval_request)
        
        # Simulate approval wait
        approval_start = time.time()
        time.sleep(0.5)  # Simulate human decision time
        approval_duration = (time.time() - approval_start) * 1000
        
        approval_received = ApprovalEvent.received(
            trace_id=trace_id,
            approved=True,
            wait_time_ms=approval_duration,
            reason="Approved by user",
        )
        collector.emit_event(approval_received)
        print(f"  ✅ Approved after {approval_duration:.2f}ms")
    
    # === END TRACE ===
    success = budget_spent < budget_ceiling
    collector.end_trace(trace_id, success=success)
    
    if success:
        print(f"\n✅ Execution completed successfully")
    else:
        print(f"\n❌ Execution failed: budget exceeded")
    
    return {
        "trace_id": trace_id,
        "success": success,
        "budget_spent": budget_spent,
        "tools_executed": len(tools),
    }


def print_metrics():
    """Print current golden signals."""
    collector = get_collector()
    metrics = collector.get_metrics()
    
    print("\n" + "="*60)
    print("📊 GOLDEN SIGNALS")
    print("="*60)
    
    print(f"\n🎯 Success Rate: {metrics['success_rate']:.2f}%")
    print(f"❌ Error Rate: {metrics['error_rate']:.2f}%")
    print(f"🔧 Tool Error Rate: {metrics['tool_error_rate']:.2f}%")
    
    print(f"\n📈 Latency (ms):")
    latency = metrics['latency']['end_to_end']
    print(f"  P50: {latency['p50']:.2f}ms")
    print(f"  P95: {latency['p95']:.2f}ms")
    print(f"  P99: {latency['p99']:.2f}ms")
    print(f"  Mean: {latency['mean']:.2f}ms")
    
    print(f"\n📊 Traffic:")
    print(f"  Total Requests: {metrics['total_requests']}")
    print(f"  Successful: {metrics['successful_requests']}")
    print(f"  Failed: {metrics['failed_requests']}")
    print(f"  RPS: {metrics['requests_per_second']:.2f}")
    
    print(f"\n🔧 Tools:")
    print(f"  Total Calls: {metrics['tool_calls']}")
    print(f"  Total Errors: {metrics['tool_errors']}")
    print(f"  Mean Steps/Task: {metrics['mean_steps_per_task']:.1f}")
    
    if metrics['approval']['requests'] > 0:
        print(f"\n⏸️  Approvals:")
        print(f"  Requests: {metrics['approval']['requests']}")
        print(f"  Timeouts: {metrics['approval']['timeouts']}")
        approval_wait = metrics['approval']['wait_time']
        print(f"  Wait Time P95: {approval_wait['p95']:.2f}ms")
    
    print("\n" + "="*60)


def main():
    """Run observability example."""
    print("🚀 CUGAR Agent Observability Example")
    print("="*60)
    
    # Initialize collector with console exporter
    # In production, use OTELExporter with real endpoint
    collector = ObservabilityCollector(
        exporters=[
            ConsoleExporter(pretty=True),
            # Uncomment to enable OTEL export:
            # OTELExporter(
            #     endpoint="http://localhost:4318",
            #     service_name="cuga-agent",
            # ),
        ],
        auto_export=True,
    )
    set_collector(collector)
    
    # Simulate multiple agent executions
    scenarios = [
        {
            "goal": "Search and analyze data",
            "tools": ["search", "filter", "analyze", "summarize"],
        },
        {
            "goal": "Generate report",
            "tools": ["gather_data", "process", "format", "export"],
        },
        {
            "goal": "Modify configuration",
            "tools": ["validate", "backup", "modify", "verify"],
        },
    ]
    
    results = []
    for i, scenario in enumerate(scenarios):
        print(f"\n\n{'='*60}")
        print(f"Scenario {i+1}/{len(scenarios)}")
        print(f"{'='*60}")
        
        trace_id = f"trace-{uuid.uuid4()}"
        result = simulate_agent_execution(
            goal=scenario["goal"],
            tools=scenario["tools"],
            trace_id=trace_id,
        )
        results.append(result)
        
        # Small delay between executions
        time.sleep(0.5)
    
    # Print golden signals
    print_metrics()
    
    # Export Prometheus metrics
    print("\n\n📊 Prometheus Metrics Export:")
    print("="*60)
    prometheus_text = collector.get_prometheus_metrics()
    print(prometheus_text[:500] + "\n... (truncated)")
    
    # Shutdown collector
    print("\n\n🛑 Shutting down observability collector...")
    collector.shutdown()
    print("✅ Done!")


if __name__ == "__main__":
    main()
