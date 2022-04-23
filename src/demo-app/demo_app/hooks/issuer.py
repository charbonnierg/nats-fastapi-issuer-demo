"""This module exposes custom hooks used by the application
"""
import contextlib
import typing

from wire import Container

from demo_app.lib import Issuer, IssuerConfig
from demo_app.settings import AppSettings


@contextlib.asynccontextmanager
async def issuer_hook(
    container: Container[AppSettings],
) -> typing.AsyncIterator[Issuer]:
    """Setup and yield issuer for the application"""
    # Parse config
    config = IssuerConfig.parse(
        account_signing_key_file=container.settings.issuer_files.account_signing_key_file,
        account_public_key_file=container.settings.issuer_files.account_public_key_file,
        account_signing_key=container.settings.issuer.account_signing_key,
        account_public_key=container.settings.issuer.account_public_key,
    )
    # Create issuer
    issuer = Issuer(config)
    # Yield issuer
    yield issuer
