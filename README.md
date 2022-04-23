## Install from pypi

A pre-release has been published on pypi with the name `fastapi-wire`. To install it simply run:

```bash
python -m pip install fastapi-wire
```

## Install from source

First clone the repository from [github](https://github.com/charbonnierg/nats-fastapi-issuer-demo) then install using one of the method below.

#### Install using poetry

```bash
poetry install
```

#### Install using script

```bash
python ./install.py
```

#### Install manually

- Create a virtual environment:

```bash
python -m venv .venv
```

- Update python package toolkit (within the virtual environment):

```bash
python -m pip install -U pip setuptools wheel build
```

- Install the project in editable mode (within the virtual environment) with all extras:

```bash
python -m pip install -e .[dev,oidc,telemetry]
```

## Run the app

- Either use the `wire` module:

```bash
python -m wire examples/app.yaml -c examples/config.json
```

- Or the `wire` command line tool:

```bash
wire examples/app.yaml -c examples/config.json
```

> Run `wire --help` to see avaible options.

- Or use `uvicorn` to start the application:

```bash
CONFIG_FILEPATH=examples/config.json uvicorn --factory demo_app.spec:spec.create_app
```

> Note that server config won't be applied since uvicorn is started from command line and not within Python process in this case.

- It's also possible to start the application with hot-reloading:

```bash
CONFIG_FILEPATH=examples/config.json uvicorn --factory demo_app.spec:spec.create_app --reload
```

## Configure the app

Application can be configured using environment variables or file, or options when using the CLI:

![App Container](https://github.com/charbonnierg/nats-fastapi-issuer-demo/raw/next/docs/settings-to-container.png)

> Note: Environment variables take precedence over variables declared in file. For example, assuming the above configuration is declared in a file named `config.json`, when running: `PORT=8000 CONFIG_FILE=./demo/config.json python -m demo_app`, application will listen on port `8000` and not `7777`.

> Note: When using `uvicorn`, `HOST` and `PORT` are ignored and must be specified as command line arguments if required.

## Design choices

Application is wrapped within a [`Container`](./src/quara-wiring/quara/wiring/core/container.py):

An [`Container`](./src/quara-wiring/quara/wiring/core/container.py) is created from:

- _Some [**settings**](./src/quara-wiring/quara/wiring/core/settings.py)_: settings are defined as pydantic models. When they are not provided directly, values are parsed from environment or file.

- _Some **hooks**_: hooks are async context managers which can inject arbitrary resources into application state. In this application, a hook is used to add an `Issuer` instance to the application state. See documentation on [Asynchronous Context Managers](https://docs.python.org/3/reference/datamodel.html#asynchronous-context-managers) and [@contextlib.asynccontextmanager](https://docs.python.org/3/library/contextlib.html#contextlib.asynccontextmanager) to easily create context managers from coroutine functions. You can see how it's used in [the hook used by the example application](https://github.com/charbonnierg/nats-fastapi-issuer-demo/blob/declarative/src/demo-app/demo_app/hooks/issuer.py).

- _Some **providers**_: providers are functions which must accept a single argument, an application container, and can add additional features to the application. They are executed before the FastAPI application is initialized, unlike hooks, which are started after application is initiliazed, but before it is started. In the repo example, providers are used for example to optionally enable prometheus metrics and opentelemetry traces. The [CORS Provider](https://github.com/charbonnierg/nats-fastapi-issuer-demo/blob/declarative/src/quara-wiring/quara/wiring/providers/cors.py) is surely the most simple provider.

- _Some [**routers**](https://fastapi.tiangolo.com/tutorial/bigger-applications/#apirouter)_: routers are objects holding a bunch of API endpoints together. Those endpoints can share a prefix and some OpenAPI metadata.

In order to faciliate creation and declaration of application containers, the [`AppSpec`](./src/quara-wiring/quara/wiring/core/spec.py) class can be used as a container factory.

> See usage in [`src/demo-app/demo_app/spec.py`](./src/demo-app/demo_app/spec.py)

## Objectives

- [x] **Distributable**: Application can be distributed as a python package.

- [x] **Configurable**: The database used in the application must be configurable using either a file or an environment variable.

- [x] **Configurable**: The server configuration (host, port, debug mode) must be configurable using either a file or an environment variable.

- [x] **User friendly**: A command line script should provide a quick and simply way to configure and start the application.

- [x] **Debug friendly**: Application settings should be exposed on a `/debug/settings` endpoint when application is started on debug mode.

- [x] **Observable**: Adding metrics or tracing capabilities to the application should be straighforward and transparent.

- [x] **Explicit**: Router endpoints must not use global variables but instead explicitely declare dependencies to be injected (such as database client or settings). This enables [efficient sharing of resources and facilitate eventual refactoring in the future](https://github.com/charbonnierg/nats-fastapi-issuer-demo/blob/9beb7e4f1d37d616de10ab701cbde7fe1115f2a2/src/demo-app/demo_app/routes/demo.py#L34).

- [x] **Conposable**: Including additional routers or features in the future should require minimal work.

  - Arbitrary hooks with access to application container within their scope can be registered. Those hooks are guaranteed to be started and stopped in order, and even if an exception is encountered during a hook exit, all remaining hooks will be closed before an exception is raised. It minimize risk of resource leak within the application. Hooks can be seen as contexts just like in the illustration below:

  - Arbitrary tasks can be started along the application. Tasks are similar to hooks, and are defined using a coroutine function which takes the application container as argument and can stay alive as long as application
  is alive. Unlike hooks, tasks have a status and can be:
    - stopped
    - started
    - restarted
  It's also possible to fetch the task status to create healthcheck handlers for example.

  - Arbitrary providers with access to application container within their scope can be registered. Those providers are executed once, before the application is created. They can be used to add optional features such as tracing or metrics.
  
  - Objects provided by hooks or providers can be accessed through dependency injection in the API endpoints. Check [this example](https://github.com/charbonnierg/nats-fastapi-issuer-demo/blob/9beb7e4f1d37d616de10ab701cbde7fe1115f2a2/src/demo-app/demo_app/routes/demo.py#L34) to see dependency injection in practice.

Below is an illustration of an hypothetic application lifecycle:

![App Lifecycle](https://github.com/charbonnierg/nats-fastapi-issuer-demo/raw/next/docs/container-lifecycle.png)


## `AppSpec` container factory

### Declarative application (from YAML/JSON/INI)

It's possible to declare application using YAML, JSON or INI files. An example application could be:

```yaml
---
# Application metadata
meta:
  name: demo_app
  title: Demo App
  description: A declarative FastAPI application 🎉
  package: wire

# Custom settings model
settings: demo_app.settings.AppSettings

# Declare providers
# A few providers are available to use directly
# It's quite easy to add new providers
providers:
  - wire.providers.structured_logging_provider
  - wire.providers.prometheus_metrics_provider
  - wire.providers.openid_connect_provider
  - wire.providers.openelemetry_traces_provider
  - wire.providers.cors_provider
  - wire.providers.debug_provider
# It's possible to add routers
routers:
  - demo_app.routes.issuer_router
  - demo_app.routes.nats_router
  - demo_app.routes.demo_router
# Or hooks
hooks:
  - demo_app.hooks.issuer_hook
# Or tasks (not used in this example)
tasks: []
# # It's also possible to declare default config file
# config_file: ~/.quara.config.json
```

## Classic application (python class)

It's also possible to define applications using a python object instead of a text file. The example application looks like:

```python
spec = AppSpec(
    meta=AppMeta(
        name="demo_app",
        title="Demo App",
        description="A declarative FastAPI application 🎉",
        package="wire",
    ),
    settings=AppSettings,
    providers=[
        wire.providers.structured_logging_provider,
        wire.providers.prometheus_metrics_provider,
        wire.providers.openid_connect_provider,
        wire.providers.openelemetry_traces_provider,
        wire.providers.cors_provider,
        wire.providers.debug_provider,
    ],
    routers=[issuer_router, nats_router, demo_router],
    hooks=[issuer_hook],
    config_file="~/.quara.config.json",
)
```

### Adding hooks

Update the file `demo_app/spec.py` to add a new hook to your application.

The `hooks` argument of the `AppSpec` constructor can be used to specify a list of hooks used by the application.

Each hook must implement the `AsyncContextManager` protocol or be functions which might return `None` or an `AsyncContextManager` instance.

Object yielded by the hook is available in API endpoints using dependency injection.

> Note: It's possible to access any container attribute within hooks.

### Adding routers

Update the file `demo_app/spec.py` to register a new router within your application.

The `routers` argument of the `AppSpec` constructor can be used to specify a list of routers used by the application.

Both `fastapi.APIRouter` and functions which might return `None` or an `fastapi.APIRouter` instance are accepted as list items.


### Adding providers

Providers are functions which can modify the FastAPI application before it is started.

They must accept an application container instance as unique argument, and can return a list of objects or None.
When None is returned, it is assumed that provider is disabled.
When a list is returned, each object present in the list will be available in API endpoints using dependency injection.

Example providers are located in `src/quara-wiring/quara/wiring/providers/` directory and are registered in `demo_app/spec.py`.

## Building the package

Run the following command to build the package:

```bash
python -m build .
```

### Advantages of the `src/` layout

This project uses a `src/` layout. It means that all source code can be found under `src/` directory. It might appear overkill at first, but it brings several benefits:

- Without src you get messy editable installs ("pip install -e"). Having no separation (no src dir) will force setuptools to put your project's root on `sys.path` - with all the junk in it (e.g.: setup.py and other test or configuration scripts will unwittingly become importable).

- You get import parity. The current directory is implicitly included in `sys.path`; but not so when installing & importing from site-packages.

- You will be forced to test the installed code (e.g.: by installing in a virtualenv and performing an editable install). This will ensure that the deployed code works (it's packaged correctly) - otherwise your tests will fail.

- Simpler packaging code and manifest. It makes manifests very simple to write (e.g.: root directory of project is never considered by setuptools or other packaging toolswhen bundling files into package). Also, zero fuss for large libraries that have multiple packages. Clear separation of code being packaged and code doing the packaging.

### Telemetry

- [`BatchSpanProcessor`](https://opentelemetry-python.readthedocs.io/en/latest/sdk/trace.export.html#opentelemetry.sdk.trace.export.BatchSpanProcessor) is configurable with the following environment variables which correspond to constructor parameters:

- [OTEL_BSP_SCHEDULE_DELAY](https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html#envvar-OTEL_BSP_SCHEDULE_DELAY)
- [OTEL_BSP_MAX_QUEUE_SIZE](https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html#envvar-OTEL_BSP_MAX_QUEUE_SIZE)
- [OTEL_BSP_MAX_EXPORT_BATCH_SIZE](https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html#envvar-OTEL_BSP_MAX_EXPORT_BATCH_SIZE)
- [OTEL_BSP_EXPORT_TIMEOUT](https://opentelemetry-python.readthedocs.io/en/latest/sdk/environment_variables.html#envvar-OTEL_BSP_EXPORT_TIMEOUT)
