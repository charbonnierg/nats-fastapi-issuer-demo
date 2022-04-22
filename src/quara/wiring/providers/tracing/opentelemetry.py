from __future__ import annotations

import typing as t

from quara.wiring.core.container import Container
from quara.wiring.core.settings import BaseAppSettings


def openelemetry_traces_provider(container: Container[BaseAppSettings]) -> None:
    """Add opentelemetry traces to your application.

    See: https://opentelemetry.io/docs/instrumentation/python/exporters/
    """
    if container.settings.telemetry.traces_enabled:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )

        # Service name is required for most backends,
        # and although it's not necessary for console export,
        # it's good to set service name anyways.
        resource = Resource(attributes={SERVICE_NAME: container.meta.name})

        # Create a new tracer provider
        provider = TracerProvider(resource=resource)

        exporter: t.Union[OTLPSpanExporter, ConsoleSpanExporter]
        if container.settings.telemetry.traces_exporter.lower() == "otlp":
            exporter = OTLPSpanExporter(
                timeout=container.settings.otlp.timeout,
                headers=container.settings.otlp.headers,
                compression=container.settings.otlp.compression,  # type: ignore[arg-type]
                endpoint=container.settings.otlp.endpoint,
            )
        else:
            exporter = ConsoleSpanExporter()

        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        # Set global tracer provider
        trace.set_tracer_provider(provider)

        # Instrument app
        FastAPIInstrumentor().instrument_app(
            container.app,
            excluded_urls=container.settings.telemetry.ignore_path,
            tracer_provider=provider,
        )
