"""A container is an object wrapping a FastAPI application which acts a single place to store
various configurations and resources.
It helps sharing resources accross routers or different objects, at different moment of the application life cycle.
"""
from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import pathlib
import sys
import types
import typing

import fastapi
import uvicorn
from pydantic import BaseModel, PyObject

from .errors import ERROR_HANDLERS
from .settings import AppMeta, AppSettings, BaseAppSettings, ConfigFilesSettings

if typing.TYPE_CHECKING:
    from fastapi.testclient import TestClient


T = typing.TypeVar("T")
SettingsT = typing.TypeVar("SettingsT", bound=BaseAppSettings)
ContainerT = typing.TypeVar("ContainerT", bound="AppContainer")


@dataclasses.dataclass
class AppContainer(typing.Generic[SettingsT]):
    """A class which can be used to create new FastAPI applications.

    All fields have default values parsed from environment, file or constants.
    """

    # Application metadata
    meta: AppMeta = dataclasses.field(default_factory=AppMeta)
    # Application settings
    settings: SettingsT = dataclasses.field(
        default_factory=typing.cast(SettingsT, BaseAppSettings)
    )
    # Configuration file
    config_file: typing.Union[pathlib.Path, str, None] = dataclasses.field(
        default_factory=lambda: ConfigFilesSettings().path
    )
    # Routers
    routers: typing.List[
        typing.Union[
            fastapi.APIRouter,
            typing.Callable[[AppContainer], typing.Optional[fastapi.APIRouter]],
        ]
    ] = dataclasses.field(default_factory=list)
    # Hooks
    hooks: typing.List[
        typing.Callable[
            [AppContainer[SettingsT]],
            typing.Optional[typing.AsyncContextManager[typing.Any]],
        ]
    ] = dataclasses.field(default_factory=list)
    # Tasks
    tasks: typing.List[
        typing.Union[
            typing.Callable[
                [AppContainer[SettingsT]],
                typing.Coroutine[typing.Any, typing.Any, typing.Any],
            ],
            AppTask[typing.Any],
            typing.Callable[[AppContainer], typing.Optional[AppTask[typing.Any]]],
        ]
    ] = dataclasses.field(default_factory=list)
    # Providers
    providers: typing.List[
        typing.Callable[[AppContainer], None],
    ] = dataclasses.field(default_factory=list)

    # Fields below are created in the __post_init__ method
    stack: contextlib.AsyncExitStack = dataclasses.field(init=False, repr=False)
    app: fastapi.FastAPI = dataclasses.field(init=False, repr=False)
    server: uvicorn.Server = dataclasses.field(init=False, repr=False)
    submitted_hooks: typing.List[str] = dataclasses.field(init=False, repr=False)
    submitted_tasks: typing.Dict[str, AppTask[typing.Any]] = dataclasses.field(
        init=False, repr=False
    )

    def __post_init__(self) -> None:
        """Post-init processing of application container.

        The fastapi application and uvicorn server are created within this function.

        See: https://docs.python.org/3/library/dataclasses.html#post-init-processing
        """
        # Merge settings from env, file and __init__
        self.settings = AppSettings.from_config_file(
            override_settings=self.settings, config_file=self.config_file
        )
        # Create async exit stack
        self.stack = contextlib.AsyncExitStack()
        # Create app
        self.app = fastapi.FastAPI(
            title=self.meta.title,
            description=self.meta.description,
            version=self.meta.version,
            exception_handlers=ERROR_HANDLERS,
            swagger_ui_init_oauth={"clientId": "fastapi-demo-app-docs"},
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
        )
        # Create uvicorn server
        self.server = uvicorn.Server(uvicorn_config)
        # Initialize pending tasks
        self.submitted_tasks = {}
        self.submitted_hooks = []
        # Execute providers
        for provider in self.providers:
            provider(self)
        # Start stack on application startup
        self.app.add_event_handler("startup", self._start_stack)
        # Exit stack on application shutdown
        self.app.add_event_handler("shutdown", self._stop_stack)
        # Attach routers to app
        for router in self.routers:
            if isinstance(router, fastapi.APIRouter):
                self.app.include_router(router)
            # Routers can be callable returning either None or an APIRouter
            # It provides a simple mechanism to enable/disable routers according to config
            else:
                _router = router(self)
                if _router is not None:
                    self.app.include_router(_router)
        # Store the context in application state
        self.app.state.container = self

    async def _start_stack(self) -> None:
        """Enter hooks stack"""
        await self.stack.__aenter__()
        # Start all resources
        try:
            # Start hooks
            for hook in self.hooks:
                context = hook(self)
                if context is None:
                    continue
                # Resources have access to the container
                await self.stack.enter_async_context(context)
                self.submitted_hooks.append(hook.__name__)
            # Start tasks
            for task in self.tasks:
                _task: typing.Optional[AppTask[typing.Any]]
                if isinstance(task, AppTask):
                    _task = task.bind(self)
                elif asyncio.iscoroutinefunction(task):
                    _task = AppTask(task).bind(self)  # type: ignore[arg-type]
                else:
                    maybe_task = task(self)
                    _task = maybe_task.bind(self) if maybe_task is not None else None  # type: ignore[union-attr]
                if _task is None:
                    continue
                # Enter task context
                pending_task = await self.stack.enter_async_context(_task)
                self.submitted_tasks[pending_task.name] = pending_task
        # Exit async stack if some resource startup failed
        except Exception:
            exc_type, exc, tb = sys.exc_info()
            await self.stack.__aexit__(exc_type, exc, tb)
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

    @staticmethod
    def provider(request: fastapi.Request) -> AppContainer:
        """Provide the appication container from a FastAPI request."""
        return request.app.state.container  # type: ignore[no-any-return]

    @property
    def test_client(self) -> TestClient:
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


class AppTask(typing.Generic[T]):
    """A task which should run in background as long as application is running.

    This implementation is quite robust in a sense that task must be started before application startup is considered complete
    and task must be stopped before application shutdown is considered complete.

    It is also really easy to either get task status, stop, start, or restart task using a custom endpoint.
    """

    def __init__(
        self,
        function: typing.Callable[
            [AppContainer], typing.Coroutine[typing.Any, typing.Any, T]
        ],
        name: typing.Optional[str] = None,
    ) -> None:
        self.function = function
        self.name = name or function.__name__
        self.task: typing.Optional[asyncio.Task[T]] = None
        self._result: typing.Optional[T] = None
        self._container: typing.Optional[AppContainer] = None

    @property
    def started(self) -> bool:
        """Return True if task is started else False"""
        if self.task is None:
            return False
        if not self.task.done():
            return True
        return False

    @property
    def done(self) -> bool:
        """Return True if task is done else False"""
        if self.task is None:
            return False
        return self.task.done()

    @property
    def cancelled(self) -> bool:
        """Return True if task has been cancelled else False"""
        if self.task is None:
            return False
        return self.task.cancelled()

    @property
    def failed(self) -> bool:
        """Return True if task is done due to failure else False"""
        if self.exception is None:
            return False
        else:
            return True

    @property
    def succeeded(self) -> bool:
        """Return True if task is done without error else False"""
        return not self.failed

    @property
    def result(self) -> T:
        """Access task result"""
        if self.cancelled:
            raise asyncio.InvalidStateError("Task has been cancelled")
        if self.exception:
            raise asyncio.InvalidStateError("Task failed with error")
        if self.task is None:
            raise asyncio.InvalidStateError("Task is not started")
        if not self.done:
            raise asyncio.InvalidStateError("Task is still pending")
        # It's safe to return task result at this point
        return self.task.result()

    @property
    def exception(self) -> typing.Optional[BaseException]:
        """Access exception raised within task (if any)"""
        if self.task is None:
            return None
        if not self.task.done():
            return None
        if self.task.cancelled():
            return asyncio.CancelledError("Task cancelled")
        else:
            return self.task.exception()

    async def wait(self) -> bool:
        """Wait until task is finished. Return True if task is finished, else False."""
        if self.task:
            _, pending = await asyncio.wait([self.task], timeout=None)
            return False if pending else True
        return False

    async def start(self) -> AppTask[T]:
        """Start task"""
        if self._container is None:
            raise asyncio.InvalidStateError("No container has been attached to task")
        if not self.started:
            self.task = asyncio.create_task(self.function(self._container))
        return self

    async def stop(self) -> None:
        """Stop task"""
        if self.task is None:
            return
        if self.started:
            self.task.cancel()
            await self.wait()

    async def restart(self) -> None:
        await self.stop()
        await self.start()

    async def __aenter__(self) -> AppTask[T]:
        """Enter task context manager"""
        return await self.start()

    async def __aexit__(
        self,
        exc_type: typing.Optional[typing.Type[BaseException]] = None,
        exc: typing.Optional[BaseException] = None,
        tb: typing.Optional[types.TracebackType] = None,
    ) -> None:
        """Exit task context manager"""
        await self.stop()

    def bind(self, container: AppContainer) -> AppTask[T]:
        """Bind the task to an application container"""
        self._container = container
        return self

    @classmethod
    def Depends(cls, key: str) -> typing.Any:
        def get_task(request: fastapi.Request) -> AppTask[typing.Any]:
            return request.app.state.container.submitted_tasks[key]  # type: ignore[no-any-return]

        return fastapi.Depends(get_task)


class AppContainerSpec(BaseModel):
    meta: PyObject
    settings: PyObject
    routers: typing.List[PyObject] = []
    hooks: typing.List[PyObject] = []
    tasks: typing.List[PyObject] = []
    providers: typing.List[PyObject] = []
    config_file: typing.Union[str, pathlib.Path, None] = None

    @typing.overload
    def create_container(
        self,
        container_factory: typing.Type[ContainerT],
        meta: typing.Union[typing.Dict[str, typing.Any], BaseModel, None] = None,
        settings: typing.Union[typing.Dict[str, typing.Any], BaseModel, None] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> ContainerT:
        ...

    @typing.overload
    def create_container(
        self,
        container_factory: None = None,
        meta: typing.Union[typing.Dict[str, typing.Any], BaseModel, None] = None,
        settings: typing.Union[typing.Dict[str, typing.Any], BaseModel, None] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> AppContainer[BaseAppSettings]:
        ...

    def create_container(
        self,
        container_factory: typing.Optional[
            typing.Type[AppContainer[BaseAppSettings]]
        ] = None,
        meta: typing.Union[typing.Dict[str, typing.Any], BaseModel, None] = None,
        settings: typing.Union[typing.Dict[str, typing.Any], BaseModel, None] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> AppContainer[BaseAppSettings]:
        if isinstance(meta, BaseModel):
            meta = meta.dict(exclude_unset=True)
        elif meta is None:
            meta = {}
        if isinstance(settings, BaseModel):
            settings = settings.dict(exclude_unset=True)
        elif settings is None:
            settings = {}
        if container_factory is None:
            container_factory = AppContainer[BaseAppSettings]
        return container_factory(
            meta=self.meta(**meta),
            settings=self.settings(**settings),
            routers=self.routers,
            hooks=self.hooks,
            tasks=self.tasks,
            providers=self.providers,
            config_file=config_file or self.config_file,
        )
