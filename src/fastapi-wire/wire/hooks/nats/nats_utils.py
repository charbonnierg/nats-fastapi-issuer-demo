import asyncio
import pathlib
import ssl
import typing
from logging import getLogger

from nats.aio.client import Client as NATSClient
from wire.core.utils import TempDir

from .settings import NATSSettings

logger = getLogger(__name__)


async def create_client(
    settings: typing.Optional[NATSSettings] = None, debug: bool = False
) -> NATSClient:
    """Create a new NATS client using nats-py"""
    if settings is None:
        settings = NATSSettings()
    if debug:
        user_settings = settings.dict(exclude_unset=True)
        logger.warning(f"NATS settings detected: {repr(user_settings)}")
        logger.warning(f"NATS settings used: {settings.json()}")
    # Create client
    client = NATSClient()

    # Prepare connect options
    connect_options: typing.Dict[str, typing.Any] = {}

    # Gather flusher options
    if settings.flush_timeout_ms is not None:
        connect_options["flush_timeout"] = settings.flush_timeout_ms / 1000
    if settings.flusher_queue_size is not None:
        connect_options["flusher_queue_size"] = settings.flusher_queue_size
    # Gather reconnect options
    if settings.connection_timeout_ms is not None:
        connect_options["connect_timeout"] = settings.connection_timeout_ms / 1000
    if settings.allow_reconnect is not None:
        connect_options["allow_reconnect"] = settings.allow_reconnect
    if settings.reconnect_timewait_ms is not None:
        connect_options["reconnect_time_wait"] = settings.reconnect_timewait_ms / 1000
    if settings.max_reconnect_attempts is not None:
        connect_options["max_reconnect_attempts"] = settings.max_reconnect_attempts
    if settings.ping_interval is not None:
        connect_options["ping_interval"] = settings.ping_interval
    if settings.max_outstanding_pings is not None:
        connect_options["max_outstanding_pings"] = settings.max_outstanding_pings

    # Gather TLS options
    if settings.tls_hostname:
        connect_options["tls_hostname"] = settings.tls_hostname
    if settings.tls_cert_file or settings.tls_key_file:
        if settings.tls_key_file is None or settings.tls_key_file is None:
            raise ValueError(
                "Both tls_key_file and tls_cert_file must be provided when either of one is used."
            )
        # Create SSL context and load certificate files
        tls = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)
        if settings.tls_ca_cert_file is not None:
            tls.load_verify_locations(settings.tls_ca_cert_file)
        tls.load_cert_chain(
            certfile=settings.tls_cert_file, keyfile=settings.tls_key_file
        )
        # Set SSL context as tls option for connect method
        connect_options["tls"] = tls

    # Gather authentication options
    if settings.username:
        connect_options["user"] = settings.username
    if settings.password:
        connect_options["password"] = settings.password
    elif settings.password_file:
        connect_options["password"] = (
            pathlib.Path(settings.password_file).read_text().splitlines(False)[0]
        )
    elif settings.token:
        connect_options["token"] = settings.token
    elif settings.token_file:
        connect_options["token"] = (
            pathlib.Path(settings.token_file).read_text().splitlines(False)[0]
        )
    elif settings.credentials_file:
        connect_options["user_credentials"] = settings.credentials_file
    elif settings.nkeys_seed_file:
        connect_options["nkeys_seed"] = settings.nkeys_seed_file

    # Finally connect
    if settings.credentials:
        with TempDir() as directory:
            creds_file = directory.path.joinpath("creds")
            creds_file.write_bytes(settings.credentials.encode("utf-8"))
            connect_options["user_credentials"] = creds_file.resolve(True).as_posix()

            await asyncio.wait_for(
                client.connect(**connect_options),
                timeout=settings.connection_timeout_ms / 1000,
            )

    elif settings.nkeys_seed:
        with TempDir() as directory:
            seed_file = directory.path.joinpath("seed")
            seed_file.write_bytes(settings.nkeys_seed.encode("utf-8"))
            connect_options["nkeys_seed"] = seed_file.resolve(True).as_posix()

            await asyncio.wait_for(
                client.connect(**connect_options),
                timeout=settings.connection_timeout_ms / 1000,
            )

    else:
        await asyncio.wait_for(
            client.connect(**connect_options),
            timeout=settings.connection_timeout_ms / 1000,
        )

    return client


async def use_nats_client(
    settings: typing.Optional[NATSSettings] = None, debug: bool = False
) -> typing.AsyncIterator[NATSClient]:
    client = await create_client(settings, debug=debug)
    try:
        yield client
    finally:
        await client.drain()
