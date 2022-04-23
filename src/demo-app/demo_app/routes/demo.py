from typing import Callable, Optional, Tuple

import opentelemetry.trace
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from opentelemetry.trace import Span, Tracer
from opentelemetry.trace.status import Status, StatusCode
from wire import (
    AppMeta,
    Container,
    get_container,
    get_hook,
    get_meta,
    get_resource,
    get_settings,
)
from wire.core.settings import LogSettings
from wire.providers.oidc.provider import OIDCAuthProvider
from wire.providers.tracing.opentelemetry import get_span, get_span_factory
from structlog import get_logger

from demo_app.lib import Issuer
from demo_app.settings import AppSettings

logger = get_logger()
router = APIRouter(
    prefix="/demo",
    tags=["Demo"],
    default_response_class=JSONResponse,
)


@router.get("/")
async def get_many_deps(
    # Fetch tracer
    tracer: Tracer = get_resource(Tracer),
    # Fetch current span
    span: Span = get_span(),
    # Fetch span factory
    span_factory: Callable[..., Tuple[Span, Optional[object]]] = get_span_factory(
        span_name="demo-op"
    ),
    # Acces NATS issuer instance (provided by a issuer hook)
    issuer: Issuer = get_hook(Issuer),
    # Acces OIDC provider instance (provided by openid_connect provider)
    oidc: OIDCAuthProvider = get_resource(OIDCAuthProvider),
    # Access app container
    container: Container[AppSettings] = get_container(),
    # Access all app metadata
    meta: AppMeta = get_meta(),
    # Access a specific metadata
    version: str = get_meta("version"),
    # Access all app settings
    settings: AppSettings = get_settings(),
    # Access some specific settings
    logging_settings: LogSettings = get_settings(LogSettings),
) -> None:
    """This endpoint illustrate how to access many dependencies.

    The signature is as follow:

    ```python
    async def get_many_deps(
        # Fetch tracer
        tracer: Tracer = get_resource(Tracer),
        # Fetch span factory
        span_factory: Callable[..., Tuple[Span, Optional[object]]] = get_span_factory(span_name="demo-op"),
        # Acces NATS issuer instance (provided by a issuer hook)
        issuer: Issuer = get_hook(Issuer),
        # Acces OIDC provider instance (provided by openid_connect provider)
        oidc: OIDCAuthProvider = get_resource(OIDCAuthProvider),
        # Access app container
        container: Container[AppSettings] = get_container(),
        # Access all app metadata
        meta: AppMeta = get_meta(),
        # Access a specific metadata
        version: str = get_meta("version"),
        # Access all app settings
        settings: AppSettings = get_settings(),
        # Access some specific settings
        logging_settings: LogSettings = get_settings(LogSettings),
    ) -> None:
    ```
    """
    child_span, token = span_factory()
    with opentelemetry.trace.use_span(child_span, end_on_exit=True):
        logger.info(
            "Received request",
            tracer=tracer,
            issuer=issuer,
            container=container,
            meta=meta,
            settings=settings,
            oidc=oidc,
            version=version,
            logging_settings=logging_settings,
        )
        # Set child span (current span within handler) status
        child_span.set_status(status=Status(status_code=StatusCode.OK))
    # Set parent span (request span) status
    span.set_status(status=Status(status_code=StatusCode.OK))
