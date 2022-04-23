import wire.providers
from wire import AppSpec
from wire.core.settings import AppMeta

from .hooks import issuer_hook
from .routes import demo_router, issuer_router, nats_router
from .settings import AppSettings

# The same spec is defined in the examples directory at the root of the git repo
#  - /examples/app.yaml
#  - /examples/app.ini
#  - /examples/app.json
# Using an AppSpec instance instead of a file let users start their application with several workers.
# This limitation might be worked around in the future.
spec = AppSpec(
    # Metadata are static, they cannot be updated on startup
    meta=AppMeta(
        name="demo_app",
        title="Demo App",
        description="A declarative FastAPI application 🎉",
        package="wire",
    ),
    # Settings are parsed on application startup from environment, file and arguments provided
    settings=AppSettings,
    # We do not control lifecycle of providers
    providers=[
        wire.providers.structured_logging_provider,
        wire.providers.prometheus_metrics_provider,
        wire.providers.openid_connect_provider,
        wire.providers.openelemetry_traces_provider,
        wire.providers.cors_provider,
        wire.providers.debug_provider,
    ],
    # App is responsible for starting routers
    # Routers can have their own lifecycle hooks
    routers=[issuer_router, nats_router, demo_router],
    # App is responsible for entering and exiting hooks
    hooks=[issuer_hook],
    # Default configuration file
    config_file="~/.quara.config.json",
)
