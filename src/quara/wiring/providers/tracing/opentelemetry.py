from __future__ import annotations

import functools
import typing as t

import fastapi
import fastapi.params
from quara.wiring.core.container import Container
from quara.wiring.core.settings import BaseAppSettings

if t.TYPE_CHECKING:
    from opentelemetry.util.types import AttributeValue


def get_span() -> fastapi.params.Depends:
    """Get the span associated with the request"""
    import opentelemetry.trace

    def span_dependency(request: fastapi.Request) -> opentelemetry.trace.Span:
        return opentelemetry.trace.get_current_span()

    return fastapi.Depends(span_dependency)


def get_span_context() -> fastapi.params.Depends:
    """Get the span context associated with the request"""
    import opentelemetry.context
    import opentelemetry.trace

    def context_dependency(request: fastapi.Request) -> opentelemetry.trace.SpanContext:
        return opentelemetry.context.get_current()

    return fastapi.Depends(context_dependency)


def get_tracer() -> fastapi.params.Depends:
    import opentelemetry.trace

    def tracer_dependency(request: fastapi.Request) -> opentelemetry.trace.Tracer:
        return request.app.state.tracer

    return tracer_dependency


def get_span_factory(
    span_name: t.Optional[str] = None,
    context_carrier: t.Optional[t.MutableMapping[str, str]] = None,
    context_getter: t.Optional[t.Mapping[str, str]] = None,
    attributes: t.Optional[t.Mapping[str, AttributeValue]] = None,
) -> fastapi.params.Depends:
    """Get a function which can be used to start a new span"""
    import opentelemetry.context
    import opentelemetry.propagate
    import opentelemetry.trace

    def span_factory(
        tracer: opentelemetry.trace.Tracer,
        span_name: t.Optional[str] = None,
        context_carrier: t.Optional[t.MutableMapping[str, str]] = None,
        context_getter: t.Optional[t.Mapping[str, str]] = None,
        attributes: t.Optional[t.Mapping[str, AttributeValue]] = None,
    ) -> t.Tuple[opentelemetry.trace.Span, t.Optional[object]]:
        """Create a new span"""
        token = ctx = span_kind = None
        if opentelemetry.trace.get_current_span() is opentelemetry.trace.INVALID_SPAN:
            ctx = opentelemetry.propagate.extract(
                context_carrier or {}, getter=context_getter or {}
            )
            token = opentelemetry.context.attach(ctx)
            span_kind = opentelemetry.trace.SpanKind.SERVER
        else:
            ctx = opentelemetry.context.get_current()
            span_kind = opentelemetry.trace.SpanKind.INTERNAL
        span = tracer.start_span(
            name=span_name,
            context=ctx,
            kind=span_kind,
            start_time=None,
            attributes=attributes,
        )
        return span, token

    def span_factory_dependency(
        request: fastapi.Request,
    ) -> t.Callable[..., t.Tuple[opentelemetry.trace.Span, t.Optional[object]]]:
        tracer = request.app.state.tracer
        # Return partial function
        return functools.partial(
            span_factory,
            tracer=tracer,
            span_name=span_name,
            context_carrier=context_carrier,
            context_getter=context_getter,
            attributes=attributes,
        )

    return fastapi.Depends(span_factory_dependency)


def openelemetry_traces_provider(
    container: Container[BaseAppSettings],
) -> t.Optional[t.List[t.Any]]:
    """Add opentelemetry traces to your application.

    See: https://opentelemetry.io/docs/instrumentation/python/exporters/
    """
    if not container.settings.telemetry.traces_enabled:
        return
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

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
    elif container.settings.telemetry.traces_exporter == "memory":
        exporter = InMemorySpanExporter()
    
    processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    # Set global tracer provider
    trace.set_tracer_provider(provider)
    # Create tracer
    tracer = trace.get_tracer(container.meta.name, container.meta.version, provider)
    # Store the tracer in the app for fast access
    container.app.state.tracer = tracer
    # Instrument app
    instrumentor = FastAPIInstrumentor()

    instrumentor.instrument_app(
        container.app,
        excluded_urls=container.settings.telemetry.ignore_path,
        tracer_provider=provider,
    )

    return [tracer, provider, instrumentor]
