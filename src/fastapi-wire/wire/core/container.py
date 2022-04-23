"""A container is an object wrapping a FastAPI application which acts a single place to store
various configurations and resources.
It helps sharing resources accross routers or different objects, at different moment of the application life cycle.
"""
import asyncio
import contextlib
import dataclasses
import pathlib
import sys
import typing

import uvicorn
from fastapi import APIRouter, FastAPI

from .settings import AppMeta, BaseAppSettings, ConfigFilesSettings
from .tasks import AppTask

if typing.TYPE_CHECKING:
    from fastapi.testclient import TestClient


T = typing.TypeVar("T")
SettingsT = typing.TypeVar("SettingsT", bound=BaseAppSettings)
ContainerT = typing.TypeVar("ContainerT", bound="Container[BaseAppSettings]")


@dataclasses.dataclass
class Container(typing.Generic[SettingsT]):
    """A class which can be used to create new FastAPI applications.

    All fields have default values parsed from environment, file or constants.
    """

    meta: AppMeta
    # Application settings
    settings: SettingsT
    # Configuration file
    config_file: typing.Union[pathlib.Path, str, None] = dataclasses.field(
        default_factory=lambda: ConfigFilesSettings().filepath
    )
    # Routers
    routers: typing.List[
        typing.Union[
            APIRouter,
            typing.Callable[["Container[BaseAppSettings]"], typing.Optional[APIRouter]],
        ]
    ] = dataclasses.field(default_factory=list)
    # Hooks
    hooks: typing.List[
        typing.Callable[
            ["Container[SettingsT]"],
            typing.Optional[typing.AsyncContextManager[typing.Any]],
        ]
    ] = dataclasses.field(default_factory=list)
    # Tasks
    tasks: typing.List[
        typing.Union[
            typing.Callable[
                ["Container[SettingsT]"],
                typing.Coroutine[typing.Any, typing.Any, typing.Any],
            ],
            AppTask[typing.Any],
            typing.Callable[
                ["Container[BaseAppSettings]"], typing.Optional[AppTask[typing.Any]]
            ],
        ]
    ] = dataclasses.field(default_factory=list)
    # Providers
    providers: typing.List[
        typing.Callable[
            ["Container[BaseAppSettings]"], typing.Optional[typing.List[typing.Any]]
        ],
    ] = dataclasses.field(default_factory=list)

    # Fields below are created in the __post_init__ method
    stack: contextlib.AsyncExitStack = dataclasses.field(init=False, repr=False)
    app: FastAPI = dataclasses.field(init=False, repr=False)
    server: uvicorn.Server = dataclasses.field(init=False, repr=False)
    submitted_hooks: typing.Dict[str, typing.Any] = dataclasses.field(
        init=False, repr=False
    )
    submitted_tasks: typing.Dict[str, AppTask[typing.Any]] = dataclasses.field(
        init=False, repr=False
    )
    provided_resources: typing.Dict[str, typing.List[typing.Any]] = dataclasses.field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Post-init processing of application container.

        The fastapi application and uvicorn server are created within this function.

        See: https://docs.python.org/3/library/dataclasses.html#post-init-processing
        """
        # Merge settings from env, file and __init__
        self.settings = self.settings.merge(self.settings, self.config_file)
        # Create async exit stack
        self.stack = contextlib.AsyncExitStack()
        # Create app
        # Prepare swagger_ui_init_auth
        if self.settings.oidc.enabled:
            if self.settings.oidc.client_id:
                if self.meta.swagger_ui_init_oauth is not None:
                    self.meta.swagger_ui_init_oauth[
                        "clientId"
                    ] = self.settings.oidc.client_id
                else:
                    self.meta.swagger_ui_init_oauth = {
                        "clientId": self.settings.oidc.client_id
                    }
        self.app = FastAPI(
            title=self.meta.title,
            description=self.meta.description,
            version=self.meta.version,
            openapi_prefix=self.meta.openapi_prefix,
            openapi_url=self.meta.openapi_url,
            openapi_tags=self.meta.openapi_tags,
            terms_of_service=self.meta.terms_of_service,
            contact=self.meta.contact,
            license_info=self.meta.license_info,
            docs_url=self.meta.docs_url,
            redoc_url=self.meta.redoc_url,
            swagger_ui_oauth2_redirect_url=self.meta.swagger_ui_oauth2_redirect_url,
            swagger_ui_init_oauth=self.meta.swagger_ui_init_oauth,
        )
        # Create uvicorn config
        uvicorn_config = uvicorn.Config(
            app=self.app,
            host=self.settings.server.host,
            port=self.settings.server.port,
            root_path=self.settings.server.root_path,
            debug=self.settings.server.debug,
            log_level=self.settings.logging.level.lower()
            if self.settings.logging.level
            else None,
            access_log=False,
            limit_concurrency=self.settings.server.limit_concurrency,
            limit_max_requests=self.settings.server.limit_max_requests,
            forwarded_allow_ips=self.settings.server.forwarded_allow_ips,
            proxy_headers=self.settings.server.proxy_headers,
            server_header=self.settings.server.server_header,
            date_header=self.settings.server.date_header,
        )
        # Create uvicorn server
        self.server = uvicorn.Server(uvicorn_config)
        # Initialize pending tasks
        self.submitted_tasks = {}
        self.submitted_hooks = {}
        self.provided_resources = {}
        # Create variable with proper annotation
        container = typing.cast(Container[BaseAppSettings], self)
        # Execute providers
        for provider in container.providers:
            # A provider might "provide" a list of resources, I.E, a list of objects of any type
            # It can also return an iterator of unknown length
            resources = provider(container)
            if resources is None:
                continue
            # Store resources so that they may be used later
            container.provided_resources[provider.__name__] = list(resources)
        # Start stack on application startup
        container.app.add_event_handler("startup", container._start_stack)
        # Exit stack on application shutdown
        container.app.add_event_handler("shutdown", container._stop_stack)
        # Attach routers to app
        for router in container.routers:
            if isinstance(router, APIRouter):
                container.app.include_router(router)
            # Routers can be callable returning either None or an APIRouter
            # It provides a simple mechanism to enable/disable routers according to config
            else:
                _router = router(container)
                if _router is not None:
                    container.app.include_router(_router)
        # Store the context in application state
        container.app.state.container = container

    async def _start_stack(self) -> None:
        """Enter hooks stack"""
        # Create variable with proper annotation
        container = typing.cast(Container[BaseAppSettings], self)
        await container.stack.__aenter__()
        # Start all resources
        try:
            # Start hooks
            for hook in container.hooks:
                context = hook(container)
                if context is None:
                    continue
                # Resources have access to the container
                container.submitted_hooks[
                    hook.__name__
                ] = await container.stack.enter_async_context(context)
            # Start tasks
            for task in container.tasks:
                _task: typing.Optional[AppTask[typing.Any]]
                if isinstance(task, AppTask):
                    _task = task.bind(container)
                elif asyncio.iscoroutinefunction(task):
                    _task = AppTask(task).bind(container)  # type: ignore[arg-type]
                else:
                    maybe_task = task(container)
                    _task = maybe_task.bind(container) if maybe_task is not None else None  # type: ignore[union-attr]
                if _task is None:
                    continue
                # Enter task context
                pending_task = await container.stack.enter_async_context(_task)
                container.submitted_tasks[pending_task.name] = pending_task
        # Exit async stack if some resource startup failed
        except Exception:
            exc_type, exc, tb = sys.exc_info()
            await container.stack.__aexit__(exc_type, exc, tb)
            raise

    async def _stop_stack(self) -> None:
        """Exit hooks stack"""
        exc_type, exc, tb = sys.exc_info()
        await self.stack.__aexit__(exc_type, exc, tb)

    def run(self) -> None:
        """Run the application as a blocking function."""
        self.server.run()

    async def run_async(self) -> None:
        """Run the application as a coroutine function."""
        await self.server.serve()

    def exit_soon(self) -> None:
        """Schedule application shutdown to run soon"""
        if self.server:
            self.server.should_exit = True

    @property
    def test_client(self) -> "TestClient":
        """Provide a quick access to a test client.

        The `fastapi.testclient.TestClient` class requires the `requests` package
        to be installed, which is not the case for `fastapi.Fastapi` class.
        This is why `TestClient` is imported when the first time property is accessed
        instead of when module is loaded.

        Note: Test client can only be accessed when debug mode is enabled.
        """
        if self.settings.server.debug:
            try:
                return self._testclient  # type: ignore[no-any-return, has-type]
            except AttributeError:
                from fastapi.testclient import TestClient

                self._testclient = TestClient(self.app)
                return self._testclient
        else:
            raise Exception("Test client is available only when debug is enabled")
