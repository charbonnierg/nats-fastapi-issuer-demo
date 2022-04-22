from __future__ import annotations

from quara.wiring.core.settings import BaseAppSettings
from quara.wiring.core.container import Container

from .router import create_debug_router


def debug_provider(container: Container[BaseAppSettings]) -> None:
    # Create the new router
    router = create_debug_router(container)
    if router is None:
        return
    # Include router in application
    container.app.include_router(router)
