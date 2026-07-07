"""OpenTelemetry tracing setup.

Configures standard tracing exporters to export telemetry data to
an OTLP Collector (like Prometheus/Grafana or LangSmith/Phoenix).
Shared across all projects and backends.
"""

import logging

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from common.config.settings import settings

logger = logging.getLogger("common.tracing")


def setup_tracing(service_name: Optional[str] = None) -> None:
    """Configures the global OpenTelemetry tracer provider and exporters.

    Args:
        service_name: Name of the service to register. If None, uses settings.
    """
    if service_name is None:
        service_name = settings.OTEL_SERVICE_NAME

    # Setup resource description
    resource = Resource.create(attributes={SERVICE_NAME: service_name})

    # Create tracer provider
    provider = TracerProvider(resource=resource)
    trace.set_tracer_provider(provider)

    # Configure OTLP grpc span exporter
    try:
        otlp_exporter = OTLPSpanExporter(
            endpoint=settings.OTEL_EXPORTER_OTLP_ENDPOINT,
            insecure=True,
        )
        processor = BatchSpanProcessor(otlp_exporter)
        provider.add_span_processor(processor)
        logger.info("OpenTelemetry OTLP exporter registered to %s", settings.OTEL_EXPORTER_OTLP_ENDPOINT)
    except Exception as e:
        logger.warning("Could not register OpenTelemetry OTLP exporter: %s", e)

    # Configure LangSmith if enabled
    if settings.LANGSMITH_TRACING and settings.LANGSMITH_API_KEY:
        import os
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.LANGSMITH_API_KEY
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT
        logger.info("LangSmith tracing enabled for project: %s", settings.LANGSMITH_PROJECT)
