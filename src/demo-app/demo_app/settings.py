"""This module defines the application settings and metadata.

Note: Metadata are not parsed from environment.
"""
import pydantic
from wire.core import BaseAppSettings

from .lib import IssuerFilesSettings, IssuerSettings


class AppSettings(BaseAppSettings):
    """Application settings inherit from base settings.

    Only database settings is specific to this application.
    Eveything else can be shared between applications.
    """

    issuer: IssuerSettings = pydantic.Field(default_factory=IssuerSettings)
    issuer_files: IssuerFilesSettings = pydantic.Field(
        default_factory=IssuerFilesSettings
    )
