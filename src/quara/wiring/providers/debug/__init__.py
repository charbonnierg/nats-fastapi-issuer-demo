from __future__ import annotations

from typing import Any, List, Optional

from quara.wiring.core.container import Container
from quara.wiring.core.settings import BaseAppSettings

from .router import create_debug_router


def debug_provider(container: Container[BaseAppSettings]) -> Optional[List[Any]]:
    # Create the new router
    router = create_debug_router(container)
    if router is None:
        return
    # Include router in application
    container.app.include_router(router)
    return []
