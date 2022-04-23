"""A container is an object wrapping a FastAPI application which acts a single place to store
various configurations and resources.
It helps sharing resources accross routers or different objects, at different moment of the application life cycle.
"""
import asyncio
import types
import typing

if typing.TYPE_CHECKING:
    from .container import Container
    from .settings import BaseAppSettings


T = typing.TypeVar("T")


class AppTask(typing.Generic[T]):
    """A task which should run in background as long as application is running.

    This implementation is quite robust in a sense that task must be started before application startup is considered complete
    and task must be stopped before application shutdown is considered complete.

    It is also really easy to either get task status, stop, start, or restart task using a custom endpoint.
    """

    def __init__(
        self,
        function: typing.Callable[
            ["Container[BaseAppSettings]"], typing.Coroutine[typing.Any, typing.Any, T]
        ],
        name: typing.Optional[str] = None,
    ) -> None:
        self.function = function
        self.name = name or function.__name__
        self.task: typing.Optional[asyncio.Task[T]] = None
        self._result: typing.Optional[T] = None
        self._container: typing.Optional["Container[BaseAppSettings]"] = None

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

    async def wait(self, timeout: typing.Optional[float] = None) -> bool:
        """Wait until task is finished. Return True if task is finished, else False."""
        if self.task:
            _, pending = await asyncio.wait([self.task], timeout=timeout)
            return False if pending else True
        return False

    async def start(self) -> "AppTask[T]":
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

    async def __aenter__(self) -> "AppTask[T]":
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

    def bind(self, container: "Container[BaseAppSettings]") -> "AppTask[T]":
        """Bind the task to an application container"""
        self._container = container
        return self
