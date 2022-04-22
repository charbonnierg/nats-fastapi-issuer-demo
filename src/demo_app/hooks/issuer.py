"""This module exposes custom hooks used by the application
"""
from __future__ import annotations

import contextlib
import typing

from starlette.requests import Request

from quara.wiring.core import Container

from demo_app.lib.issuer import Issuer, IssuerConfig
from demo_app.settings import AppSettings


@contextlib.asynccontextmanager
async def issuer_hook(
    container: Container[AppSettings],
) -> typing.AsyncIterator[Issuer]:
    """Setup issuer for the application"""
    # Parse config
    config = IssuerConfig.parse(
        account_signing_key_file=container.settings.issuer_files.account_signing_key_file,
        account_public_key_file=container.settings.issuer_files.account_public_key_file,
        account_signing_key=container.settings.issuer.account_signing_key,
        account_public_key=container.settings.issuer.account_public_key,
    )
    # Create issuer
    issuer = Issuer(config)
    # Store issuer in app
    container.app.state.issuer = issuer
    # Yield issuer
    yield issuer


def issuer(request: Request) -> Issuer:
    """Access the issuer from a Starlette/FastAPI request"""
    return request.app.state.issuer
