"""This module provides error handlers to use within FastAPI application."""
from __future__ import annotations

import sys
from typing import Any, Callable, Coroutine, Dict, Type, Union

from starlette.requests import Request
from starlette.responses import Response
from structlog import get_logger

logger = get_logger()


async def default_error_handler(err, request) -> None:
    exc_info = sys.exc_info()
    print(exc_info[-1].tb_lineno, exc_info[-1].tb_frame)
    logger.error("Failed to process request", exc_info=sys.exc_info())


ERROR_HANDLERS: Dict[
    Union[int, Type[Exception]], Callable[[Request, Any], Coroutine[Any, Any, Response]]
] = {Exception: default_error_handler}
