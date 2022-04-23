from typing import TYPE_CHECKING


from quara.wiring import Container
from .settings import AppSettings

AppContainer = Container[AppSettings]
