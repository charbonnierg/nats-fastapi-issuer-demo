import contextlib
import typing
from logging import getLogger

from nats.aio.client import Client as NATSClient
from wire import Container

from .nats_debug_router import router as debug_router
from .nats_utils import create_client
from .settings import NATSAppSettings

logger = getLogger(__name__)


@contextlib.asynccontextmanager
async def nats_client_hook(
    container: Container[NATSAppSettings],
) -> typing.AsyncIterator[NATSClient]:
    """Provide a NATS client for the application.

    Client is connected before applications starts and is drained on application shutdown
    """
    try:
        settings = container.settings.nats
    except AttributeError:
        logger.warning("Application does not provide settings for MongoDB hook")
        settings = None
    # Create a new client
    client = await create_client(settings, debug=container.settings.server.debug)
    # Include debug router when debug mode is enabled
    if container.settings.server.debug:
        container.app.include_router(debug_router)
    yield client
