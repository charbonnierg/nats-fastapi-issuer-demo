import json
import typing

from fastapi import APIRouter
from nats import NATS
from wire import get_hook
from wire.providers.oidc import UserClaims, get_user
from structlog import get_logger

from demo_app.lib import Issuer, NATSAttrs

logger = get_logger()
router = APIRouter(
    prefix="/nats",
    tags=["NATS"],
)


@router.post(
    "/publish",
    summary="Publish a message on NATS.",
    status_code=204,
)
async def publish_message(
    subject: str,
    payload: typing.Union[
        typing.List[typing.Any], typing.Dict[str, typing.Any], None
    ] = None,
    headers: typing.Optional[typing.Dict[str, str]] = None,
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(),
) -> None:
    """Publish a message on NATS using current user credentials."""
    with issuer.temporary_creds(
        user.name, nats=NATSAttrs(pub={"allow": ["foo"]})
    ) as creds:
        nc = NATS()
        await nc.connect(user_credentials=creds.as_posix())
    # At this point credentials are no longer present on disk
    try:
        await nc.publish(subject, json.dumps(payload).encode("utf-8"), headers=headers)
        logger.info("Published message on NATS")
        return None
    except Exception as err:
        logger.error("Failed to publish message", err=err)
        raise
    finally:
        await nc.close()


@router.post(
    "/request",
    summary="Request a message on NATS.",
    status_code=202,
)
async def request_message(
    subject: str,
    payload: typing.Union[
        typing.List[typing.Any], typing.Dict[str, typing.Any], None
    ] = None,
    headers: typing.Optional[typing.Dict[str, str]] = None,
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(),
) -> typing.Dict[str, typing.Any]:
    """Request a message on NATS using current user credentials."""
    with issuer.temporary_creds(
        user.name, nats=NATSAttrs(pub={"allow": ["foo"]})
    ) as creds:
        nc = NATS()
        await nc.connect(user_credentials=creds.as_posix())
    # At this point credentials are no longer present on disk
    try:
        response = await nc.request(
            subject, json.dumps(payload).encode("utf-8"), headers=headers or {}
        )
        return json.loads(response.data.decode("utf-8"))  # type: ignore[no-any-return]
    finally:
        await nc.close()
