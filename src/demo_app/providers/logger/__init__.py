from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable, Union

import structlog
from starlette.requests import Request
from starlette.responses import Response
from uvicorn.config import LOG_LEVELS

from demo_app.container import AppContainer
from demo_app.settings import AppSettings

from ._log_levels import make_filtering_bound_logger


def structured_logging_provider(container: AppContainer[AppSettings]) -> None:
    """Add structured logger to the application."""
    if container.settings.telemetry.traces_enabled:
        from opentelemetry import trace

        tracer = trace.get_tracer(__name__)
    else:
        tracer = None
    level = container.settings.logging.level or "info"
    level_int = LOG_LEVELS[level.lower()]
    renderer: Union[structlog.dev.ConsoleRenderer, structlog.processors.JSONRenderer]
    if container.settings.logging.renderer == "console":
        renderer = structlog.dev.ConsoleRenderer(
            colors=container.settings.logging.colors
        )
    else:
        renderer = structlog.processors.JSONRenderer(sort_keys=True)
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.threadlocal.merge_threadlocal,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            renderer,
        ],
        wrapper_class=make_filtering_bound_logger(level_int),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logger = structlog.get_logger()

    class StructlogHandler(logging.Handler):
        """
        Feeds all events back into structlog.
        """

        def __init__(self, *args: Any, **kw: Any):
            super(StructlogHandler, self).__init__(*args, **kw)
            self._log = logger

        def emit(self, record: logging.LogRecord) -> None:
            if isinstance(record.msg, Exception):
                self._log.exception(record.msg, logger=record.name)
            if record.levelno >= 40:
                if container.settings.server.debug:
                    self._log.error(
                        record.msg % record.args,
                        logger=record.name,
                        exc_info=record.exc_info,
                    )
                elif record.exc_info:
                    self._log.error(
                        record.msg % record.args,
                        logger=record.name,
                        error_type=record.exc_info[0],
                        error=record.exc_info[1],
                    )
                else:
                    self._log.error(record.msg % record.args, logger=record.name)
            elif record.levelno >= 30:
                self._log.warning(record.msg % record.args, logger=record.name)
            elif record.levelno >= 20:
                self._log.info(record.msg % record.args, logger=record.name)
            else:
                self._log.debug(record.msg % record.args, logger=record.name)

    container.app.state.logger = logger

    def configure_standard_logging() -> None:
        standard_loggers = [
            logging.getLogger(name) for name in logging.root.manager.loggerDict
        ]
        for standard_logger in standard_loggers:
            if standard_logger.name == "uvicorn.access":
                continue
            while True:
                try:
                    handler = standard_logger.handlers[0]
                except IndexError:
                    break
                standard_logger.removeHandler(handler)

        logging.root.addHandler(StructlogHandler())

    configure_standard_logging()

    if container.settings.logging.access_log:

        @container.app.middleware("http")
        async def logging_middleware(
            request: Request, call_next: Callable[..., Awaitable[Response]]
        ) -> Response:
            # clear the threadlocal context
            structlog.threadlocal.clear_threadlocal()
            # bind threadlocal
            structlog.threadlocal.bind_threadlocal(
                logger="fastapi",
                http_version=request.scope.get("http_version", "unknown"),
            )
            # Check if a trace is available
            if tracer:
                span_context = trace.get_current_span().get_span_context()
                trace_id = span_context.trace_id
                span_id = span_context.span_id
                structlog.threadlocal.bind_threadlocal(
                    span_id=format(span_id, "02x"), trace_id=format(trace_id, "02x")
                )
            # Measure handler time
            start_time = time.time()
            try:
                response = await call_next(request)
            except Exception as err:
                process_time = time.time() - start_time
                if container.settings.server.debug:
                    request.app.state.logger.exception(err)
                else:
                    request.app.state.logger.error(
                        "Failed to process request",
                        process_time=process_time,
                        error_type=type(err).__name__,
                        error=repr(err),
                    )
                structlog.threadlocal.clear_threadlocal()
                return Response(
                    content=b'{"details": "Internal server error"}',
                    media_type="application/json",
                    status_code=500,
                )
            else:
                process_time = time.time() - start_time
                request.app.state.logger.info(
                    f"{request.method.upper()} - {request.scope['path']} - {':'.join(str(v) for v in request.scope['client'])}",
                    status_code=response.status_code,
                    process_time=process_time,
                )
                structlog.threadlocal.clear_threadlocal()
            return response


__all__ = ["structured_logging_provider"]
