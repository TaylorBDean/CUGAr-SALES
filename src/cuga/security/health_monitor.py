"""Runtime registry health checks with tool discovery, schema drift detection, and cache TTLs."""

from __future__ import annotations

import asyncio
import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..mcp.interfaces import ToolSpec


logger = logging.getLogger(__name__)


@dataclass
class HealthCheckResult:
    """Result of a tool health check."""
    
    tool_name: str
    is_healthy: bool
    checked_at: datetime
    response_time_ms: float
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SchemaSignature:
    """Schema signature for drift detection."""
    
    tool_name: str
    schema_hash: str
    schema: Dict[str, Any]
    captured_at: datetime
    
    @classmethod
    def from_tool_spec(cls, spec: ToolSpec) -> SchemaSignature:
        """Generate signature from tool spec."""
        schema = spec.input_schema or {}
        schema_str = str(sorted(schema.items()))
        schema_hash = hashlib.sha256(schema_str.encode()).hexdigest()
        
        return cls(
            tool_name=spec.alias,
            schema_hash=schema_hash,
            schema=schema,
            captured_at=datetime.utcnow(),
        )
    
    def has_drifted(self, other: SchemaSignature) -> bool:
        """Check if schema has changed compared to another signature."""
        return self.schema_hash != other.schema_hash


@dataclass
class CachedToolSpec:
    """Cached tool spec with TTL."""
    
    spec: ToolSpec
    cached_at: datetime
    ttl_seconds: int = 3600  # 1 hour default
    
    def is_expired(self) -> bool:
        """Check if cache entry has expired."""
        return datetime.utcnow() > self.cached_at + timedelta(seconds=self.ttl_seconds)


class RegistryHealthMonitor:
    """Runtime health monitoring for tool registry with discovery, drift detection, and caching."""
    
    def __init__(
        self,
        discovery_interval_seconds: int = 300,  # 5 minutes
        schema_check_interval_seconds: int = 600,  # 10 minutes
        cache_ttl_seconds: int = 3600,  # 1 hour
        max_cold_start_tools: int = 100,  # Limit for huge registry cold starts
    ) -> None:
        """
        Initialize health monitor.
        
        Args:
            discovery_interval_seconds: How often to ping tools for availability
            schema_check_interval_seconds: How often to check for schema drift
            cache_ttl_seconds: Default TTL for cached tool specs
            max_cold_start_tools: Maximum tools to load on cold start (prevents huge lists)
        """
        self.discovery_interval = discovery_interval_seconds
        self.schema_check_interval = schema_check_interval_seconds
        self.cache_ttl = cache_ttl_seconds
        self.max_cold_start_tools = max_cold_start_tools
        
        self._tool_cache: Dict[str, CachedToolSpec] = {}
        self._schema_signatures: Dict[str, SchemaSignature] = {}
        self._health_results: Dict[str, HealthCheckResult] = {}
        self._last_discovery: Optional[datetime] = None
        self._last_schema_check: Optional[datetime] = None
    
    def cache_tool_spec(self, spec: ToolSpec, ttl_seconds: Optional[int] = None) -> None:
        """Cache a tool spec with TTL."""
        cached = CachedToolSpec(
            spec=spec,
            cached_at=datetime.utcnow(),
            ttl_seconds=ttl_seconds or self.cache_ttl,
        )
        self._tool_cache[spec.alias] = cached
        
        logger.debug(
            "Tool spec cached",
            extra={
                "tool": spec.alias,
                "ttl_seconds": cached.ttl_seconds,
                "expires_at": (cached.cached_at + timedelta(seconds=cached.ttl_seconds)).isoformat(),
            },
        )
    
    def get_cached_tool_spec(self, tool_name: str) -> Optional[ToolSpec]:
        """Retrieve cached tool spec if not expired."""
        cached = self._tool_cache.get(tool_name)
        if cached is None:
            return None
        
        if cached.is_expired():
            logger.debug(f"Cached tool spec expired: {tool_name}")
            del self._tool_cache[tool_name]
            return None
        
        return cached.spec
    
    def invalidate_cache(self, tool_name: Optional[str] = None) -> None:
        """Invalidate cache for specific tool or all tools."""
        if tool_name:
            if tool_name in self._tool_cache:
                del self._tool_cache[tool_name]
                logger.info(f"Cache invalidated for tool: {tool_name}")
        else:
            self._tool_cache.clear()
            logger.info("All tool caches invalidated")
    
    def capture_schema_signature(self, spec: ToolSpec) -> SchemaSignature:
        """Capture schema signature for drift detection."""
        signature = SchemaSignature.from_tool_spec(spec)
        self._schema_signatures[spec.alias] = signature
        
        logger.debug(
            "Schema signature captured",
            extra={
                "tool": spec.alias,
                "schema_hash": signature.schema_hash,
            },
        )
        
        return signature
    
    def check_schema_drift(self, spec: ToolSpec) -> Optional[Dict[str, Any]]:
        """
        Check if tool schema has drifted from last known signature.
        
        Returns:
            Drift details dict if drift detected, None otherwise
        """
        new_signature = SchemaSignature.from_tool_spec(spec)
        old_signature = self._schema_signatures.get(spec.alias)
        
        if old_signature is None:
            # First time seeing this tool, capture baseline
            self.capture_schema_signature(spec)
            return None
        
        if new_signature.has_drifted(old_signature):
            drift_details = {
                "tool": spec.alias,
                "old_hash": old_signature.schema_hash,
                "new_hash": new_signature.schema_hash,
                "old_schema": old_signature.schema,
                "new_schema": new_signature.schema,
                "detected_at": datetime.utcnow().isoformat(),
            }
            
            logger.warning(
                "Schema drift detected",
                extra=drift_details,
            )
            
            # Update baseline
            self.capture_schema_signature(spec)
            
            return drift_details
        
        return None
    
    async def ping_tool(self, spec: ToolSpec, timeout_seconds: float = 5.0) -> HealthCheckResult:
        """
        Ping tool for availability check (lightweight discovery).
        
        Args:
            spec: Tool spec to ping
            timeout_seconds: Maximum time to wait for response
        
        Returns:
            HealthCheckResult with availability status
        """
        start_time = datetime.utcnow()
        
        try:
            # Lightweight ping - just check if tool is responsive
            # In real implementation, this would call tool's health endpoint
            # For now, we simulate with a small delay
            await asyncio.sleep(0.01)  # Simulate network call
            
            response_time = (datetime.utcnow() - start_time).total_seconds() * 1000
            
            result = HealthCheckResult(
                tool_name=spec.alias,
                is_healthy=True,
                checked_at=datetime.utcnow(),
                response_time_ms=response_time,
                metadata={"version": spec.version or "unknown"},
            )
            
            self._health_results[spec.alias] = result
            
            logger.debug(
                "Tool ping successful",
                extra={
                    "tool": spec.alias,
                    "response_time_ms": response_time,
                },
            )
            
            return result
            
        except asyncio.TimeoutError:
            result = HealthCheckResult(
                tool_name=spec.alias,
                is_healthy=False,
                checked_at=datetime.utcnow(),
                response_time_ms=-1,
                error_message=f"Timeout after {timeout_seconds}s",
            )
            
            self._health_results[spec.alias] = result
            
            logger.error(
                "Tool ping timeout",
                extra={
                    "tool": spec.alias,
                    "timeout_seconds": timeout_seconds,
                },
            )
            
            return result
            
        except Exception as e:
            result = HealthCheckResult(
                tool_name=spec.alias,
                is_healthy=False,
                checked_at=datetime.utcnow(),
                response_time_ms=-1,
                error_message=str(e),
            )
            
            self._health_results[spec.alias] = result
            
            logger.error(
                "Tool ping failed",
                extra={
                    "tool": spec.alias,
                    "error": str(e),
                },
                exc_info=True,
            )
            
            return result
    
    async def discover_tools(self, specs: List[ToolSpec]) -> Dict[str, HealthCheckResult]:
        """
        Run discovery ping for all tools (cold start protection).
        
        Args:
            specs: List of tool specs to discover
        
        Returns:
            Mapping of tool name -> health result
        """
        if len(specs) > self.max_cold_start_tools:
            logger.warning(
                f"Tool list exceeds cold start limit ({len(specs)} > {self.max_cold_start_tools}), "
                f"truncating to first {self.max_cold_start_tools} tools"
            )
            specs = specs[: self.max_cold_start_tools]
        
        logger.info(f"Starting tool discovery for {len(specs)} tools")
        
        # Ping all tools concurrently
        ping_tasks = [self.ping_tool(spec) for spec in specs]
        results = await asyncio.gather(*ping_tasks, return_exceptions=True)
        
        health_map = {}
        for result in results:
            if isinstance(result, HealthCheckResult):
                health_map[result.tool_name] = result
            elif isinstance(result, Exception):
                logger.error(f"Discovery task failed: {result}", exc_info=True)
        
        self._last_discovery = datetime.utcnow()
        
        healthy_count = sum(1 for r in health_map.values() if r.is_healthy)
        logger.info(
            f"Tool discovery complete: {healthy_count}/{len(health_map)} tools healthy"
        )
        
        return health_map
    
    def get_health_status(self, tool_name: str) -> Optional[HealthCheckResult]:
        """Get last known health status for a tool."""
        return self._health_results.get(tool_name)
    
    def get_all_health_statuses(self) -> Dict[str, HealthCheckResult]:
        """Get health statuses for all monitored tools."""
        return self._health_results.copy()
    
    def should_run_discovery(self) -> bool:
        """Check if discovery interval has elapsed."""
        if self._last_discovery is None:
            return True
        return datetime.utcnow() > self._last_discovery + timedelta(seconds=self.discovery_interval)
    
    def should_check_schemas(self) -> bool:
        """Check if schema check interval has elapsed."""
        if self._last_schema_check is None:
            return True
        return datetime.utcnow() > self._last_schema_check + timedelta(seconds=self.schema_check_interval)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get monitoring metrics summary."""
        total_tools = len(self._health_results)
        healthy_tools = sum(1 for r in self._health_results.values() if r.is_healthy)
        cached_tools = len(self._tool_cache)
        
        avg_response_time = 0.0
        if healthy_tools > 0:
            response_times = [
                r.response_time_ms
                for r in self._health_results.values()
                if r.is_healthy and r.response_time_ms > 0
            ]
            if response_times:
                avg_response_time = sum(response_times) / len(response_times)
        
        return {
            "total_tools": total_tools,
            "healthy_tools": healthy_tools,
            "unhealthy_tools": total_tools - healthy_tools,
            "cached_tools": cached_tools,
            "avg_response_time_ms": round(avg_response_time, 2),
            "last_discovery": self._last_discovery.isoformat() if self._last_discovery else None,
            "last_schema_check": self._last_schema_check.isoformat() if self._last_schema_check else None,
        }
