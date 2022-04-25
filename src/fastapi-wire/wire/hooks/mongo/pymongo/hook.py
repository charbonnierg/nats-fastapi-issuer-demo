import contextlib
import typing
from logging import getLogger

from pymongo import MongoClient
from wire import Container

from ..settings import MongoAppSettings
from .pymongo_debug_router import router as debug_router
from .pymongo_utils import create_client

logger = getLogger(__name__)


@contextlib.asynccontextmanager
async def pymongo_client_hook(
    container: Container[MongoAppSettings],
) -> typing.AsyncIterator[MongoClient]:
    """Provide a Motor client for the application.

    There is no need to manage connection using motor.
    """
    try:
        settings = container.settings.mongo
    except AttributeError:
        logger.warning("Application does not provide settings for MongoDB hook")
        settings = None
    # Create a new client
    client = create_client(settings, debug=container.settings.server.debug)
    # Include debug router when debug mode is enabled
    if container.settings.server.debug:
        container.app.include_router(debug_router)
    yield client
