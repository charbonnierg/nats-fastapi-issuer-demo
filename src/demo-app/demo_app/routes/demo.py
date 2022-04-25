from typing import Callable, Optional, Tuple

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from structlog import get_logger
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

# OIDC related import
try:
    from wire.providers.oidc.provider import OIDCAuthProvider
except ModuleNotFoundError as err:
    raise ModuleNotFoundError(
        "Router requires the extra dependencies 'async-mongo', 'oidc' and 'telemetry'."
        "Install them using the command: 'pip install fastapi-wire[async-mongo,oidc,telemetry]'"
    ) from err
# Opentelemetry related import
try:
    import opentelemetry.trace
    from opentelemetry.trace import Span, Tracer
    from opentelemetry.trace.status import Status, StatusCode
    from wire.providers.tracing.opentelemetry import get_span, get_span_factory
except ModuleNotFoundError as err:
    raise ModuleNotFoundError(
        "Router requires the extra dependencies 'async-mongo', 'oidc' and 'telemetry'."
        "Install them using the command: 'pip install fastapi-wire[async-mongo,oidc,telemetry]'"
    ) from err
# MongoDB related imports
try:
    from motor.core import AgnosticCollection, AgnosticDatabase
    from wire.hooks.mongo.motor import get_collection, get_database
except ModuleNotFoundError as err:
    raise ModuleNotFoundError(
        "Router requires the extra dependencies 'async-mongo', 'oidc' and 'telemetry'."
        "Install them using the command: 'pip install fastapi-wire[async-mongo,oidc,telemetry]'"
    ) from err

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
    tracer: Tracer = get_resource(Tracer, default=None),
    # Fetch current span
    span: Span = get_span(),
    # Fetch span factory
    span_factory: Callable[..., Tuple[Span, Optional[object]]] = get_span_factory(
        span_name="demo-op"
    ),
    # Access mongodb database
    db: AgnosticDatabase = get_database("test"),
    # Access mongodb collection
    col: AgnosticCollection = get_collection("demo", db="test"),
    # Acces NATS issuer instance (provided by a issuer hook)
    issuer: Issuer = get_hook(Issuer),
    # Acces OIDC provider instance (provided by openid_connect provider)
    oidc: OIDCAuthProvider = get_resource(OIDCAuthProvider, default=None),
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
    """This endpoint illustrate how to access many dependencies."""
    child_span, token = span_factory()
    with opentelemetry.trace.use_span(child_span, end_on_exit=True):
        logger.info(
            "Received request",
            tracer=tracer,
            db=db,
            col=col,
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
