from __future__ import annotations

import os
import platform
import sys
from typing import Any, Dict, List

import fastapi

from demo_app.providers.oidc import UserClaims, get_user

from ..container import AppContainer, AppSettings

router = fastapi.APIRouter(
    prefix="/debug",
    tags=["Debug"],
    default_response_class=fastapi.responses.JSONResponse,
)


@router.get("/settings", summary="Get application settings", response_model=AppSettings)
async def get_settings(
    settings: AppSettings = fastapi.Depends(AppSettings.provider),
    user: UserClaims = get_user(),
) -> AppSettings:
    """Return application settings for debug purpose"""
    return settings


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
    container: AppContainer = fastapi.Depends(AppContainer.provider),
    user: UserClaims = get_user(),
) -> List[Dict[str, Any]]:
    return container.submitted_hooks


@router.get("/tasks", summary="Get tasks status")
async def get_tasks_status(
    container: AppContainer = fastapi.Depends(AppContainer.provider),
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
