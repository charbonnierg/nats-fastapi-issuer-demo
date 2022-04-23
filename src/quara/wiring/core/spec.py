from __future__ import annotations

import json
import pathlib
import typing
from configparser import ConfigParser

import fastapi
import pydantic
import yaml

from .container import AppTask, Container
from .settings import AppMeta, BaseAppSettings
from .utils import fullname

ContainerT = typing.TypeVar("ContainerT", bound="Container")


class RawSpec(pydantic.BaseModel):
    meta: AppMeta = pydantic.Field(default_factory=AppMeta)
    settings: typing.Union[
        pydantic.PyObject, typing.Type[BaseAppSettings]
    ] = BaseAppSettings
    routers: typing.List[pydantic.PyObject] = []
    hooks: typing.List[pydantic.PyObject] = []
    tasks: typing.List[pydantic.PyObject] = []
    providers: typing.List[pydantic.PyObject] = []
    config_file: typing.Union[str, pathlib.Path, None] = None

    class Config:
        """Required for pydantic to support arbitrary types"""

        arbitrary_types_allowed = True

    def validate(self) -> AppSpec:
        """Validate application spec"""
        return AppSpec.parse_obj(self.dict(exclude_unset=True))


class AppSpec(pydantic.BaseModel):
    meta: AppMeta = pydantic.Field(default_factory=AppMeta)
    settings: typing.Type[BaseAppSettings] = BaseAppSettings
    routers: typing.List[
        typing.Union[
            fastapi.APIRouter,
            typing.Callable[
                [Container[typing.Any]], typing.Optional[fastapi.APIRouter]
            ],
        ]
    ] = []
    hooks: typing.List[
        typing.Callable[
            [Container[typing.Any]],
            typing.Optional[typing.AsyncContextManager[typing.Any]],
        ]
    ] = []
    tasks: typing.List[
        typing.Union[
            typing.Callable[
                [Container[typing.Any]],
                typing.Coroutine[typing.Any, typing.Any, typing.Any],
            ],
            AppTask[typing.Any],
            typing.Callable[
                [Container[typing.Any]], typing.Optional[AppTask[typing.Any]]
            ],
        ]
    ] = []
    providers: typing.List[
        typing.Callable[[Container[typing.Any]], None],
    ] = []
    config_file: typing.Union[str, pathlib.Path, None] = None

    class Config:
        """Required for pydantic to support arbitrary types"""

        arbitrary_types_allowed = True

    @classmethod
    def from_spec(cls, raw_spec: RawSpec) -> AppSpec:
        """Create application spec from raw spec"""
        return raw_spec.validate()

    @classmethod
    def from_json_file(
        cls,
        path: typing.Union[str, pathlib.Path],
    ) -> AppSpec:
        """Load application spec from JSON file"""
        return RawSpec.parse_raw(pathlib.Path(path).read_bytes()).validate()

    @classmethod
    def from_yaml_file(
        cls,
        path: typing.UnionUnion[str, pathlib.Path],
    ) -> AppSpec:
        """Load application spec from YAML file"""
        raw_spec = yaml.safe_load(pathlib.Path(path).read_bytes())
        return RawSpec.parse_obj(raw_spec).validate()

    @classmethod
    def from_ini_file(
        cls,
        path: typing.UnionUnion[str, pathlib.Path],
    ) -> AppSpec:
        """Load application spec from INI file"""
        parser = ConfigParser()
        parser.read(path, encoding="utf-8")
        ini_config = {
            section: dict(parser.items(section)) for section in parser.sections()
        }
        raw_spec = {"meta": ini_config.get("meta", {}), **ini_config.get("spec", {})}
        if "providers" in raw_spec:
            raw_spec["providers"] = [
                string.strip()
                for string in raw_spec["providers"].splitlines(False)
                if string
            ]
        if "routers" in raw_spec:
            raw_spec["routers"] = [
                string.strip()
                for string in raw_spec["routers"].splitlines(False)
                if string
            ]
        if "tasks" in raw_spec:
            raw_spec["tasks"] = [
                string.strip()
                for string in raw_spec["tasks"].splitlines(False)
                if string
            ]
        if "hooks" in raw_spec:
            raw_spec["hooks"] = [
                string.strip()
                for string in raw_spec["hooks"].splitlines(False)
                if string
            ]
        return RawSpec.parse_obj(raw_spec).validate()

    @classmethod
    def from_file(
        cls,
        path: typing.UnionUnion[str, pathlib.Path],
        media_type: typing.Union[typing.Literal["json", "yaml", "ini"], None] = None,
    ) -> AppSpec:
        """Load application spec from file. File format is inferred and default to YAML if not found."""
        filepath = pathlib.Path(path)
        # Make sure file exists
        if not filepath.exists():
            raise FileNotFoundError(f"Spec file does not exist: {path}")
        # Infer media type
        if media_type is None:
            suffix = filepath.suffix.lower()
            if "json" in suffix:
                media_type = "json"
            elif "yml" in suffix or "yaml" in suffix:
                media_type = "yaml"
            elif "ini" in suffix or "cfg" in suffix or "config" in suffix:
                media_type = "ini"
            else:
                media_type = "yaml"
        # Parse according to media type
        if media_type == "yaml":
            return cls.from_yaml_file(path)
        elif media_type == "json":
            return cls.from_json_file(path)
        elif media_type == "ini":
            return cls.from_ini_file(path)
        # We should never reach this statement
        raise Exception(f"Unknown media type value: {media_type}")

    @staticmethod
    def inspect(spec: typing.Mapping[str, typing.Any]) -> typing.Dict[str, typing.Any]:
        raw_spec: typing.Dict[str, typing.Any] = {}
        if "meta" in spec:
            raw_spec["meta"] = spec["meta"]
        if "settings" in spec:
            raw_spec["settings"] = fullname(spec["settings"])
        if "routers" in spec:
            raw_spec["routers"] = [fullname(router) for router in spec["routers"]]
        if "tasks" in spec:
            raw_spec["tasks"] = [fullname(task) for task in spec["tasks"]]
        if "hooks" in spec:
            raw_spec["hooks"] = [fullname(hook) for hook in spec["hooks"]]
        if "providers" in spec:
            raw_spec["providers"] = [
                fullname(provider) for provider in spec["providers"]
            ]
        if "config_file" in spec:
            raw_spec["config_file"] = spec["config_file"]
        return raw_spec

    def dict(
        self,
        *,
        include: typing.Union[
            pydantic.fields.AbstractSetIntStr, pydantic.fields.MappingIntStrAny
        ] = None,
        exclude: typing.Union[
            pydantic.fields.AbstractSetIntStr, pydantic.fields.MappingIntStrAny
        ] = None,
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
    ) -> typing.Dict[str, typing.Any]:
        items = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        return self.inspect(items)

    def json(
        self,
        *,
        include: typing.Union[
            pydantic.fields.AbstractSetIntStr, pydantic.fields.MappingIntStrAny
        ] = None,
        exclude: typing.Union[
            pydantic.fields.AbstractSetIntStr, pydantic.fields.MappingIntStrAny
        ] = None,
        by_alias: bool = False,
        skip_defaults: bool = None,
        exclude_unset: bool = False,
        exclude_defaults: bool = False,
        exclude_none: bool = False,
        encoder: typing.Optional[typing.Callable[[typing.Any], typing.Any]] = None,
        **dumps_kwargs: typing.Any,
    ) -> str:
        items = super().dict(
            include=include,
            exclude=exclude,
            by_alias=by_alias,
            skip_defaults=skip_defaults,
            exclude_unset=exclude_unset,
            exclude_defaults=exclude_defaults,
            exclude_none=exclude_none,
        )
        if encoder:
            dumps_kwargs["cls"] = encoder
        return json.dumps(self.inspect(items), **dumps_kwargs)

    @typing.overload
    def create_container(
        self,
        container_factory: typing.Type[ContainerT],
        meta: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        settings: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> ContainerT:
        ...

    @typing.overload
    def create_container(
        self,
        container_factory: None = None,
        meta: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        settings: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> Container[BaseAppSettings]:
        ...

    def create_container(
        self,
        container_factory: typing.Optional[
            typing.Type[Container[BaseAppSettings]]
        ] = None,
        meta: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        settings: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> Container[BaseAppSettings]:
        """Create a new container instance"""
        if isinstance(meta, pydantic.BaseModel):
            meta = meta.dict(exclude_unset=True)
        elif meta is None:
            meta = {}
        if isinstance(settings, pydantic.BaseModel):
            settings = settings.dict(exclude_unset=True)
        elif settings is None:
            settings = {}
        # Use Container[BaseAppSettings] if no container factory is specified
        if container_factory is None:
            container_factory = Container[BaseAppSettings]
        # Create new container instance
        return container_factory(
            meta=AppMeta.parse_obj({**self.meta.dict(exclude_unset=True), **meta}),
            settings=self.settings.parse_obj(settings),
            routers=self.routers,
            hooks=self.hooks,
            tasks=self.tasks,
            providers=self.providers,
            config_file=config_file or self.config_file,
        )

    def create_app(
        self,
        container_factory: typing.Optional[
            typing.Type[Container[BaseAppSettings]]
        ] = None,
        meta: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        settings: typing.Union[
            typing.Dict[str, typing.Any], pydantic.BaseModel, None
        ] = None,
        config_file: typing.Union[str, pathlib.Path, None] = None,
    ) -> fastapi.FastAPI:
        """Create a new FastAPI application"""
        # Create new container first
        container = self.create_container(
            container_factory=container_factory,
            meta=meta,
            settings=settings,
            config_file=config_file,
        )
        # Return application
        return container.app


def create_container_from_specs(
    filepath: typing.Union[str, pathlib.Path],
    meta: typing.Union[typing.Dict[str, typing.Any], pydantic.BaseModel, None] = None,
    settings: typing.Union[
        typing.Dict[str, typing.Any], pydantic.BaseModel, None
    ] = None,
    config_file: typing.Union[str, pathlib.Path, None] = None,
) -> Container[BaseAppSettings]:
    """Create a new container instance from file spec"""
    spec = AppSpec.from_file(filepath)
    return spec.create_container(
        meta=meta,
        settings=settings,
        config_file=config_file,
    )


def create_app_from_specs(
    filepath: typing.Union[str, pathlib.Path],
    meta: typing.Union[typing.Dict[str, typing.Any], pydantic.BaseModel, None] = None,
    settings: typing.Union[
        typing.Dict[str, typing.Any], pydantic.BaseModel, None
    ] = None,
    config_file: typing.Union[str, pathlib.Path, None] = None,
) -> fastapi.FastAPI:
    """Create a new container instance from file spec"""
    spec = AppSpec.from_file(filepath)
    return spec.create_app(
        meta=meta,
        settings=settings,
        config_file=config_file,
    )
