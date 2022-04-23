from typing import Any, List, Optional

from wire.core.container import Container
from wire.core.settings import BaseAppSettings

from .router import create_debug_router


def debug_provider(container: Container[BaseAppSettings]) -> Optional[List[Any]]:
    # Create the new router
    router = create_debug_router(container)
    if router is None:
        return None
    # Include router in application
    container.app.include_router(router)
    return []
