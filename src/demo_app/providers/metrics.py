from __future__ import annotations

from demo_app.container import AppContainer
from demo_app.settings import AppSettings


def prometheus_metrics_provider(container: AppContainer[AppSettings]) -> None:
    """Add prometheus metrics to your application."""
    if container.settings.telemetry.metrics_enabled:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator(
            excluded_handlers=[
                path.strip()
                for path in container.settings.telemetry.ignore_path.split(",")
            ]
        ).instrument(container.app).expose(
            container.app,
            endpoint=container.settings.telemetry.metrics_path,
            include_in_schema=True,
            tags=["Telemetry"],
        )
