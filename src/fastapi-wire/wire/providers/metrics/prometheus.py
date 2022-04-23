from typing import Any, List, Optional

from wire.core.container import Container
from wire.core.settings import BaseAppSettings


def prometheus_metrics_provider(
    container: Container[BaseAppSettings],
) -> Optional[List[Any]]:
    """Add prometheus metrics to your application."""
    if not container.settings.telemetry.metrics_enabled:
        return None

    from prometheus_fastapi_instrumentator import Instrumentator

    instrumentor = Instrumentator(
        excluded_handlers=[
            path.strip() for path in container.settings.telemetry.ignore_path.split(",")
        ]
    )
    instrumentor.instrument(container.app).expose(
        container.app,
        endpoint=container.settings.telemetry.metrics_path,
        include_in_schema=True,
        tags=["Telemetry"],
    )

    return [instrumentor]
