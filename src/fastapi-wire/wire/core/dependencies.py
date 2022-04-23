import typing as t

from fastapi import Depends, Request
from pydantic import BaseSettings
from wire.core.container import Container
from wire.core.settings import BaseAppSettings
from wire.core.tasks import AppTask

# FIXME: All those operations should be available from the container itself
# This way we could use methods in hooks/tasks/providers scopes and dependencies in endpoints.


def get_container() -> t.Any:
    """Provide the appication container from a FastAPI request."""

    def container_dependency(request: Request) -> Container[BaseAppSettings]:
        """Provide the appication container from a FastAPI request."""
        return request.app.state.container  # type: ignore[no-any-return]

    return Depends(dependency=container_dependency)


def get_settings(
    settingsT: t.Optional[t.Type[BaseSettings]] = None,
    default: t.Optional[BaseSettings] = ...,  # type: ignore[assignment]
) -> t.Any:
    """Provide the application settings from a FastAPI request."""

    def settings_dependency(
        request: Request,
    ) -> t.Optional[BaseSettings]:
        """Provide the application settings from a FastAPI request."""
        container: Container[BaseAppSettings] = request.app.state.container
        app_settings = container.settings
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

    return Depends(dependency=settings_dependency)


def get_meta(
    key: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> t.Any:
    """Get app metadata (either all metadata or a single key if an argument is provided)"""
    if key:
        attr_key = key
        if default is ...:

            def meta_dependency(
                request: Request,
            ) -> t.Any:
                """Get a single app metadata field value"""
                container: Container[BaseAppSettings] = request.app.state.container
                try:
                    return getattr(container.meta, attr_key)
                except AttributeError:
                    raise KeyError(f"Metadata field does not exist: {attr_key}")

        else:

            def meta_dependency(
                request: Request,
            ) -> t.Any:
                """Get a single app metadata field value"""
                container: Container[BaseAppSettings] = request.app.state.container
                return getattr(container.meta, attr_key, default)

    else:

        def meta_dependency(
            request: Request,
        ) -> t.Any:
            """Get all app metadata"""
            container: Container[BaseAppSettings] = request.app.state.container
            return container.meta

    return Depends(dependency=meta_dependency)


def get_task(
    name: str,
    default: t.Optional[AppTask[t.Any]] = ...,  # type: ignore[assignment]
) -> t.Any:
    """Provide a task instance from a FastAPI request."""

    if default is ...:

        def task_dependency(
            request: Request,
        ) -> t.Optional[AppTask[t.Any]]:
            """Provide a task instance from a FastAPI request."""
            container: Container[BaseAppSettings] = request.app.state.container
            return container.submitted_tasks[name]

    else:

        def task_dependency(
            request: Request,
        ) -> t.Optional[AppTask[t.Any]]:
            """Provide a task instance from a FastAPI request."""
            container: Container[BaseAppSettings] = request.app.state.container
            return container.submitted_tasks.get(name, default)

    return Depends(dependency=task_dependency)


def get_tasks() -> t.Any:
    """Provide dict of tasks instances from a FastAPI request."""

    def tasks_dependency(
        request: Request,
    ) -> t.Dict[str, AppTask[t.Any]]:
        """Provide a task instance from a FastAPI request."""
        container: Container[BaseAppSettings] = request.app.state.container
        return container.submitted_tasks

    return Depends(dependency=tasks_dependency)


def get_hook(
    hookT: t.Type[t.Any],
    name: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> t.Any:
    """Provide a hook instance from a FastAPI request."""

    def hook_dependency(
        request: Request,
    ) -> t.Optional[t.Any]:
        """Provide a hook instance from a FastAPI request."""
        container: Container[BaseAppSettings] = request.app.state.container
        for hook_name, hook in container.submitted_hooks.items():
            if isinstance(hook, hookT):
                if name is None:
                    return hook
                if name.lower() == hook_name.lower():
                    return hook
        if default is not ...:
            return default
        raise TypeError(f"Cannot find hook of type {hookT}")

    return Depends(dependency=hook_dependency)


def get_hooks() -> t.Any:
    """Provide a hook instance from a FastAPI request."""

    def hooks_dependency(
        request: Request,
    ) -> t.Dict[str, t.Any]:
        """Provide a hook instance from a FastAPI request."""
        container: Container[BaseAppSettings] = request.app.state.container
        return container.submitted_hooks

    return Depends(dependency=hooks_dependency)


def get_resource(
    resourceT: t.Type[t.Any],
    provider: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> t.Any:
    """Provide a resource instance from a FastAPI request."""

    def resource_dependency(
        request: Request,
    ) -> t.Optional[t.Any]:
        """Provide a resource instance from a FastAPI request."""
        container: Container[BaseAppSettings] = request.app.state.container
        for (
            provider_name,
            resources,
        ) in container.provided_resources.items():
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

    return Depends(dependency=resource_dependency)


def get_resources(
    provider: t.Optional[str] = None,
    default: t.Optional[t.Any] = ...,
) -> t.Any:
    """Provide a hook instance from a FastAPI request."""

    if provider is None:

        def resources_dependency(
            request: Request,
        ) -> t.Optional[t.Dict[str, t.List[t.Any]]]:
            """Provide a hook instance from a FastAPI request."""
            container: Container[BaseAppSettings] = request.app.state.container
            return container.provided_resources

    else:
        provider_name = provider

        if default is not ...:
            default_value = default

            def resources_dependency(
                request: Request,
            ) -> t.Optional[t.Dict[str, t.List[t.Any]]]:
                """Provide a hook instance from a FastAPI request."""
                container: Container[BaseAppSettings] = request.app.state.container
                return {
                    provider_name: container.provided_resources.get(
                        provider_name, t.cast(t.List[t.Any], default_value)
                    )
                }

        else:

            def resources_dependency(
                request: Request,
            ) -> t.Optional[t.Dict[str, t.List[t.Any]]]:
                """Provide a hook instance from a FastAPI request."""
                container: Container[BaseAppSettings] = request.app.state.container
                return {provider_name: container.provided_resources[provider_name]}

    return Depends(resources_dependency)
