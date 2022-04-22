"""This module exposes the container holding the application.

Routers and hooks are registered in this module.
"""
from __future__ import annotations

import pathlib
import typing

from fastapi import FastAPI

from demo_app.settings import AppSettings

from .container import AppContainer
from .hooks.issuer import issuer_hook
from .providers.cors import cors_provider
from .providers.logger import structured_logging_provider
from .providers.metrics import prometheus_metrics_provider
from .providers.oidc import oidc_provider
from .providers.tracing import openelemetry_traces_provider
from .routes import debug_router, issuer_router, nats_router


def create_container(
    settings: typing.Optional[AppSettings] = None,
    config_file: typing.Union[pathlib.Path, str, None] = None,
) -> AppContainer[AppSettings]:
    """Application container factory.

    Modify this function to include new routers, new hooks or new providers.

    Returns:
        A new application container.
    """
    # Create an application container
    return AppContainer(
        # Config file can be either a file, a path or None
        config_file=config_file,
        # Settings must be an instance of AppSettings
        settings=settings or AppSettings(),
        # Application routers
        routers=[
            # Router can be APIRouter instances
            issuer_router,
            nats_router,
            # Or functions. Function must either return None or an APIRouter instance
            lambda container: debug_router if container.settings.server.debug else None,
        ],
        # Hooks are coroutine functions which accept an application container and return an async context manager
        hooks=[issuer_hook],
        # Providers are functions which accept an application container and return None
        providers=[
            # Add logger
            structured_logging_provider,
            # Add CORS
            cors_provider,
            # Add prometheus metrics (optional)
            prometheus_metrics_provider,
            # Add traces (optional)
            openelemetry_traces_provider,
            # Add OpenID Connect authentication (optional)
            oidc_provider,
        ],
    )


def create_app(settings: typing.Optional[AppSettings] = None) -> FastAPI:
    """Application instance factory"""
    # Container is accessible from application state:
    # app = create_app()
    # app.state.container
    return create_container(settings).app
