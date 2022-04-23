"""This module defines the application settings and metadata.

Note: Metadata are not parsed from environment.
"""
import pathlib
import typing

import pkg_resources
import pydantic

SettingsT = typing.TypeVar("SettingsT", bound="BaseAppSettings")


class AppMeta(pydantic.BaseModel):
    """Application metadata."""

    name: str = "app"
    title: str = "QUARA App"
    description: str = "Rest API application built using QUARA framework"
    package: typing.Optional[str] = None
    version: str = ""
    openapi_prefix: str = ""
    openapi_url: typing.Optional[str] = "/openapi.json"
    openapi_tags: typing.Optional[typing.List[typing.Dict[str, typing.Any]]] = None
    terms_of_service: typing.Optional[str] = None
    contact: typing.Optional[typing.Dict[str, typing.Union[str, typing.Any]]] = None
    license_info: typing.Optional[
        typing.Dict[str, typing.Union[str, typing.Any]]
    ] = None
    docs_url: typing.Optional[str] = "/docs"
    redoc_url: typing.Optional[str] = "/redoc"
    swagger_ui_oauth2_redirect_url: typing.Optional[str] = "/docs/oauth2-redirect"
    swagger_ui_init_oauth: typing.Optional[typing.Dict[str, typing.Any]] = None

    @pydantic.validator("version", pre=False, always=True)
    def auto_version(
        cls, v: typing.Any, values: typing.Dict[str, typing.Any]
    ) -> typing.Any:
        """Set version automatically if package is defined"""
        if v == "":
            if "package" in values and values["package"] is not None:
                return pkg_resources.get_distribution(values["package"]).version
            else:
                return ""
        else:
            return v


class ConfigFilesSettings(
    pydantic.BaseSettings, case_sensitive=False, env_prefix="config_"
):
    """Configuration related to files paths"""

    filepath: typing.Optional[str] = None


class ServerSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="server_"):

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8080
    debug: bool = False
    root_path: str = ""
    limit_concurrency: typing.Optional[int] = None
    limit_max_requests: typing.Optional[int] = None
    forwarded_allow_ips: typing.Optional[str] = None
    proxy_headers: bool = True
    server_header: bool = True
    date_header: bool = True


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
    traces_enabled: bool = True
    metrics_enabled: bool = True
    metrics_path: str = "/metrics"
    ignore_path: str = "metrics,docs,openapi.json"
    traces_exporter: typing.Literal["otlp", "console", "memory"] = "memory"


class OTLPSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="otlp_"):
    # Opentelemetry exporter configuration
    timeout: typing.Optional[int] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_TIMEOUT"
    )
    headers: typing.Optional[typing.Sequence[str]] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_HEADERS"
    )
    endpoint: typing.Optional[str] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_ENDPOINT"
    )
    compression: typing.Literal["none", "deflate", "gzip"] = pydantic.Field(
        None, env="OTEL_EXPORTER_OTLP_COMPRESSION"
    )


class OIDCSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="oidc_"):
    enabled: bool = False
    issuer_url: str = ""
    client_id: str = ""
    algorithms: typing.List[str] = ["RS256"]


class CORSSettings(pydantic.BaseSettings, case_sensitive=False, env_prefix="cors_"):
    allow_origins: typing.List[str] = ["*"]
    allow_methods: typing.List[str] = ["GET", "PATCH", "POST", "PUT", "DELETE", "HEAD"]
    allow_headers: typing.List[str] = []
    allow_credentials: bool = True
    allow_origin_regex: typing.Optional[str] = None
    expose_headers: typing.List[str] = []
    max_age: int = 600


class BaseAppSettings(
    pydantic.BaseSettings, case_sensitive=False, extra=pydantic.Extra.allow
):
    # Meta attribute can be overriden with a default value in child classes
    meta: AppMeta = pydantic.Field(default_factory=AppMeta)
    logging: LogSettings = pydantic.Field(default_factory=LogSettings)
    server: ServerSettings = pydantic.Field(default_factory=ServerSettings)
    telemetry: TelemetrySettings = pydantic.Field(default_factory=TelemetrySettings)
    otlp: OTLPSettings = pydantic.Field(default_factory=OTLPSettings)
    cors: CORSSettings = pydantic.Field(default_factory=CORSSettings)
    oidc: OIDCSettings = pydantic.Field(default_factory=OIDCSettings)

    @classmethod
    def merge(
        cls: typing.Type[SettingsT],
        override_settings: typing.Optional[SettingsT] = None,
        config_file: typing.Optional[typing.Union[str, pathlib.Path]] = None,
    ) -> SettingsT:
        """Parse application settings from file AND environment variables.

        Additionally, settings can be provided as a Settings instance.
        Those settings will take precedence over both environment and file settings.
        """
        files_settings = (
            ConfigFilesSettings(filepath=config_file)
            if config_file
            else ConfigFilesSettings()
        )
        if files_settings.filepath:
            # First parse file
            config_file_path = (
                pathlib.Path(files_settings.filepath).expanduser().resolve(True)
            )
            # Load settings from file
            app_settings_from_file = cls.parse_file(
                config_file_path, content_type="application/json"
            )
            # Load settings from env
            app_settings_from_env = cls()
            # Environment variables take precedence over file configuration
            app_settings = cls.parse_obj(
                _merge(
                    app_settings_from_file.dict(exclude_unset=True),
                    app_settings_from_env.dict(exclude_unset=True),
                )
            )
        else:
            app_settings = cls()
        # Override settings take precedence over both file configuration and environment variables
        if override_settings:
            app_settings = cls.parse_obj(
                _merge(
                    app_settings.dict(exclude_unset=True),
                    override_settings.dict(exclude_unset=True),
                )
            )
        # Return settings without override by default
        return app_settings


def _merge(
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
                _merge(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                a[key] = b[key]
        else:
            a[key] = b[key]
    return a
