from __future__ import annotations

from quara.wiring import AppSpec
from quara.wiring.core.settings import AppMeta
import quara.wiring.providers

from .settings import AppSettings
from .routes import issuer_router, nats_router, demo_router
from .hooks import issuer_hook

spec = AppSpec(
    meta=AppMeta(
        name="demo_app",
        title="Demo App",
        description="A declarative FastAPI application 🎉",
        package="demo-app"
    ),
    settings=AppSettings,
    providers=[
        quara.wiring.providers.structured_logging_provider,
        quara.wiring.providers.prometheus_metrics_provider,
        quara.wiring.providers.openid_connect_provider,
        quara.wiring.providers.openelemetry_traces_provider,
        quara.wiring.providers.cors_provider,
        quara.wiring.providers.debug_provider,
    ],
    routers=[
        issuer_router, nats_router, demo_router
    ],
    hooks=[
        issuer_hook
    ],
    config_file="~/.quara.config.json"
)
