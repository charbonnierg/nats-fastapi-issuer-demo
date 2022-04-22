"""This module exposes the container holding the application.

Routers and hooks are registered in this module.
"""
from __future__ import annotations

import pathlib
import typing

from fastapi import FastAPI

from demo_app.settings import AppSettings

from .container import AppContainer, AppContainerSpec

# We can describe our application using import strings !
# This is extremely useful because it allows parsing application from JSON/YAML files
# We can imagine serverless functions in the future where dependencies are provided as a pyproject.toml or a requirements list
# Application could be described as a simple YAML file !
app_spec = AppContainerSpec(
    # Specify meta class
    meta="demo_app.settings.AppMeta",
    # Specify settings class
    settings="demo_app.settings.AppSettings",
    # Add routers
    routers=[
        "demo_app.routes.conditional_debug_router",
        "demo_app.routes.nats_router",
        "demo_app.routes.issuer_router",
    ],
    # Add hooks
    hooks=["demo_app.hooks.issuer.issuer_hook"],
    # Add providers
    providers=[
        # Add logger
        "demo_app.providers.logger.structured_logging_provider",
        # Add CORS
        "demo_app.providers.cors.cors_provider",
        # Add prometheus metrics (optional)
        "demo_app.providers.metrics.prometheus_metrics_provider",
        # Add traces (optional)
        "demo_app.providers.tracing.openelemetry_traces_provider",
        # Add OpenID Connect authentication (optional)
        "demo_app.providers.oidc.oidc_provider",
    ],
)


def create_container(
    settings: typing.Union[typing.Dict[str, typing.Any], AppSettings, None] = None,
    config_file: typing.Union[str, pathlib.Path, None] = None,
    meta: typing.Union[typing.Dict[str, typing.Any], AppSettings, None] = None,
) -> AppContainer[AppSettings]:
    """Application container factory. Useful because it returns a correctly annotated AppContainer.

    Returns:
        A new application container.
    """
    # Create an application container
    return app_spec.create_container(
        container_factory=AppContainer[AppSettings],
        meta=meta,
        settings=settings,
        config_file=config_file,
    )


def create_app(
    settings: typing.Union[typing.Dict[str, typing.Any], AppSettings, None] = None,
    config_file: typing.Union[str, pathlib.Path, None] = None,
    meta: typing.Union[typing.Dict[str, typing.Any], AppSettings, None] = None,
) -> FastAPI:
    """Application instance factory. Useful because it returns a FastAPI instance directly and can be used by uvicorn.

    Returns:
        A new application instance (fastapi.FastAPI).
    """
    return create_container(meta=meta, settings=settings, config_file=config_file).app
