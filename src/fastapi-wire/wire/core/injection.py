import asyncio
import inspect
import typing as t
from inspect import Parameter, _empty

import typing_extensions as t_

ParamsT = t_.ParamSpec("ParamsT")
T = t.TypeVar("T")


# Define default constructor
def identity(obj: T) -> T:
    return obj


class _Depends:
    __slots__ = ["dependency", "resolved_dependency"]

    def __init__(self, dependency: t.Callable[[t.Any], t.Any]):
        self.dependency = dependency
        self.resolved_dependency = dependency

    def __call__(self, value: t.Any) -> t.Any:
        return self.resolved_dependency(value)

    def __resolve__(self, injector: "DependencyInjector") -> None:
        self.resolved_dependency = injector.create_wrapper(self.dependency)


# A class which holds informations on how dependency injection should be performed
class DependencyInjector(t.Generic[ParamsT]):
    def __init__(
        self,
        type_constructors: t.Optional[
            t.Dict[t.Type[t.Any], t.Callable[ParamsT, t.Any]]
        ] = None,
        default_constructors: t.Optional[
            t.List[t.Type[t.Callable[ParamsT, t.Any]]]
        ] = None,
        name_constructors: t.Optional[t.Dict[str, t.Callable[ParamsT, t.Any]]] = None,
        untyped_is_identity: bool = True,
    ) -> None:
        self.type_constructors = type_constructors or {}
        self.default_constructors = default_constructors or []
        self.name_constructors = name_constructors or {}
        if untyped_is_identity:
            self.type_constructors[_empty] = identity
        if _Depends not in self.default_constructors:
            self.default_constructors.append(_Depends)

    def create_wrapper(
        self, func: t.Callable[..., t.Any]
    ) -> t.Callable[ParamsT, t.Any]:
        # Get function signature
        signature = inspect.signature(func)
        # Handle case when no parameters are expected
        if not signature.parameters:
            if asyncio.iscoroutinefunction(func):

                async def wrapper(
                    *args: ParamsT.args, **kwargs: ParamsT.kwargs
                ) -> t.Any:
                    # Execute original function
                    return await func()

            else:

                def wrapper(*args: ParamsT.args, **kwargs: ParamsT.kwargs) -> t.Any:
                    # Execute original function
                    return func()

            # Return wrapper
            return wrapper

        parameters_factory = self.get_parameters_factory(signature)

        # Do not decorate at all if there is no need
        if parameters_factory is None:
            return func

        if asyncio.iscoroutinefunction(func):

            async def wrapper(*args: ParamsT.args, **kwargs: ParamsT.kwargs) -> t.Any:
                # Extract argument when message is received
                _args, _kwargs = parameters_factory(*args, **kwargs)
                # Execute original function
                return await func(*_args, **_kwargs)

        else:

            def wrapper(*args: ParamsT.args, **kwargs: ParamsT.kwargs) -> t.Any:
                # Extract argument when message is received
                _args, _kwargs = parameters_factory(*args, **kwargs)
                # Execute original function
                return func(*_args, **_kwargs)

        return wrapper

    def get_parameters_factory(
        self, signature: inspect.Signature
    ) -> t.Optional[t.Callable[ParamsT, t.Tuple[t.Tuple[t.Any], t.Dict[str, t.Any]]]]:

        # Initialize factories
        args_factories: t.List[t.Callable[ParamsT, t.Any]] = []
        kwargs_factories: t.Dict[str, t.Callable[ParamsT, t.Any]] = {}
        # Iterate over parameters
        for param_name, param in signature.parameters.items():
            positional_only = param.kind == param.POSITIONAL_ONLY
            constructor = self.get_parameter_constructor(param)
            if positional_only:
                args_factories.append(constructor)
            else:
                kwargs_factories[param_name] = constructor

        if not args_factories:
            if len(kwargs_factories) == 1:
                if next(iter(kwargs_factories.values())) == identity:
                    return None
        if not kwargs_factories:
            if len(args_factories) == 1:
                if args_factories[0] == identity:
                    return None

        # Create factory
        def factory(
            *args: ParamsT.args, **kwargs: ParamsT.kwargs
        ) -> t.Tuple[t.Tuple[t.Any], t.Dict[str, t.Any]]:
            # Take first arg
            _input, *args = args
            # First process kwargs
            _kwargs_factories = kwargs_factories.copy()
            for key in kwargs:
                # Remove factories if we already have a value
                _kwargs_factories.pop(key)
            # Then process args
            _args_factories = args_factories.copy()
            for _ in args:
                try:
                    # Remove next args factory
                    _args_factories.pop(0)
                except KeyError:
                    # Remove next kwargs factory
                    _kwargs_factories.pop(next(iter(_kwargs_factories)))
            if _args_factories:
                args = list(args)
                # Update args using remaining factories
                for constructor in _args_factories:
                    args.append(constructor(_input))
            if _kwargs_factories:
                # Update kwargs using remaining factories
                kwargs.update(
                    {
                        name: constructor(_input)
                        for name, constructor in _kwargs_factories.items()
                    }
                )
            return tuple(args), kwargs

        # Return factory
        return factory

    def get_parameter_constructor(
        self, parameter: Parameter
    ) -> t.Callable[ParamsT, t.Any]:
        # Try using name
        if parameter.name in self.name_constructors:
            return self.name_constructors[parameter.name]
        # Try using default value
        default_type = type(parameter.default)
        # If default type is callable, use return value
        if default_type in self.default_constructors:
            # Classes can define a method named __resolve__ which accept the dependency injector instance
            if hasattr(parameter.default, "__resolve__"):
                parameter.default.__resolve__(self)
            return parameter.default
        # Try using type hint
        if parameter.annotation in self.type_constructors:
            return self.type_constructors[parameter.annotation]
        # Raise an error
        raise TypeError(f"Type {parameter.annotation} is not a supported")

    def register_default_constructor(self, type: t.Type[T]) -> None:
        if type not in self.default_constructors:
            self.default_constructors.append(type)

    def register_type_constructor(
        self, type: t.Type[T], constructor: t.Callable[ParamsT, T]
    ) -> None:
        self.type_constructors[type] = constructor

    def register_name_constructor(
        self, name: str, constructor: t.Callable[ParamsT, t.Any]
    ) -> None:
        self.name_constructors[name] = constructor
