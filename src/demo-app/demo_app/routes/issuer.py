import typing

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse, Response
from wire import get_hook
from wire.providers.oidc import UserClaims, get_user
from structlog import get_logger

from demo_app.lib import Claims, Issuer, NATSAttrs
from demo_app.lib.issuer import IssuerPublicKeys

logger = get_logger()
router = APIRouter(
    prefix="/nats",
    tags=["NATS Authorization"],
)


@router.get(
    "/account/keys",
    summary="Return issuer public keys.",
    status_code=200,
    response_model=IssuerPublicKeys,
)
async def get_issuer_config(issuer: Issuer = get_hook(Issuer)) -> IssuerPublicKeys:
    """Get issuer account public keys"""
    return issuer.public_keys


@router.post(
    "/users/me",
    summary="Show user infos",
    status_code=202,
    response_model=Claims,
)
async def get_current_user(
    issuer: Issuer = get_hook(Issuer),
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
    status_code=202,
)
async def get_current_user_credentials(
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(),
) -> PlainTextResponse:
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
    return PlainTextResponse(content=nats_user.creds, status_code=202)


@router.post(
    "/users/me/jwt",
    summary="Return JWT for current user",
    response_class=Response,
    status_code=202,
)
async def get_current_user_jwt(
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(),
) -> PlainTextResponse:
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
    return PlainTextResponse(content=nats_user.jwt.encode(), status_code=202)


@router.post(
    "/users/{username}/creds",
    summary="Return credentials for any user",
    response_class=Response,
    status_code=202,
)
async def get_user_credentials(
    username: str,
    nats: typing.Optional[NATSAttrs] = None,
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(["nats-issuer", "nats-admin"], all=False),
) -> PlainTextResponse:
    """Return NATS credentials for any user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    nats_user = issuer.create_user(username, nats or NATSAttrs())
    return PlainTextResponse(content=nats_user.creds, status_code=202)


@router.post(
    "/users/{username}/jwt",
    summary="Return credentials for any user",
    response_class=Response,
    status_code=202,
)
async def get_user_jwt(
    username: str,
    nats: typing.Optional[NATSAttrs] = None,
    issuer: Issuer = get_hook(Issuer),
    user: UserClaims = get_user(["nats-issuer", "nats-admin"], all=False),
) -> PlainTextResponse:
    """Return NATS JWT token for any user.

    Note that account is static. Account public  key and signing public key can be fetched using /keys endpoint.
    """
    nats_user = issuer.create_user(username, nats or NATSAttrs())
    return PlainTextResponse(
        content=nats_user.jwt.encode(), status_code=202, media_type="octet/stream"
    )
