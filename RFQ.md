# Subscriptions in applications

0. When do we want to add a broker?
   1. Always ? => NO: Only when a broker is required
   2. Only when specified in spec ?  => YES: It seems the right place to declare subscriptions
   3. Only when specified in settings ?  => NO: I think that subscriptions are more of an application component rather than an application setting

1. What do we want to do ?

   1. Do we want to do something at application startup ?  => YES: We need to: 1. Provide a broker 2. Identify and create subscriptions
   2. Do we want to do something during application runtime ?  => YES: We want to known subscriptions states
      1. Do we want to expose control methods ?  => NO: At the moment it seems a bit too much. But we might be interested in start/stop/restart control flow
      2. Do we want to expose monitoring methods ? => YES: Exposing some metrics about subscriptions seems important enough to include in a POC
   3. Do we need to clean-up things at application shutdown ?  => YES: We need to drain subscriptions
   4. Do we want to expose resources to endpoint developers ?  => YES: Started subscriptions should be available to users

2. What is the prefered API to expose ?

    PROPOSAL: We rename `routers` option in ApiSpec into `web_routers` and we allow a new option `nats_routers` which will accept a list of `NATSRouter` instances.

    - `NATSRouter` should provide decorators such as `@subscribe(subject=...)` or `@susbcribe_and_reply(subject=...)`

    - All `NATSRouters` use the same `NATSClient` instance.

    - Dependency injection allows developers to access container resources in subscription callbacks.

Subscription usage:

```python
from wire import get_resource
from wire.nats import NATSRouter, NATSClient
# Hypothetical resource
from my_pkg import Database

router = NATSRouter(prefix="some.service")

@router.subscribe(subject="some.publisher.subject.with.{address}")
async def on_published_message(address: str, data: bytes, client: NATSClient, database: Database = get_resource(Database)) -> None:
    """Process an incoming message"""
    # Publish received data on another subject
    client.publish(subject="hello", data=data)
```
- `address` parameter is injected based on subject value because it corresponds to the variable found in subject: `"some.publisher.subject.with.{address}"`
- `data` parameter is injected because it is annotated as `bytes`. `bytes` parameters are expected to receive message data as value.
- `client` parameter is injected because it is annotated as `NATSClient`. `NATSClient` parameters are expected to receive the client which received the message as value.
- `database` parameter is injected because its default value is an instance of `fastapi.Depends` (or `wire.nats.Depends` which could be a similar class). Parameters with default values of type `Depends` are expected to receive the return value of the underlying dependency. In this example `get_resource(Database)` is equivalent to `Depends(get_database)` where `get_database` in a function with the following signature: `def get_database(msg: nats.aio.msg.Msg) -> Database`. It is called with the incoming message as parameter, and should return a `Database` instance. In general, dependencies are expected to accept a `nats.aio.msg.Msg` and can return values of any type.


Service usage:

```python
from wire import get_resource
from wire.nats import NATSRouter, NATSClient, default_encoder
# Hypothetical resource
from my_pkg import Database

router = NATSRouter(prefix="some.service")

@router.subscribe_and_reply(
    subject="some.publisher.subject",
    encoder=wire.nats.default_encoder,
    queue="some_queue",
)
async def on_published_message(data: bytes, client: NATSClient, database: Database = get_resource(Database)) -> str:
    """Process an incoming message"""
    # Return any value
    return "hello"
```

- A queue can be used just like with `NATSClient.subscribe` method
- All arguments accepted by `NATSClient.subscribe` should also be accepted by the decorator
- `encoder` is optional and in this example the default value is explicitely used.
- `encoder` is a callable with the following signature: `def encoder(obj: Any) -> bytes`.
It must accept objects of any type and return bytes instances.
If encoder fails to serialize return value to bytes, an  `EncoderError` should be raised.

- A default encoder can be specified at the router level.

High-Level Service usage

```python
from wire import get_resource
from wire.nats import NATSRouter, NATSClient, default_encoder
# Hypothetical resource
from my_pkg import Database

router = NATSRouter(prefix="some.service")

@router.service(
    subject="some.publisher.subject",
    status_code=200,
    media_type="text/plain",
)
async def on_published_message(data: bytes, client: NATSClient, database: Database = get_resource(Database)) -> str:
    """Process an incoming message"""
    # Return any value
    return "hello"
```

High-level services are services which always return a response, even in case of failure. Response headers are used to describe success or failure, and can include additional information such a media type to indicate to clients how to consume received data.

## Dependency injection specification

### Basic logic

Dependency injection should resolve around a simple principle:

- Susbcription callback is inspected at definition time

  - All callback arguments are expected to be either:
    - Annotated (with or without a default value)
    - Non annotated: In this case, argument is considered to be of type `Msg` and will receive the message as value.

  - A function is generated to extract argument values from message
  
  - A wrapper is generated which first call function to extract argument values and then call original function with arguments
  

### Subject placeholders

It's possible to declare arguments which values will be extracted from subject:

```python
@subscribe(subject="pub.sensor.{id}.temperature)
async def on_new_temperature(msg: Msg, sensor_id: str) -> None:
    ...
```

Limitations:
  - It's not possible to use placeholders in the middle of a token: "pub.sensor_{id}.temperature" is not a valid subject.
  - Due to the first limitation, placeholder values cannot contain "`."`"
  - Placeholder name must be a valid python variable name

Implementation logic:
- Before subscription, identify placeholder names and indexes. In the example used above, it would be: `("id", 2)`.
  - Explanation: once subject is split using "`.`", `{id}` is the third element: `["pub", "sensor", "{id}", "temperature"][2] == "{id}"`
  
  - A regex could be use to identify variables (for example: `r"\{(.*?)\}"`)

- Replace all placeholders with `*` character. In this example subject would become `pub.sensor.*.temperature`.

- Create a wrapper for the callback. This wrapper will:
  - Take the subject from the received message
  - Extract the placeholder value from the subject: `placeholder_value = subject[placeholder_index]`
  - Create a dict of keyword arguments:  `kwargs = {placeholder_name: placeholder_value}`
  - Call the original function with the message and the kwargs: `func(msg, **kwargs)`

## 