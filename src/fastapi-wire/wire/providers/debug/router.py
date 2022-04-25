# FIXME: Originally, this module dies not exist and all code was in __init__.py
# This is why there was a need for dynamic imports, I.E, import of optional dependencies first time they are used
# instead of global import time.
# Now, this module is imported by the debug provider only when it is enabled
# As such, it could be refactored into a simple FastAPI router defined globally.
# It would be more readable IMO
import asyncio
import inspect
import os
import platform
import sys
from io import StringIO
from typing import Any, Dict, List

import fastapi
from wire import BaseAppSettings, Container, get_container, get_settings
from wire.core.dependencies import get_meta
from wire.core.settings import AppMeta
from wire.core.utils import fullname
from wire.providers.oidc import get_user


def show_environment() -> Dict[str, Any]:
    """Gather various information regarding the host machine, the python interpreter and the environment."""
    return {
        "executable": sys.executable,
        "platform": platform.uname()._asdict(),
        "sys_path": sys.path,
        "version": sys.version,
        "environment": dict(os.environ),
    }


async def show_meta(
    meta: AppMeta = get_meta(),
) -> AppMeta:
    """Return application meta for debug purpose"""
    return meta


async def show_settings(
    settings: BaseAppSettings = get_settings(),
) -> BaseAppSettings:
    """Return application settings for debug purpose"""
    return settings


async def list_hooks(
    container: Container[BaseAppSettings] = get_container(),
) -> Dict[str, Any]:
    """Return a dict of hook names and hook types used found in application container"""
    # FIXME: This will fail if hook is not created using @asynccontextmanager
    # Logic to inspect hook should be refactored into a single function
    return {
        key: {
            "resource": fullname(value),
            "resource_file": inspect.getsourcefile(value.__class__),
            "hook": fullname(
                next(
                    hook for hook in container.hooks if hook.__name__ == key
                ).__wrapped__  # type: ignore[attr-defined]
            ),
            "hook_file": inspect.getsourcefile(
                next(
                    hook for hook in container.hooks if hook.__name__ == key
                ).__wrapped__  # type: ignore[attr-defined]
            ),
        }
        for key, value in container.submitted_hooks.items()
    }


async def list_providers(
    container: Container[BaseAppSettings] = get_container(),
) -> Dict[str, List[str]]:
    """Return a dict of provider names and provided resources found in application container"""
    # FIXME: Logc to inspect provider should be refactored into a single function
    # We should avoid looping several times or computing same values twice
    return {
        key: [
            {
                "resource": fullname(value),
                "resource_file": inspect.getsourcefile(value.__class__),
                "provider": fullname(
                    next(
                        provider
                        for provider in container.providers
                        if provider.__name__ == key
                    )
                ),
                "provider_file": inspect.getsourcefile(
                    next(
                        provider
                        for provider in container.providers
                        if provider.__name__ == key
                    )
                ),
            }
            for value in values
        ]
        for key, values in container.provided_resources.items()
    }


def list_tasks(
    container: Container[BaseAppSettings] = get_container(),
) -> List[Dict[str, Any]]:
    """Return a list with all tasks found in application container"""
    # FIXME: Logic to inspect task should be refactored into a single function
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


async def get_asyncio_summary() -> Dict[str, Any]:
    all_tasks = asyncio.all_tasks()
    tasks_infos: List[Any] = []
    for task in all_tasks:
        io = StringIO()
        task.print_stack(file=io)
        io.seek(0)
        tasks_infos.append(
            {
                "name": task.get_name(),
                "coro": task.get_coro().__qualname__,
                "stack": io.read().splitlines(False),
            }
        )
    return {"count": len(all_tasks), "tasks": tasks_infos}


def create_debug_router(
    container: Container[BaseAppSettings],
) -> fastapi.APIRouter:
    """Create a FastAPI router with debug endpoints."""

    # FIXME: Add an option in settings to configure roles with access to debug endpoints
    router_dependencies = [get_user()] if container.settings.oidc.enabled else []
    router = fastapi.APIRouter(
        prefix="/debug",
        tags=["Debug"],
        dependencies=router_dependencies,
    )

    router.get("/meta", summary="Get application meta", response_model=AppMeta)(
        show_meta
    )
    router.get(
        "/settings", summary="Get application settings", response_model=BaseAppSettings
    )(show_settings)
    router.get("/environment", summary="Get infos about application environment")(
        show_environment
    )
    router.get("/hooks", summary="List hooks used by the application")(list_hooks)
    router.get("/providers", summary="Get providers used by the application")(
        list_providers
    )
    router.get("/tasks", summary="Get tasks report")(list_tasks)
    router.get("/tasks/asyncio", summary="Inspect currently running asyncio tasks")(
        get_asyncio_summary
    )

    return router
