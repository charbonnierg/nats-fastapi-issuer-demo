from typing import Any, List, Optional

from wire.core.container import Container
from wire.core.settings import BaseAppSettings

from .router import create_debug_router


def debug_provider(container: Container[BaseAppSettings]) -> Optional[List[Any]]:
    """Provide additional endpoints to the application.

    When OIDC is enabled, those endpoints are protected.
    """
    if not container.settings.server.debug:
        # Return None when debug provider is disabled
        return None
    router = create_debug_router(container)
    container.app.include_router(router)
    # The debug router does not provide any additional resource
    return []
