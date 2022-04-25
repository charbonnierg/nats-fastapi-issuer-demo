import typing as t

from pydantic import BaseSettings, Field
from wire import BaseAppSettings


class NATSSettings(BaseSettings, case_sensitive=False, env_prefix="nats_"):
    # Host and port are not supported, only URI
    uri: str = "nats://localhost:4222"
    name: t.Optional[str] = None
    flusher_queue_size: t.Optional[int] = 1024
    flush_timeout_ms: t.Optional[float] = 60_000
    connection_timeout_ms: float = 2_000
    allow_reconnect: t.Optional[bool] = False
    reconnect_timewait_ms: float = 2_000
    max_reconnect_attempts: t.Optional[int] = None
    ping_interval: t.Optional[float] = None
    max_outstanding_pings: t.Optional[int] = None
    username: t.Optional[str] = None
    password: t.Optional[str] = None
    password_file: t.Optional[str] = None
    token: t.Optional[str] = None
    token_file: t.Optional[str] = None
    credentials: t.Optional[str] = None
    credentials_file: t.Optional[str] = None
    nkeys_seed: t.Optional[str] = None
    nkeys_seed_file: t.Optional[str] = None
    tls_hostname: t.Optional[str] = None
    tls_ca_cert_file: t.Optional[str] = None
    tls_cert_file: t.Optional[str] = None
    tls_key_file: t.Optional[str] = None


class NATSAppSettings(BaseAppSettings):
    nats: NATSSettings = Field(default_factory=NATSSettings)
