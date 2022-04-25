import pathlib
import typing as t

from pydantic import BaseSettings, Field, validator
from wire import BaseAppSettings


class MongoSettings(BaseSettings, case_sensitive=False, env_prefix="mongo_"):
    # Host and port are not supported, only URI
    uri: str = "mongodb://localhost:27017"
    # The default timeout of pymongo is 30 seconds which is way too long IMO
    # 3 seconds seems enough to determine whether database is reachable or not
    server_selection_timeout_ms: float = 3000
    # Useful for test and development
    # Should be disabled in production
    rs_initialize: bool = False
    rs_already_initialized_ok: bool = True
    rs_configuration: t.Union[str, pathlib.Path, t.Dict[str, t.Any], None] = None
    rs_enabled: bool = None  # type: ignore[assignment]

    @validator("rs_enabled", pre=False, always=True)
    def auto_value(cls, v: t.Any, values: t.Dict[str, t.Any]) -> t.Any:
        # Always accept user defined values
        if v is not None:
            return v
        # Auto value
        if "rs_initialize" in values and values["rs_initialize"]:
            # Replica set is enabled if we need to initialize it
            return True
        if "rs_configuration" in values and values["rs_configuration"] is not None:
            # If a configuration is provided, replica set should be enabled
            return True
        # Return false in all other cases
        return False


class MongoAppSettings(BaseAppSettings):
    mongo: MongoSettings = Field(default_factory=MongoSettings)
