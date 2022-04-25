import json
import pathlib
import typing
from logging import getLogger

from bson import ObjectId
from motor.core import AgnosticClient
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import OperationFailure

from ..settings import MongoSettings

logger = getLogger(__name__)


def default_json_encoder(obj: typing.Any) -> typing.Any:
    """Useful when encoding object IDs to JSON"""
    if isinstance(obj, ObjectId):
        return str(obj)
    return obj


async def create_client(
    settings: typing.Optional[MongoSettings] = None, debug: bool = False
) -> AgnosticClient:
    """Create a new MongoDB client using motor.

    Client is of type `motor.asyncio.AsyncIOMotorClient` but returned type is annotated
    as `motor.core.AgnosticClient`.
    This is due to `motor.asyncio.AsyncIOMotorClient` class being created dynamically, and not being annotated,
    which lead both mypy or VSCode to know almost nothing about the class.
    `motor.core.AgnosticClient` on the other hand is defined statically in a module, so autocomplete
    and basic type checking are possible.

    >>> c = create_client()
    >>> isinstance(c, AgnosticClient)
    True
    >>> isinstance(c, AsyncIOMotorClient)
    True
    """
    if settings is None:
        settings = MongoSettings()
    if debug:
        user_settings = settings.dict(exclude_unset=True)
        logger.warning(f"MongoDB settings detected: {repr(user_settings)}")
        logger.warning(f"MongoDB settings used: {settings.json()}")
    # Prepare additional keyword arguments
    kwargs: typing.Dict[str, typing.Any] = {}
    if settings.server_selection_timeout_ms is not None:
        kwargs["serverSelectionTimeoutMS"] = settings.server_selection_timeout_ms
    # Create client
    client = AsyncIOMotorClient(settings.uri, **kwargs)
    # Optionally make sure replica set is initialized
    if settings.rs_initialize:
        # This will make sure that MongoDB server is reachable
        await enable_replica_set(
            client,
            configuration=settings.rs_configuration,
            already_initialized_ok=settings.rs_already_initialized_ok,
        )
    if settings.rs_enabled:
        # First check that replica set is initialized
        status = await get_replicate_set_status(client)
        if status is None:
            raise Exception(
                "Expected replica set to be enabled but replica set is not initialized and auto initialization is not enabled"
            )
        # Then check that replica set status is OK
        if status.get("ok", False) != 1:
            raise Exception(
                f"Expected replica set to be enabled but replica set status is not OK: {status}"
            )
        if debug:
            logger.warning("Replica set status OK")
    # Yield the client
    return client


async def enable_replica_set(
    client: AgnosticClient,
    configuration: typing.Union[
        typing.Dict[str, typing.Any], str, pathlib.Path, None
    ] = None,
    already_initialized_ok: bool = True,
) -> typing.Dict[str, typing.Any]:
    """Enable replica set. Useful for bootstraping databases during tests.

    If a path instance or a string is provided as configuration, value is expected to point to
    a valid JSON file holding replica set configuration.
    By default no configuration is provided.
    """
    # Check if replica set is already initialized
    rs_status = await get_replicate_set_status(client)
    if rs_status is not None:
        # Raise an error if that's not ok
        if not already_initialized_ok:
            raise Exception("Cannot initialize replica set: already initialized.")
        else:
            # Return replica set status
            return rs_status
    # In order to known which command use, open a mongo shell, and enter a command without parenthesis:
    # For example:
    # > rs.initiate
    # (note that rs.initiate is used instead of `rs.initiate()`. It's because we're interested in source code only.)
    # will print:
    #   function (c) {
    #       return db._adminCommand({replSetInitiate: c});
    #   }
    # That's how we known that the command to use is "replSetInitiate"
    CMD = "replSetInitiate"
    # Parse the configuration
    if isinstance(configuration, str):
        # Transform string into Path
        configuration = pathlib.Path(configuration)
    if isinstance(configuration, pathlib.Path):
        # Load config from path
        rs_config = json.loads(configuration.read_text())
    elif configuration is None:
        # Default configuration is empty
        rs_config = {}
    else:
        # Make a shallow copy
        rs_config = configuration.copy()
    # Run command using configuration
    logger.warning(f"Initializing replica set with config: {repr(rs_config)}")
    res = await client.admin.command({CMD: rs_config})
    # Send replica set status as return value
    if res.get("ok", False) == 1:
        return await get_replicate_set_status(client)
    else:
        raise Exception(f"Failed to enable replica set: {repr(res)}")


async def get_replicate_set_status(
    client: AgnosticClient,
) -> typing.Optional[typing.Dict[str, typing.Any]]:
    """Get replica set status.

    Returns None when replica set is not initialized.
    """
    cmd = "replSetGetStatus"
    try:
        return await client.admin.command(cmd)  # type: ignore[no-any-return]
    except OperationFailure as err:
        # 'errmsg': 'no replset config has been received', 'code': 94, 'codeName': 'NotYetInitialized'
        if err.code == 94:
            return None
        raise


async def get_replicate_set_config(
    client: AgnosticClient,
) -> typing.Optional[typing.Dict[str, typing.Any]]:
    """Get replica set status.

    Returns None when replica set is not initialized.
    """
    CMD = "replSetGetConfig"
    try:
        return await client.admin.command({CMD: 1})
    except OperationFailure as err:
        # 'errmsg': 'no replset config has been received', 'code': 94, 'codeName': 'NotYetInitialized'
        if err.code == 94:
            return None
        raise
