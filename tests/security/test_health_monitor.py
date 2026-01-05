"""Tests for registry health monitoring with discovery, drift detection, and caching."""

import asyncio
import pytest
from datetime import datetime, timedelta

from cuga.mcp.interfaces import ToolSpec
from cuga.security.health_monitor import (
    CachedToolSpec,
    HealthCheckResult,
    RegistryHealthMonitor,
    SchemaSignature,
)


@pytest.fixture
def sample_tool_specs():
    """Sample tool specs for testing."""
    return [
        ToolSpec(
            alias="tool_a",
            version="1.0.0",
            description="Tool A",
            input_schema={"type": "object", "properties": {"x": {"type": "string"}}},
        ),
        ToolSpec(
            alias="tool_b",
            version="1.1.0",
            description="Tool B",
            input_schema={"type": "object", "properties": {"y": {"type": "number"}}},
        ),
        ToolSpec(
            alias="tool_c",
            version="2.0.0",
            description="Tool C",
            input_schema={"type": "object", "properties": {"z": {"type": "boolean"}}},
        ),
    ]


@pytest.fixture
def health_monitor():
    """Health monitor instance."""
    return RegistryHealthMonitor(
        discovery_interval_seconds=300,
        schema_check_interval_seconds=600,
        cache_ttl_seconds=3600,
        max_cold_start_tools=100,
    )


def test_cache_tool_spec(health_monitor, sample_tool_specs):
    """Test caching tool spec with TTL."""
    spec = sample_tool_specs[0]
    health_monitor.cache_tool_spec(spec, ttl_seconds=1800)
    
    cached = health_monitor.get_cached_tool_spec("tool_a")
    assert cached is not None
    assert cached.alias == "tool_a"
    assert cached.version == "1.0.0"


def test_cache_expiration(health_monitor, sample_tool_specs):
    """Test cache entry expiration."""
    spec = sample_tool_specs[0]
    health_monitor.cache_tool_spec(spec, ttl_seconds=0)  # Immediate expiration
    
    # Should return None after expiration
    cached = health_monitor.get_cached_tool_spec("tool_a")
    assert cached is None


def test_cache_invalidation_single_tool(health_monitor, sample_tool_specs):
    """Test invalidating cache for single tool."""
    for spec in sample_tool_specs:
        health_monitor.cache_tool_spec(spec)
    
    health_monitor.invalidate_cache("tool_a")
    
    assert health_monitor.get_cached_tool_spec("tool_a") is None
    assert health_monitor.get_cached_tool_spec("tool_b") is not None
    assert health_monitor.get_cached_tool_spec("tool_c") is not None


def test_cache_invalidation_all_tools(health_monitor, sample_tool_specs):
    """Test invalidating all cached tools."""
    for spec in sample_tool_specs:
        health_monitor.cache_tool_spec(spec)
    
    health_monitor.invalidate_cache()
    
    assert health_monitor.get_cached_tool_spec("tool_a") is None
    assert health_monitor.get_cached_tool_spec("tool_b") is None
    assert health_monitor.get_cached_tool_spec("tool_c") is None


def test_schema_signature_generation(sample_tool_specs):
    """Test schema signature generation from tool spec."""
    spec = sample_tool_specs[0]
    signature = SchemaSignature.from_tool_spec(spec)
    
    assert signature.tool_name == "tool_a"
    assert len(signature.schema_hash) == 64  # SHA256 hex digest
    assert signature.schema == spec.input_schema


def test_schema_drift_detection_no_change(health_monitor, sample_tool_specs):
    """Test no drift when schema unchanged."""
    spec = sample_tool_specs[0]
    
    # First capture
    health_monitor.capture_schema_signature(spec)
    
    # Check again with same schema
    drift = health_monitor.check_schema_drift(spec)
    assert drift is None


def test_schema_drift_detection_with_change(health_monitor, sample_tool_specs):
    """Test drift detection when schema changes."""
    spec_v1 = sample_tool_specs[0]
    
    # Capture baseline
    health_monitor.capture_schema_signature(spec_v1)
    
    # Create modified spec
    spec_v2 = ToolSpec(
        alias="tool_a",
        version="1.1.0",
        description="Tool A updated",
        input_schema={"type": "object", "properties": {"x": {"type": "number"}}},  # Changed type
    )
    
    # Check for drift
    drift = health_monitor.check_schema_drift(spec_v2)
    
    assert drift is not None
    assert drift["tool"] == "tool_a"
    assert drift["old_hash"] != drift["new_hash"]
    assert drift["old_schema"] == spec_v1.input_schema
    assert drift["new_schema"] == spec_v2.input_schema


def test_schema_signature_hash_consistency():
    """Test schema signatures produce consistent hashes."""
    spec1 = ToolSpec(
        alias="test_tool",
        version="1.0.0",
        input_schema={"type": "object", "properties": {"a": {"type": "string"}}},
    )
    
    spec2 = ToolSpec(
        alias="test_tool",
        version="1.0.0",
        input_schema={"type": "object", "properties": {"a": {"type": "string"}}},
    )
    
    sig1 = SchemaSignature.from_tool_spec(spec1)
    sig2 = SchemaSignature.from_tool_spec(spec2)
    
    assert sig1.schema_hash == sig2.schema_hash


@pytest.mark.asyncio
async def test_ping_tool_success(health_monitor, sample_tool_specs):
    """Test successful tool ping."""
    spec = sample_tool_specs[0]
    result = await health_monitor.ping_tool(spec)
    
    assert result.tool_name == "tool_a"
    assert result.is_healthy is True
    assert result.response_time_ms > 0
    assert result.error_message is None


@pytest.mark.asyncio
async def test_discover_tools(health_monitor, sample_tool_specs):
    """Test tool discovery with health checks."""
    health_map = await health_monitor.discover_tools(sample_tool_specs)
    
    assert len(health_map) == 3
    assert "tool_a" in health_map
    assert "tool_b" in health_map
    assert "tool_c" in health_map
    
    for result in health_map.values():
        assert isinstance(result, HealthCheckResult)
        assert result.is_healthy is True


@pytest.mark.asyncio
async def test_discover_tools_cold_start_limit(health_monitor):
    """Test cold start protection with tool count limit."""
    # Create more tools than max_cold_start_tools
    many_specs = [
        ToolSpec(
            alias=f"tool_{i}",
            version="1.0.0",
            description=f"Tool {i}",
            input_schema={},
        )
        for i in range(150)
    ]
    
    health_map = await health_monitor.discover_tools(many_specs)
    
    # Should be limited to max_cold_start_tools (100)
    assert len(health_map) <= health_monitor.max_cold_start_tools


def test_get_health_status(health_monitor):
    """Test retrieving health status for specific tool."""
    result = HealthCheckResult(
        tool_name="test_tool",
        is_healthy=True,
        checked_at=datetime.utcnow(),
        response_time_ms=42.5,
    )
    health_monitor._health_results["test_tool"] = result
    
    retrieved = health_monitor.get_health_status("test_tool")
    assert retrieved is not None
    assert retrieved.tool_name == "test_tool"
    assert retrieved.is_healthy is True


def test_get_health_status_unknown_tool(health_monitor):
    """Test retrieving health status for unknown tool."""
    status = health_monitor.get_health_status("unknown_tool")
    assert status is None


def test_get_all_health_statuses(health_monitor):
    """Test retrieving all health statuses."""
    results = {
        "tool_a": HealthCheckResult("tool_a", True, datetime.utcnow(), 10.0),
        "tool_b": HealthCheckResult("tool_b", True, datetime.utcnow(), 20.0),
        "tool_c": HealthCheckResult("tool_c", False, datetime.utcnow(), -1, "Error"),
    }
    
    health_monitor._health_results = results
    
    all_statuses = health_monitor.get_all_health_statuses()
    assert len(all_statuses) == 3
    assert all_statuses["tool_a"].is_healthy is True
    assert all_statuses["tool_c"].is_healthy is False


def test_should_run_discovery_initial(health_monitor):
    """Test discovery should run initially."""
    assert health_monitor.should_run_discovery() is True


def test_should_run_discovery_after_interval(health_monitor):
    """Test discovery should run after interval."""
    health_monitor._last_discovery = datetime.utcnow() - timedelta(seconds=301)
    assert health_monitor.should_run_discovery() is True


def test_should_not_run_discovery_before_interval(health_monitor):
    """Test discovery should not run before interval."""
    health_monitor._last_discovery = datetime.utcnow()
    assert health_monitor.should_run_discovery() is False


def test_should_check_schemas_initial(health_monitor):
    """Test schema check should run initially."""
    assert health_monitor.should_check_schemas() is True


def test_should_check_schemas_after_interval(health_monitor):
    """Test schema check should run after interval."""
    health_monitor._last_schema_check = datetime.utcnow() - timedelta(seconds=601)
    assert health_monitor.should_check_schemas() is True


def test_should_not_check_schemas_before_interval(health_monitor):
    """Test schema check should not run before interval."""
    health_monitor._last_schema_check = datetime.utcnow()
    assert health_monitor.should_check_schemas() is False


def test_get_metrics(health_monitor):
    """Test metrics summary generation."""
    health_monitor._health_results = {
        "tool_a": HealthCheckResult("tool_a", True, datetime.utcnow(), 10.5),
        "tool_b": HealthCheckResult("tool_b", True, datetime.utcnow(), 20.3),
        "tool_c": HealthCheckResult("tool_c", False, datetime.utcnow(), -1),
    }
    
    health_monitor._tool_cache = {
        "tool_a": CachedToolSpec(
            spec=ToolSpec(alias="tool_a", version="1.0.0"),
            cached_at=datetime.utcnow(),
        ),
    }
    
    metrics = health_monitor.get_metrics()
    
    assert metrics["total_tools"] == 3
    assert metrics["healthy_tools"] == 2
    assert metrics["unhealthy_tools"] == 1
    assert metrics["cached_tools"] == 1
    assert metrics["avg_response_time_ms"] > 0


def test_cached_tool_spec_expiration():
    """Test CachedToolSpec expiration logic."""
    spec = ToolSpec(alias="test", version="1.0.0")
    
    cached = CachedToolSpec(
        spec=spec,
        cached_at=datetime.utcnow() - timedelta(seconds=3601),
        ttl_seconds=3600,
    )
    
    assert cached.is_expired() is True


def test_cached_tool_spec_not_expired():
    """Test CachedToolSpec not expired."""
    spec = ToolSpec(alias="test", version="1.0.0")
    
    cached = CachedToolSpec(
        spec=spec,
        cached_at=datetime.utcnow(),
        ttl_seconds=3600,
    )
    
    assert cached.is_expired() is False
