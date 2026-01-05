"""
Example: Integrating MCP/OpenAPI Governance with Orchestrator

This example demonstrates how to integrate the governance system into an
orchestrator's tool execution pipeline with:

1. Cache-first tool spec retrieval with TTL
2. Schema drift detection and alerts
3. Governance validation (tenant capability maps + tool restrictions)
4. Approval gates for high-risk actions (HITL)
5. Rate limiting enforcement
6. Structured observability with trace_id propagation

Prerequisites:
    - Governance configurations loaded from configurations/policies/*.yaml
    - Health monitor initialized on startup
    - Governance engine initialized with capabilities and tenant maps

Usage:
    python examples/governance_integration.py
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict

from cuga.agents.policy import PolicyViolation
from cuga.mcp.interfaces import ToolSpec
from cuga.security import (
    ApprovalStatus,
    GovernanceEngine,
    RegistryHealthMonitor,
    create_governance_engine,
)


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class MockToolRegistry:
    """Mock tool registry for demonstration."""
    
    def __init__(self):
        self.tools = {
            "slack_send_message": ToolSpec(
                alias="slack_send_message",
                version="1.0.0",
                description="Send message to Slack channel",
                input_schema={
                    "type": "object",
                    "properties": {
                        "channel": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["channel", "message"],
                },
            ),
            "file_read": ToolSpec(
                alias="file_read",
                version="1.0.0",
                description="Read file contents",
                input_schema={
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                    },
                    "required": ["path"],
                },
            ),
            "stock_order_place": ToolSpec(
                alias="stock_order_place",
                version="2.0.0",
                description="Place stock trading order",
                input_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "quantity": {"type": "number"},
                        "order_type": {"type": "string", "enum": ["market", "limit"]},
                    },
                    "required": ["symbol", "quantity", "order_type"],
                },
            ),
        }
    
    def get(self, tool_name: str) -> ToolSpec:
        """Get tool spec by name."""
        if tool_name not in self.tools:
            raise KeyError(f"Tool '{tool_name}' not found")
        return self.tools[tool_name]
    
    def execute(self, tool_name: str, inputs: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool (mock implementation)."""
        logger.info(f"Executing tool '{tool_name}' with inputs: {inputs}")
        return {"success": True, "result": f"Mock execution of {tool_name}"}


async def execute_tool_with_governance(
    tool_name: str,
    inputs: Dict[str, Any],
    context: Dict[str, Any],
    governance_engine: GovernanceEngine,
    health_monitor: RegistryHealthMonitor,
    registry: MockToolRegistry,
) -> Dict[str, Any]:
    """
    Execute tool with full governance pipeline.
    
    Pipeline stages:
        1. Cache check with TTL enforcement
        2. Schema drift detection and alert
        3. Governance validation (tenant + tool restrictions)
        4. Approval gate (if required)
        5. Rate limit enforcement
        6. Tool execution
    
    Args:
        tool_name: Name of tool to execute
        inputs: Tool input parameters
        context: Execution context (tenant, trace_id, etc.)
        governance_engine: Initialized governance engine
        health_monitor: Initialized health monitor
        registry: Tool registry
    
    Returns:
        Tool execution result
    
    Raises:
        PolicyViolation: If governance checks fail
    """
    tenant = context.get("tenant", "default")
    trace_id = context.get("trace_id", f"trace-{datetime.utcnow().timestamp()}")
    
    logger.info(
        "Starting tool execution with governance",
        extra={
            "tool": tool_name,
            "tenant": tenant,
            "trace_id": trace_id,
        }
    )
    
    # Stage 1: Check cache first
    cached_spec = health_monitor.get_cached_tool_spec(tool_name)
    if cached_spec is None:
        logger.debug(f"Cache miss for tool '{tool_name}', fetching from registry")
        spec = registry.get(tool_name)
        health_monitor.cache_tool_spec(spec)
        
        # Stage 2: Check for schema drift
        drift = health_monitor.check_schema_drift(spec)
        if drift:
            logger.warning(
                "Schema drift detected",
                extra={
                    "tool": drift["tool"],
                    "old_hash": drift["old_hash"],
                    "new_hash": drift["new_hash"],
                    "trace_id": trace_id,
                }
            )
            # In production: alert operators, invalidate dependent caches, etc.
    else:
        logger.debug(f"Cache hit for tool '{tool_name}'")
        spec = cached_spec
    
    # Stage 3: Governance validation
    try:
        governance_engine.validate_tool_call(
            tool_name=tool_name,
            tenant=tenant,
            inputs=inputs,
            context=context,
        )
        logger.info(
            "Governance validation passed",
            extra={
                "tool": tool_name,
                "tenant": tenant,
                "trace_id": trace_id,
            }
        )
    except PolicyViolation as e:
        logger.error(
            "Governance validation failed",
            extra={
                "tool": tool_name,
                "tenant": tenant,
                "code": e.code,
                "message": e.message,
                "trace_id": trace_id,
            }
        )
        raise
    
    # Stage 4: Approval gate (if required)
    capability = governance_engine.capabilities.get(tool_name)
    if capability and capability.requires_approval:
        approval_request_id = f"{trace_id}-approval"
        
        approval = governance_engine.request_approval(
            tool_name=tool_name,
            tenant=tenant,
            inputs=inputs,
            context=context,
            request_id=approval_request_id,
        )
        
        logger.info(
            "Approval request created",
            extra={
                "request_id": approval_request_id,
                "tool": tool_name,
                "tenant": tenant,
                "status": approval.status.value,
                "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
                "trace_id": trace_id,
            }
        )
        
        # Stage 5: Wait for approval (in real system, this would be webhook/polling)
        if approval.status == ApprovalStatus.PENDING:
            logger.info(
                "Waiting for HITL approval",
                extra={
                    "request_id": approval_request_id,
                    "tool": tool_name,
                    "trace_id": trace_id,
                }
            )
            
            # Simulate approval decision (in real system, this comes from user)
            # For demo: auto-approve after short delay
            await asyncio.sleep(0.1)
            governance_engine.approve_request(approval_request_id, approved_by="demo-user")
            
            logger.info(
                "Approval granted",
                extra={
                    "request_id": approval_request_id,
                    "tool": tool_name,
                    "approved_by": "demo-user",
                    "trace_id": trace_id,
                }
            )
        
        # Verify approval status
        status = governance_engine.get_approval_status(approval_request_id)
        if status != ApprovalStatus.APPROVED:
            raise PolicyViolation(
                profile=tenant,
                tool=tool_name,
                code="approval_not_granted",
                message=f"Approval status: {status.value}",
            )
    
    # Stage 6: Execute tool (rate limits already enforced in validate_tool_call)
    logger.info(
        "Executing tool",
        extra={
            "tool": tool_name,
            "tenant": tenant,
            "trace_id": trace_id,
        }
    )
    
    result = registry.execute(tool_name, inputs, context)
    
    logger.info(
        "Tool execution completed",
        extra={
            "tool": tool_name,
            "tenant": tenant,
            "success": result.get("success"),
            "trace_id": trace_id,
        }
    )
    
    return result


async def main():
    """Demonstration of governance integration."""
    
    # Initialize components
    logger.info("Initializing governance engine and health monitor")
    
    governance_engine = create_governance_engine()
    health_monitor = RegistryHealthMonitor()
    registry = MockToolRegistry()
    
    # Run initial tool discovery
    logger.info("Running tool discovery")
    tool_specs = [registry.get(name) for name in registry.tools.keys()]
    health_map = await health_monitor.discover_tools(tool_specs)
    
    for tool_name, health in health_map.items():
        logger.info(
            f"Tool '{tool_name}' health: {'✓' if health.is_healthy else '✗'} "
            f"({health.response_time_ms:.2f}ms)"
        )
    
    # Example 1: Marketing tenant sends Slack message (requires approval)
    logger.info("\n=== Example 1: Marketing sends Slack message (WRITE action) ===")
    try:
        result = await execute_tool_with_governance(
            tool_name="slack_send_message",
            inputs={"channel": "#general", "message": "Hello from marketing!"},
            context={"tenant": "marketing", "trace_id": "trace-001"},
            governance_engine=governance_engine,
            health_monitor=health_monitor,
            registry=registry,
        )
        logger.info(f"Result: {result}")
    except PolicyViolation as e:
        logger.error(f"Failed: {e}")
    
    # Example 2: Marketing tenant reads file (auto-approved READ)
    logger.info("\n=== Example 2: Marketing reads file (READ action) ===")
    try:
        result = await execute_tool_with_governance(
            tool_name="file_read",
            inputs={"path": "/data/report.csv"},
            context={"tenant": "marketing", "trace_id": "trace-002"},
            governance_engine=governance_engine,
            health_monitor=health_monitor,
            registry=registry,
        )
        logger.info(f"Result: {result}")
    except PolicyViolation as e:
        logger.error(f"Failed: {e}")
    
    # Example 3: Marketing tenant tries stock order (denied by tenant map)
    logger.info("\n=== Example 3: Marketing tries stock order (denied) ===")
    try:
        result = await execute_tool_with_governance(
            tool_name="stock_order_place",
            inputs={"symbol": "AAPL", "quantity": 100, "order_type": "market"},
            context={"tenant": "marketing", "trace_id": "trace-003"},
            governance_engine=governance_engine,
            health_monitor=health_monitor,
            registry=registry,
        )
        logger.info(f"Result: {result}")
    except PolicyViolation as e:
        logger.error(f"Failed: {e.code} - {e.message}")
    
    # Example 4: Trading tenant places stock order (allowed)
    logger.info("\n=== Example 4: Trading places stock order (FINANCIAL action) ===")
    try:
        result = await execute_tool_with_governance(
            tool_name="stock_order_place",
            inputs={"symbol": "AAPL", "quantity": 100, "order_type": "market"},
            context={"tenant": "trading", "trace_id": "trace-004"},
            governance_engine=governance_engine,
            health_monitor=health_monitor,
            registry=registry,
        )
        logger.info(f"Result: {result}")
    except PolicyViolation as e:
        logger.error(f"Failed: {e}")
    
    # Show metrics
    logger.info("\n=== Health Monitor Metrics ===")
    metrics = health_monitor.get_metrics()
    logger.info(f"Total tools: {metrics['total_tools']}")
    logger.info(f"Healthy tools: {metrics['healthy_tools']}")
    logger.info(f"Cached tools: {metrics['cached_tools']}")
    logger.info(f"Avg response time: {metrics['avg_response_time_ms']:.2f}ms")


if __name__ == "__main__":
    asyncio.run(main())
