"""This module defines the application settings and metadata.

Note: Metadata are not parsed from environment.
"""
from __future__ import annotations

import pathlib
import typing

import fastapi
import pkg_resources
import pydantic

from .lib.issuer import IssuerFilesSettings, IssuerSettings

SettingsT = typing.TypeVar("SettingsT", bound="BaseAppSettings")

PKG_NAME = "demo-app"
DEMO_DUMP = pathlib.Path(__file__).parent / "data" / "data_management.json"


class AppMeta(pydantic.BaseModel):
    """Application metadata."""

    name: str = "demo_app"
    title: str = "Demo App"
    description: str = "Demo FastAPI Application"
    version: str = pkg_resources.get_distribution(PKG_NAME).version


class ConfigFilesSettings(
    pydantic.BaseSettings, case_sensitive=False, env_prefix="config_"
):
    """Configuration related to files paths"""

    path: typing.Optional[str] = None


class ServerSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="server_"):

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    root_path: str = ""
    limit_concurrency: typing.Optional[int] = None
    limit_max_requests: typing.Optional[int] = None


class LogSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="logging_"):
    # Log settings
    access_log: bool = True
    level: typing.Optional[str] = None
    colors: bool = True
    renderer: typing.Literal["console", "json"] = "console"


class TelemetrySettings(
    pydantic.BaseSettings, case_sensitive=False, env_prefix="telemetry_"
):
    # Telemetry settings
    traces_enabled: bool = False
    metrics_enabled: bool = False
    metrics_path: str = "/metrics"
    ignore_path: str = "metrics,docs,openapi.json"
    traces_exporter: typing.Literal["otlp", "console"] = "console"


class OTLPSettings(pydantic.BaseSettings, env_prefix="otlp_"):
    # Opentelemetry exporter configuration
    timeout: typing.Optional[int] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_TIMEOUT"
    )
    headers: typing.Optional[typing.Dict[str, str]] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_HEADERS"
    )
    endpoint: typing.Optional[str] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    compression: typing.Literal["none", "deflate", "gzip"] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_COMPRESSION"
    )


class OIDCSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="oidc_"):
    enabled: bool = True
    issuer_url: str = "https://lemur-10.cloud-iam.com/auth/realms/demo-app"
    client_id: str = "demo-app"
    algorithms: typing.List[str] = ["RS256"]


class CORSSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="cors_"):
    allow_origins: typing.List[str] = ["*"]
    allow_methods: typing.List[str] = ["GET", "PATCH", "POST", "PUT", "DELETE", "HEAD"]
    allow_headers: typing.List[str] = []
    allow_credentials: bool = True
    allow_origin_regex: typing.Optional[str] = None
    expose_headers: typing.List[str] = []
    max_age: int = 600


class BaseAppSettings(pydantic.BaseSettings, case_sensitive=False):
    logging: LogSettings = pydantic.Field(default_factory=LogSettings)
    server: ServerSettings = pydantic.Field(default_factory=ServerSettings)
    telemetry: TelemetrySettings = pydantic.Field(default_factory=TelemetrySettings)
    otlp: OTLPSettings = pydantic.Field(default_factory=OTLPSettings)
    cors: CORSSettings = pydantic.Field(default_factory=CORSSettings)
    oidc: OIDCSettings = pydantic.Field(default_factory=OIDCSettings)

    @classmethod
    def from_config_file(
        cls: typing.Type[SettingsT],
        override_settings: typing.Optional[SettingsT] = None,
        config_file: typing.Optional[typing.Union[str, pathlib.Path]] = None,
    ) -> SettingsT:
        """Parse application settings from file AND environment variables.

        Additionally, settings can be provided as a Settings instance.
        Those settings will take precedence over both environment and file settings.
        """
        files_settings = (
            ConfigFilesSettings(path=config_file)
            if config_file
            else ConfigFilesSettings()
        )
        if files_settings.path:
            # First parse file
            config_file_path = pathlib.Path(files_settings.path).resolve(True)
            # Load settings from file
            app_settings_from_file = cls.parse_file(
                config_file_path, content_type="application/json"
            )
            # Load settings from env
            app_settings_from_env = cls()
            # Environment variables take precedence over file configuration
            app_settings = cls.parse_obj(
                merge(
                    app_settings_from_file.dict(exclude_unset=True),
                    app_settings_from_env.dict(exclude_unset=True),
                )
            )
        else:
            app_settings = cls()
        # Override settings take precedence over both file configuration and environment variables
        if override_settings:
            app_settings = cls.parse_obj(
                merge(
                    app_settings.dict(exclude_unset=True),
                    override_settings.dict(exclude_unset=True),
                )
            )
        # Return settings without override by default
        return app_settings

    @classmethod
    def provider(cls: typing.Type[SettingsT], request: fastapi.Request) -> SettingsT:
        """Provide the database fro a given FastAPI request."""
        return request.app.state.container.settings  # type: ignore[no-any-return]


class AppSettings(BaseAppSettings):
    """Application settings inherit from base settings.

    Only database settings is specific to this application.
    Eveything else can be shared between applications.
    """

    issuer: IssuerSettings = pydantic.Field(default_factory=IssuerSettings)
    issuer_files: IssuerFilesSettings = pydantic.Field(
        default_factory=IssuerFilesSettings
    )


def merge(
    a: typing.Dict[typing.Any, typing.Any],
    b: typing.Dict[typing.Any, typing.Any],
    path: typing.Optional[typing.List[str]] = None,
) -> typing.Dict[typing.Any, typing.Any]:
    """Merge dictionary b into dictionary a"""
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a
