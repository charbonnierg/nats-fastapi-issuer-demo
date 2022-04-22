from __future__ import annotations

import typing

import fastapi
from structlog import get_logger

from demo_app.hooks.issuer import issuer
from demo_app.lib.issuer import Claims, Issuer, NATSAttrs
from demo_app.providers.oidc import get_user
from demo_app.providers.oidc.models import UserClaims

logger = get_logger()
router = fastapi.APIRouter(
    prefix="/nats",
    tags=["NATS Authorization"],
    default_response_class=fastapi.responses.JSONResponse,
)


@router.get(
    "/account/keys",
    summary="Return issuer public keys.",
    status_code=200,
    # response_model=typing.List[EmployeeInDB],
)
async def get_issuer_infos(
    issuer: Issuer = fastapi.Depends(issuer),
    user: UserClaims = get_user()
    # logger: BoundLogger = fastapi.Depends(logger),
) -> typing.Dict[str, str]:
    """Get all employees data."""
    return {
        "account_key": issuer.config.account_public_key,
        "signing_key": issuer.keypair.public_key.decode(),
    }


@router.post(
    "/users/me",
    summary="Show user infos",
    status_code=202,
    response_model=Claims,
)
async def get_current_user(
    issuer: Issuer = fastapi.Depends(issuer),
    user: UserClaims = get_user(),
) -> Claims:
    """Return NATS credentials for current user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    allow_subs = user.dict().get("allow-subscriptions", [])
    allow_pubs = user.dict().get("allow-publications", [])
    logger.warning(allow_pubs)
    if "nats-admin" in user.realm_access.roles:
        allow_pubs = [">"]
        allow_subs = [">"]
    nats = NATSAttrs(pub={"allow": allow_pubs}, sub={"allow": allow_subs})
    nats_user = issuer.create_user(user.name, nats)
    return nats_user.jwt.claims


@router.post(
    "/users/me/creds",
    summary="Return credentials for current user",
    response_class=fastapi.Response,
    status_code=202,
    # response_model=typing.List[EmployeeInDB],
)
async def get_current_user_credentials(
    issuer: Issuer = fastapi.Depends(issuer),
    user: UserClaims = get_user(),
) -> fastapi.responses.PlainTextResponse:
    """Return NATS credentials for current user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    allow_subs = user.dict().get("allow-subscriptions", [])
    allow_pubs = user.dict().get("allow-publications", [])
    if "nats-admin" in user.realm_access.roles:
        allow_pubs = [">"]
        allow_subs = [">"]
    nats = NATSAttrs(pub={"allow": allow_pubs}, sub={"allow": allow_subs})
    nats_user = issuer.create_user(user.name, nats)
    return fastapi.responses.PlainTextResponse(content=nats_user.creds, status_code=202)


@router.post(
    "/users/me/jwt",
    summary="Return JWT for current user",
    response_class=fastapi.Response,
    status_code=202,
    # response_model=typing.List[EmployeeInDB],
)
async def get_current_user_jwt(
    issuer: Issuer = fastapi.Depends(issuer),
    user: UserClaims = get_user(),
) -> fastapi.responses.PlainTextResponse:
    """Return NATS credentials for current user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    allow_subs = user.dict().get("allow-subscriptions", [])
    allow_pubs = user.dict().get("allow-publications", [])
    if "nats-admin" in user.realm_access.roles:
        allow_pubs = [">"]
        allow_subs = [">"]
    nats = NATSAttrs(pub={"allow": allow_pubs}, sub={"allow": allow_subs})
    nats_user = issuer.create_user(user.name, nats)
    return fastapi.responses.PlainTextResponse(
        content=nats_user.jwt.encode(), status_code=202
    )


@router.post(
    "/users/{username}/creds",
    summary="Return credentials for any user",
    response_class=fastapi.Response,
    status_code=202,
)
async def get_user_credentials(
    username: str,
    nats: typing.Optional[NATSAttrs] = None,
    issuer: Issuer = fastapi.Depends(issuer),
    _: UserClaims = get_user(["nats-issuer", "nats-admin"], all=False),
    # logger: BoundLogger = fastapi.Depends(logger),
) -> fastapi.responses.PlainTextResponse:
    """Return NATS credentials for any user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    nats_user = issuer.create_user(username, nats or NATSAttrs())
    return fastapi.responses.PlainTextResponse(content=nats_user.creds, status_code=202)


@router.post(
    "/users/{username}/jwt",
    summary="Return credentials for any user",
    response_class=fastapi.Response,
    status_code=202,
)
async def get_user_jwt(
    username: str,
    nats: typing.Optional[NATSAttrs] = None,
    issuer: Issuer = fastapi.Depends(issuer),
    _: UserClaims = get_user(["nats-issuer", "nats-admin"], all=False),
    # logger: BoundLogger = fastapi.Depends(logger),
) -> fastapi.responses.PlainTextResponse:
    """Return NATS JWT token for any user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    nats_user = issuer.create_user(username, nats or NATSAttrs())
    return fastapi.responses.PlainTextResponse(
        content=nats_user.jwt.encode(), status_code=202, media_type="octet/stream"
    )
