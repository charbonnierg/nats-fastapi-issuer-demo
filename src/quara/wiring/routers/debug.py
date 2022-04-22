from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict, List, Optional

import fastapi

from quara.wiring.providers.oidc import UserClaims, get_user
from quara.wiring.core.settings import BaseAppSettings
from quara.wiring.core.container import Container



router = fastapi.APIRouter(
    prefix="/debug",
    tags=["Debug"],
    default_response_class=fastapi.responses.JSONResponse,
)


def conditional_router(
    container: Container[BaseAppSettings],
) -> Optional[fastapi.APIRouter]:
    global router
    if container.settings.server.debug:
        return router
    return None


@router.get("/settings", summary="Get application settings", response_model=BaseAppSettings)
async def get_settings(
    container: Container[BaseAppSettings] = fastapi.Depends(Container.provider),
    user: UserClaims = get_user(),
) -> BaseAppSettings:
    """Return application settings for debug purpose"""
    return container.settings


@router.get("/python", summary="Get infos about application environment")
async def get_environment(
    user: UserClaims = get_user(),
) -> Dict[str, Any]:
    """Return various infos about application environment for debugging purpose"""
    return {
        "executable": sys.executable,
        "platform": platform.uname()._asdict(),
        "sys_path": sys.path,
        "version": sys.version,
        "environment": dict(os.environ),
    }


@router.get("/hooks", summary="List hooks used by the application")
async def list_hooks(
    container: Container[BaseAppSettings] = fastapi.Depends(Container.provider),
    user: UserClaims = get_user(),
) -> List[Dict[str, Any]]:
    return container.submitted_hooks


@router.get("/tasks", summary="Get tasks status")
async def get_tasks_status(
    container: Container[BaseAppSettings] = fastapi.Depends(Container.provider),
    user: UserClaims = get_user(),
) -> List[Dict[str, Any]]:
    """Return application tasks status"""
    return [
        {
            "name": task.name,
            "started": task.started,
            "done": task.done,
            "cancelled": task.cancelled,
            "exception": str(task.exception) if task.exception else None,
        }
        for task in container.submitted_tasks.values()
    ]
