from __future__ import annotations

import json
import typing

import fastapi
from nats import NATS
from quara.wiring import get_hook
from quara.wiring.providers.oidc import UserClaims, get_user
from structlog import get_logger

from demo_app.lib import Issuer, NATSAttrs

logger = get_logger()
router = fastapi.APIRouter(
    prefix="/nats",
    tags=["NATS"],
    default_response_class=fastapi.responses.JSONResponse,
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
    user: UserClaims = get_user()
    # logger: BoundLogger = fastapi.Depends(logger),
) -> typing.Dict[str, str]:
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
        return fastapi.Response(None, status_code=204)
    except Exception as err:
        logger.error("Failed to publish message", err=err)
    finally:
        await nc.close()


@router.post(
    "/request",
    summary="Request a message on NATS.",
    status_code=204,
)
async def request_message(
    subject: str,
    payload: typing.Union[
        typing.List[typing.Any], typing.Dict[str, typing.Any], None
    ] = None,
    headers: typing.Optional[typing.Dict[str, str]] = None,
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(),
) -> typing.Dict[str, str]:
    """Request a message on NATS using current user credentials."""
    with issuer.temporary_creds(
        user.name, nats=NATSAttrs(pub={"allow": ["foo"]})
    ) as creds:
        nc = NATS()
        await nc.connect(user_credentials=creds.as_posix())
    # At this point credentials are no longer present on disk
    try:
        response = await nc.request(
            subject, json.dumps(payload).encode("utf-8"), headers=headers
        )
        out = f'{{"data": {json.dumps(response.data.decode("utf-8"))}}}'
        return fastapi.responses.PlainTextResponse(
            out.encode("utf-8"), media_type="application/json"
        )
    except Exception as err:
        return fastapi.responses.PlainTextResponse(
            f"Response failed. Error type={type(err).__name__}. Error message={repr(err)}",
            status_code=500,
        )
    finally:
        await nc.close()
