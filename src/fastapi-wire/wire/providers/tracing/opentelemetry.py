import functools
import typing as t

from fastapi import Depends, Request
from wire import BaseAppSettings, Container

AttributeValue = t.Union[
    str,
    bool,
    int,
    float,
    t.Sequence[str],
    t.Sequence[bool],
    t.Sequence[int],
    t.Sequence[float],
]


def get_span() -> t.Any:
    """Get the span associated with the request"""
    import opentelemetry.trace

    def span_dependency(request: Request) -> opentelemetry.trace.Span:
        return opentelemetry.trace.get_current_span()

    return Depends(dependency=span_dependency)


def get_span_context() -> t.Any:
    """Get the span context associated with the request"""
    import opentelemetry.context
    import opentelemetry.trace

    def context_dependency(request: Request) -> opentelemetry.context.Context:
        return opentelemetry.context.get_current()

    return Depends(dependency=context_dependency)


def get_tracer() -> t.Any:
    import opentelemetry.trace

    def tracer_dependency(request: Request) -> opentelemetry.trace.Tracer:
        return request.app.state.tracer  # type: ignore

    return Depends(dependency=tracer_dependency)


def get_span_factory(
    span_name: t.Optional[str] = None,
    context_carrier: t.Optional[t.MutableMapping[str, str]] = None,
    context_getter: t.Optional[t.Mapping[str, str]] = None,
    attributes: t.Optional[t.Mapping[str, AttributeValue]] = None,
) -> t.Any:
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
                carrier=context_carrier or {},
                getter=t.cast(
                    opentelemetry.propagate.textmap.Getter, context_getter or {}
                ),
            )
            token = opentelemetry.context.attach(ctx)
            span_kind = opentelemetry.trace.SpanKind.SERVER
        else:
            ctx = opentelemetry.context.get_current()
            span_kind = opentelemetry.trace.SpanKind.INTERNAL
        span = tracer.start_span(
            name=span_name or "default",
            context=ctx,
            kind=span_kind,
            start_time=None,
            attributes=attributes,
        )
        return span, token

    def span_factory_dependency(
        request: Request,
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

    return Depends(dependency=span_factory_dependency)


def openelemetry_traces_provider(
    container: Container[BaseAppSettings],
) -> t.Optional[t.List[t.Any]]:
    """Add opentelemetry traces to your application.

    See: https://opentelemetry.io/docs/instrumentation/python/exporters/
    """
    if not container.settings.telemetry.traces_enabled:
        return None
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    # Service name is required for most backends,
    # and although it's not necessary for console export,
    # it's good to set service name anyways.
    resource = Resource(attributes={SERVICE_NAME: container.meta.name})

    # Create a new tracer provider
    provider = TracerProvider(resource=resource)

    exporter: t.Union[OTLPSpanExporter, ConsoleSpanExporter, InMemorySpanExporter]
    if container.settings.telemetry.traces_exporter.lower() == "otlp":
        exporter = OTLPSpanExporter(
            timeout=container.settings.otlp.timeout,
            headers=container.settings.otlp.headers,
            compression=container.settings.otlp.compression,
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
