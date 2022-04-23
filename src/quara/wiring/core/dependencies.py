from __future__ import annotations

import typing as t

import fastapi
import fastapi.params

if t.TYPE_CHECKING:
    from quara.wiring import AppMeta, AppTask, BaseAppSettings, Container


# FIXME: All those operations should be available from the container itself
# This way we could use methods in hooks/tasks/providers scopes and dependencies in endpoints.


def get_container() -> fastapi.params.Depends:
    """Provide the appication container from a FastAPI request."""

    def container_dependency(request: fastapi.Request) -> Container[BaseAppSettings]:
        """Provide the appication container from a FastAPI request."""
        return request.app.state.container

    return fastapi.Depends(container_dependency)


def get_settings(
    settingsT: t.Optional[t.Type[t.Any]] = None,
    default: t.Optional[t.Any] = ...,
) -> fastapi.params.Depends:
    """Provide the application settings from a FastAPI request."""

    def settings_dependency(request: fastapi.Request) -> BaseAppSettings:
        """Provide the application settings from a FastAPI request."""
        app_settings = request.app.state.container.settings
        if settingsT is None:
            return app_settings
        if isinstance(app_settings, settingsT):
            return app_settings
        else:
            for _, value in app_settings:
                if isinstance(value, settingsT):
                    return value
        if default is not ...:
            return default
        raise TypeError(f"Cannot find settings of type {settingsT}")

    return fastapi.Depends(settings_dependency)


def get_meta(
    key: t.Optional[str] = None, default: t.Optional[t.Any] = ...
) -> fastapi.params.Depends:
    """Get app metadata (either all metadata or a single key if an argument is provided)"""
    if key:
        if default is ...:

            def meta_dependency(request: fastapi.Request) -> t.Any:
                """Get a single app metadata field value"""
                try:
                    return getattr(request.app.state.container.meta, key)
                except AttributeError:
                    raise KeyError(f"Metadata field does not exist: {key}")

        else:

            def meta_dependency(request: fastapi.Request) -> t.Any:
                """Get a single app metadata field value"""
                return getattr(request.app.state.container.meta, key, default)

    else:

        def meta_dependency(request: fastapi.Request) -> AppMeta:
            """Get all app metadata"""
            return request.app.state.container.meta

    return fastapi.Depends(meta_dependency)


def get_task(name: str, default: t.Optional[t.Any] = ...) -> fastapi.params.Depends:
    """Provide a task instance from a FastAPI request."""

    if default is ...:

        def task_dependency(request: fastapi.Request) -> AppTask[t.Any]:
            """Provide a task instance from a FastAPI request."""
            return request.app.state.container.submitted_tasks[name]

    else:

        def task_dependency(request: fastapi.Request) -> AppTask[t.Any]:
            """Provide a task instance from a FastAPI request."""
            return request.app.state.container.submitted_tasks.get(name, default)

    return fastapi.Depends(task_dependency)


def get_tasks() -> fastapi.params.Depends:
    """Provide dict of tasks instances from a FastAPI request."""

    def tasks_dependency(request: fastapi.Request) -> t.Dict[str, AppTask[t.Any]]:
        """Provide a task instance from a FastAPI request."""
        return request.app.state.container.submitted_tasks

    return fastapi.Depends(tasks_dependency)


def get_hook(
    hookT: t.Type[t.Any],
    name: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> fastapi.params.Depends:
    """Provide a hook instance from a FastAPI request."""

    def hook_dependency(request: fastapi.Request) -> t.Any:
        """Provide a hook instance from a FastAPI request."""
        for hook_name, hook in request.app.state.container.submitted_hooks.items():
            if isinstance(hook, hookT):
                if name is None:
                    return hook
                if name.lower() == hook_name.lower():
                    return hook
        if default is not ...:
            return default
        raise TypeError(f"Cannot find hook of type {hookT}")

    return fastapi.Depends(hook_dependency)


def get_hooks() -> fastapi.params.Depends:
    """Provide a hook instance from a FastAPI request."""

    def hooks_dependency(request: fastapi.Request) -> t.Dict[str, t.Any]:
        """Provide a hook instance from a FastAPI request."""
        return request.app.state.container.submitted_hooks

    return fastapi.Depends(hooks_dependency)


def get_resource(
    resourceT: t.Type[t.Any],
    provider: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> fastapi.params.Depends:
    """Provide a resource instance from a FastAPI request."""

    def resource_dependency(request: fastapi.Request) -> t.Any:
        """Provide a resource instance from a FastAPI request."""
        for (
            provider_name,
            resources,
        ) in request.app.state.container.provided_resources.items():
            if provider is not None:
                if provider_name != provider:
                    continue
            for resource in resources:
                if isinstance(resource, resourceT):
                    if provider is None:
                        return resource
        if default is not ...:
            return default
        raise TypeError(f"Cannot find hook of type {resourceT}")

    return fastapi.Depends(resource_dependency)


def get_resources(
    provider: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> fastapi.params.Depends:
    """Provide a hook instance from a FastAPI request."""

    if provider is None:

        def resources_dependency(request: fastapi.Request) -> t.Dict[str, t.Any]:
            """Provide a hook instance from a FastAPI request."""
            return request.app.state.container.provided_resources

    elif default is not ...:

        def resources_dependency(request: fastapi.Request) -> t.Dict[str, t.Any]:
            """Provide a hook instance from a FastAPI request."""
            return request.app.state.container.provided_resources.get(provider, default)

    else:

        def resources_dependency(request: fastapi.Request) -> t.Dict[str, t.Any]:
            """Provide a hook instance from a FastAPI request."""
            return request.app.state.container.provided_resources[provider]

    return fastapi.Depends(resources_dependency)
