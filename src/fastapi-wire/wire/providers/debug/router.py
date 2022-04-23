import os
import platform
import sys
from typing import Any, Dict, List, Optional

import fastapi
from wire import BaseAppSettings, Container, get_container, get_settings
from wire.core.utils import fullname
from wire.providers.oidc import get_user


def _get_environment() -> Dict[str, Any]:
    return {
        "executable": sys.executable,
        "platform": platform.uname()._asdict(),
        "sys_path": sys.path,
        "version": sys.version,
        "environment": dict(os.environ),
    }


def _get_tasks_status(container: Container[BaseAppSettings]) -> List[Dict[str, Any]]:
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


def create_debug_router(
    container: Container[BaseAppSettings],
) -> Optional[fastapi.APIRouter]:

    if not container.settings.server.debug:
        return None

    router = fastapi.APIRouter(
        prefix="/debug",
        tags=["Debug"],
        default_response_class=fastapi.responses.JSONResponse,
        # Require authentication when OIDC is enabled
        # FIXME: Add an option in settings to configure roles with access to debug endpoints
        dependencies=[get_user()] if container.settings.oidc.enabled else [],
    )

    @router.get(
        "/settings", summary="Get application settings", response_model=BaseAppSettings
    )
    async def show_settings(
        settings: BaseAppSettings = get_settings(),
    ) -> BaseAppSettings:
        """Return application settings for debug purpose"""
        return settings

    @router.get("/environment", summary="Get infos about application environment")
    async def show_environment() -> Dict[str, Any]:
        """Return various infos about application environment for debugging purpose"""
        return _get_environment()

    @router.get("/hooks", summary="List hooks used by the application")
    async def list_hooks(
        container: Container[BaseAppSettings] = get_container(),
    ) -> Dict[str, str]:
        return {
            key: fullname(value) for key, value in container.submitted_hooks.items()
        }

    @router.get("/providers", summary="Get providers used by the application")
    async def list_providers(
        container: Container[BaseAppSettings] = get_container(),
    ) -> Dict[str, List[str]]:
        """Return application tasks status"""
        return {
            key: [fullname(value) for value in values]
            for key, values in container.provided_resources.items()
        }

    @router.get("/tasks", summary="Get tasks status")
    async def get_tasks_status(
        container: Container[BaseAppSettings] = get_container(),
    ) -> List[Dict[str, Any]]:
        """Return application tasks status"""
        return _get_tasks_status(container)

    return router
