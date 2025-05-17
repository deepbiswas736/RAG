"""
OpenTelemetry tracer configuration for the Kafka utility service.
"""

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.propagate import inject, extract
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
import logging

logger = logging.getLogger(__name__)

def configure_tracer(
    service_name: str,
    otlp_endpoint: str = "http://otel-collector:4317",
    sample_rate: float = 1.0
) -> None:
    """
    Configure OpenTelemetry tracer for the service.
    
    Args:
        service_name: Name of the service
        otlp_endpoint: Endpoint for OTLP exporter
        sample_rate: Sampling rate (0.0 to 1.0)
    """
    # Create resource with service info
    resource = Resource.create({
        SERVICE_NAME: service_name,
        "deployment.environment": "production",
        "service.version": "1.0.0",  # TODO: Get from package version
    })
    
    # Set up tracer provider
    provider = TracerProvider(resource=resource)
    
    # Configure OTLP exporter
    try:
        otlp_exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
    except Exception as e:
        logger.error(f"Failed to configure OTLP exporter: {e}")
        # Fallback to console exporter for development/debugging
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    
    # Set the tracer provider
    trace.set_tracer_provider(provider)
    
    # Set the global propagator to use W3C Trace Context
    trace.set_tracer_provider(provider)

def extract_context_from_message(headers: dict) -> dict:
    """
    Extract trace context from message headers.
    
    Args:
        headers: Message headers containing trace context
        
    Returns:
        Trace context dictionary
    """
    return TraceContextTextMapPropagator().extract(headers)

def inject_context_into_headers(headers: dict) -> dict:
    """
    Inject current trace context into message headers.
    
    Args:
        headers: Existing message headers
        
    Returns:
        Headers with trace context
    """
    TraceContextTextMapPropagator().inject(headers)
    return headers
