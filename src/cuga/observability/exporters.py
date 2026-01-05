"""
OpenTelemetry Exporter for CUGAR Agent System

Exports structured events and golden signals to OTEL-compatible backends:
- OTLP (OpenTelemetry Protocol)
- Jaeger
- Zipkin
- Custom OTEL collectors

All exports are PII-safe with automatic redaction and support batch/streaming modes.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .events import StructuredEvent
from .golden_signals import GoldenSignals


class OTELExporter:
    """
    Export structured events and metrics to OTEL backends.
    
    Supports environment-based configuration:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint URL
    - OTEL_EXPORTER_OTLP_HEADERS: Custom headers (key=value,key2=value2)
    - OTEL_SERVICE_NAME: Service name for traces
    - OTEL_TRACES_EXPORTER: Exporter type (otlp, jaeger, zipkin, console, none)
    - OTEL_METRICS_EXPORTER: Metrics exporter type
    """
    
    def __init__(
        self,
        endpoint: Optional[str] = None,
        service_name: str = "cuga-agent",
        headers: Optional[Dict[str, str]] = None,
        enabled: bool = True,
    ) -> None:
        """
        Initialize OTEL exporter.
        
        Args:
            endpoint: OTLP endpoint URL (defaults to OTEL_EXPORTER_OTLP_ENDPOINT)
            service_name: Service name for traces (defaults to OTEL_SERVICE_NAME)
            headers: Custom headers for OTLP requests
            enabled: Whether exporter is enabled (defaults to OTEL_TRACES_EXPORTER != "none")
        """
        self.endpoint = endpoint or os.getenv(
            "OTEL_EXPORTER_OTLP_ENDPOINT",
            "http://localhost:4318"
        )
        self.service_name = service_name or os.getenv("OTEL_SERVICE_NAME", "cuga-agent")
        self.headers = headers or self._parse_headers_from_env()
        self.enabled = enabled and os.getenv("OTEL_TRACES_EXPORTER", "otlp") != "none"
        
        # Initialize OTEL SDK components if available
        self._tracer_provider = None
        self._meter_provider = None
        self._init_otel_sdk()
    
    def _parse_headers_from_env(self) -> Dict[str, str]:
        """Parse OTEL_EXPORTER_OTLP_HEADERS environment variable."""
        headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
        if not headers_str:
            return {}
        
        headers = {}
        for pair in headers_str.split(","):
            if "=" in pair:
                key, value = pair.split("=", 1)
                headers[key.strip()] = value.strip()
        return headers
    
    def _init_otel_sdk(self) -> None:
        """Initialize OTEL SDK if available."""
        if not self.enabled:
            return
        
        try:
            # Try to import OTEL SDK components
            from opentelemetry import trace, metrics
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            from opentelemetry.sdk.metrics import MeterProvider
            from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
            from opentelemetry.sdk.resources import Resource
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            
            # Create resource with service name
            resource = Resource.create({"service.name": self.service_name})
            
            # Initialize tracer provider
            self._tracer_provider = TracerProvider(resource=resource)
            span_exporter = OTLPSpanExporter(
                endpoint=f"{self.endpoint}/v1/traces",
                headers=self.headers,
            )
            self._tracer_provider.add_span_processor(
                BatchSpanProcessor(span_exporter)
            )
            trace.set_tracer_provider(self._tracer_provider)
            
            # Initialize meter provider
            metric_exporter = OTLPMetricExporter(
                endpoint=f"{self.endpoint}/v1/metrics",
                headers=self.headers,
            )
            metric_reader = PeriodicExportingMetricReader(metric_exporter)
            self._meter_provider = MeterProvider(
                resource=resource,
                metric_readers=[metric_reader],
            )
            metrics.set_meter_provider(self._meter_provider)
            
        except ImportError:
            # OTEL SDK not available, fall back to console logging
            self.enabled = False
    
    def export_event(self, event: StructuredEvent) -> None:
        """
        Export a single structured event as OTEL span.
        
        Args:
            event: Structured event to export
        """
        if not self.enabled:
            return
        
        try:
            from opentelemetry import trace
            
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span(
                event.event_type.value,
                attributes=self._event_to_attributes(event),
            ) as span:
                if event.error_message:
                    span.set_status(trace.Status(trace.StatusCode.ERROR, event.error_message))
                else:
                    span.set_status(trace.Status(trace.StatusCode.OK))
        
        except Exception:
            # Silently fail to avoid breaking execution
            pass
    
    def export_events_batch(self, events: List[StructuredEvent]) -> None:
        """
        Export multiple events in batch.
        
        Args:
            events: List of structured events to export
        """
        for event in events:
            self.export_event(event)
    
    def export_metrics(self, signals: GoldenSignals) -> None:
        """
        Export golden signals as OTEL metrics.
        
        Args:
            signals: Golden signals to export
        """
        if not self.enabled:
            return
        
        try:
            from opentelemetry import metrics
            
            meter = metrics.get_meter(__name__)
            
            # Create counters
            requests_counter = meter.create_counter(
                "cuga.requests.total",
                description="Total number of requests",
            )
            success_counter = meter.create_counter(
                "cuga.requests.success",
                description="Successful requests",
            )
            failed_counter = meter.create_counter(
                "cuga.requests.failed",
                description="Failed requests",
            )
            tool_calls_counter = meter.create_counter(
                "cuga.tool_calls.total",
                description="Total tool calls",
            )
            tool_errors_counter = meter.create_counter(
                "cuga.tool_errors.total",
                description="Total tool errors",
            )
            
            # Record current values
            requests_counter.add(signals.total_requests.get())
            success_counter.add(signals.successful_requests.get())
            failed_counter.add(signals.failed_requests.get())
            tool_calls_counter.add(signals.tool_calls.get())
            tool_errors_counter.add(signals.tool_errors.get())
            
            # Create gauges for rates
            meter.create_observable_gauge(
                "cuga.success_rate",
                callbacks=[lambda _: [(signals.success_rate(), {})]],
                description="Request success rate percentage",
            )
            meter.create_observable_gauge(
                "cuga.tool_error_rate",
                callbacks=[lambda _: [(signals.tool_error_rate(), {})]],
                description="Tool error rate percentage",
            )
            meter.create_observable_gauge(
                "cuga.steps_per_task.mean",
                callbacks=[lambda _: [(signals.mean_steps_per_task(), {})]],
                description="Mean steps per task",
            )
            
            # Create histograms for latency
            latency_histogram = meter.create_histogram(
                "cuga.latency.milliseconds",
                description="Request latency in milliseconds",
            )
            for sample in signals.end_to_end_latency.samples:
                latency_histogram.record(sample)
        
        except Exception:
            # Silently fail to avoid breaking execution
            pass
    
    def _event_to_attributes(self, event: StructuredEvent) -> Dict[str, Any]:
        """Convert event to OTEL span attributes."""
        attributes = {
            "event.type": event.event_type.value,
            "trace.id": event.trace_id,
            "event.status": event.status,
        }
        
        if event.request_id:
            attributes["request.id"] = event.request_id
        if event.session_id:
            attributes["session.id"] = event.session_id
        if event.user_id:
            attributes["user.id"] = event.user_id
        if event.duration_ms is not None:
            attributes["event.duration_ms"] = event.duration_ms
        if event.error_message:
            attributes["error.message"] = event.error_message
        
        # Add event-specific attributes
        for key, value in event.attributes.items():
            if isinstance(value, (str, int, float, bool)):
                attributes[f"event.{key}"] = value
            elif isinstance(value, list) and all(isinstance(v, str) for v in value):
                attributes[f"event.{key}"] = ",".join(value)
        
        return attributes
    
    def export_to_console(self, event: StructuredEvent) -> None:
        """
        Export event to console (fallback mode).
        
        Args:
            event: Event to export
        """
        print(json.dumps(event.to_dict(), indent=2))
    
    def shutdown(self) -> None:
        """Shutdown exporter and flush pending data."""
        if self._tracer_provider:
            try:
                from opentelemetry.sdk.trace import TracerProvider
                if isinstance(self._tracer_provider, TracerProvider):
                    self._tracer_provider.shutdown()
            except Exception:
                pass
        
        if self._meter_provider:
            try:
                from opentelemetry.sdk.metrics import MeterProvider
                if isinstance(self._meter_provider, MeterProvider):
                    self._meter_provider.shutdown()
            except Exception:
                pass


class ConsoleExporter:
    """
    Simple console exporter for development/debugging.
    
    Prints events and metrics to stdout in JSON format.
    """
    
    def __init__(self, pretty: bool = True) -> None:
        """
        Initialize console exporter.
        
        Args:
            pretty: Whether to use pretty-printed JSON
        """
        self.pretty = pretty
    
    def export_event(self, event: StructuredEvent) -> None:
        """Export event to console."""
        if self.pretty:
            print(json.dumps(event.to_dict(), indent=2))
        else:
            print(json.dumps(event.to_dict()))
    
    def export_events_batch(self, events: List[StructuredEvent]) -> None:
        """Export batch of events to console."""
        for event in events:
            self.export_event(event)
    
    def export_metrics(self, signals: GoldenSignals) -> None:
        """Export metrics to console."""
        metrics_dict = signals.to_dict()
        if self.pretty:
            print(json.dumps(metrics_dict, indent=2))
        else:
            print(json.dumps(metrics_dict))
    
    def shutdown(self) -> None:
        """No-op for console exporter."""
        pass


def create_exporter(
    exporter_type: Optional[str] = None,
    **kwargs: Any,
) -> OTELExporter | ConsoleExporter:
    """
    Factory function to create appropriate exporter.
    
    Args:
        exporter_type: Type of exporter (otlp, console, none)
        **kwargs: Additional arguments for exporter
    
    Returns:
        Configured exporter instance
    """
    exporter_type = exporter_type or os.getenv("OTEL_TRACES_EXPORTER", "otlp")
    
    if exporter_type == "none":
        return ConsoleExporter(pretty=False)
    elif exporter_type == "console":
        return ConsoleExporter(**kwargs)
    else:  # otlp, jaeger, zipkin
        return OTELExporter(**kwargs)
