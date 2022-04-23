from wire.core.container import Container
from wire.core.settings import BaseAppSettings
from starlette.middleware.cors import CORSMiddleware


def cors_provider(container: Container[BaseAppSettings]) -> None:
    """Add CORS support to the application"""
    container.app.add_middleware(
        CORSMiddleware,
        allow_origins=container.settings.cors.allow_origins,
        allow_origin_regex=container.settings.cors.allow_origin_regex,
        allow_credentials=container.settings.cors.allow_credentials,
        allow_methods=container.settings.cors.allow_methods,
        allow_headers=container.settings.cors.allow_headers,
    )
