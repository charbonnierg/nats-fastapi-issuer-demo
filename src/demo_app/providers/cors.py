from __future__ import annotations

from starlette.middleware.cors import CORSMiddleware

from demo_app.container import AppContainer
from demo_app.settings import AppSettings


def cors_provider(container: AppContainer[AppSettings]) -> None:
    """Add CORS support to the application"""
    container.app.add_middleware(
        CORSMiddleware,
        allow_origins=container.settings.cors.allow_origins,
        allow_origin_regex=container.settings.cors.allow_origin_regex,
        allow_credentials=container.settings.cors.allow_credentials,
        allow_methods=container.settings.cors.allow_methods,
        allow_headers=container.settings.cors.allow_headers,
    )
