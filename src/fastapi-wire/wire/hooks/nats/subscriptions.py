import typing as t
from datetime import datetime, timezone

from nats.aio.client import Client
from nats.aio.msg import Msg
from wire.core.injection import DependencyInjector
from wire.hooks.nats.subjects import substitute_placeholder_tokens

T = t.TypeVar("T")


# # Some types which can be used to annotate parameters
class Subject(str):
    pass


class Reply(str):
    pass


class _Token:
    __slots__ = ["index"]

    def __init__(self, index: int):
        self.index = index

    def __call__(self, msg: Msg) -> str:
        return msg.subject.split(".")[self.index]


class _Header:
    __slots__ = ["key"]

    def __init__(self, key: str):
        self.key = key

    def __call__(self, msg: Msg) -> str:
        return msg.headers[self.key]


class _Depends:
    __slots__ = ["dependency", "resolved_dependency"]

    def __init__(self, dependency: t.Callable[[t.Any], t.Any]):
        self.dependency = dependency
        self.resolved_dependency = dependency

    def __call__(self, value: t.Any) -> t.Any:
        return self.resolved_dependency(value)

    def __resolve__(self, injector: DependencyInjector) -> None:
        self.resolved_dependency = injector.create_wrapper(self.dependency)


# # Some functions to use as default value
# # Functions are explicitely typed as Any so that user can assign any annotation in function signatures
def Token(index: int) -> t.Any:
    return _Token(index)


def Header(key: str) -> t.Any:
    return _Header(key)


def Depends(dependency: t.Callable[..., t.Any]) -> t.Any:
    return _Depends(dependency)


# Define default constructor
def identity(obj: T) -> T:
    return obj


# # A mapping of type and constructors
type_constructors: t.Dict[t.Type[t.Any], t.Callable[[Msg], t.Any]] = {
    Msg: identity,
    Client: lambda msg: msg.client,
    bytes: lambda msg: msg.data,
    Subject: lambda msg: msg.subject,
    Reply: lambda msg: msg.reply,
}
# A mapping of default values and constructors
default_constructors: t.Dict[t.Type[t.Any], t.Callable[[Msg], t.Any]] = [
    _Header,
    _Token,
]


# Function to wrap subscriptions callbacks
def wrap_subscription_callback(
    subject: str, func: t.Callable[..., t.Any]
) -> t.Tuple[str, t.Callable[[Msg], t.Any]]:

    factory = DependencyInjector[Msg](type_constructors, default_constructors)
    sanitized_subject, placeholders = substitute_placeholder_tokens(subject)

    for index, name in placeholders:

        def constructor(msg: Msg) -> str:
            token = msg.subject.split(".")[index]
            return token

        factory.register_name_constructor(name, constructor)

    return sanitized_subject, factory.create_wrapper(func)


# Examples
import functools  # type: ignore[noqa: E402]


def first_token(subject: Subject) -> str:
    return subject.split(".")[0]


def simple(
    data: bytes,
    subject: Subject,
):
    _, token, id = subject.split(".")
    now = datetime.now(timezone.utc)
    return data, subject, token, id, now, msg


def foo(
    data: bytes,
    subject: Subject,
    id: str,
    msg: Msg,
    first_token: str = Depends(first_token),
    second_token: str = Token(1),
    now: datetime = Depends(functools.partial(datetime.now, timezone.utc)),
):
    return data, subject, first_token, second_token, id, now, msg


def bar(msg: Msg):
    _, token, id = msg.subject.split(".")
    now = datetime.now(timezone.utc)
    return msg.data, msg.subject, token, id, now, msg


sub, wrapped = wrap_subscription_callback("pub.sensor.{id}", foo)

sub, wrapped_untouched = wrap_subscription_callback("pub.sensor.{id}", bar)

msg = Msg(None, subject="pub.sensor.12", data=b"hello")


def _func(msg):
    return msg.data


def func(msg):
    for i in range(10):
        _func(msg)
    return _func(msg)
