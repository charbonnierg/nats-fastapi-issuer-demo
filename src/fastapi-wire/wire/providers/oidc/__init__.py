from typing import Any, List, Optional

from fastapi import Depends, HTTPException, Security
from fastapi.responses import PlainTextResponse
from fastapi.security.utils import get_authorization_scheme_param
from starlette.requests import Request
from starlette.status import HTTP_403_FORBIDDEN
from wire import BaseAppSettings, Container
from wire.core.dependencies import get_container

from .errors import NotAllowedError
from .models import NO_AUTH_USER_CLAIMS, UserClaims
from .security import OIDCAuth


def openid_connect_provider(
    container: Container[BaseAppSettings],
) -> Optional[List[Any]]:
    if not container.settings.oidc.enabled:
        return None
    try:
        from wire.providers.oidc.provider import OIDCAuthProvider
    except ModuleNotFoundError as err:
        raise ModuleNotFoundError(
            "Extra dependency 'oidc' is required to use the openid connect provider. Install it using the command: 'pip install fastapi-wire[oidc]'"
        ) from err

    # Create oidc provider
    oidc = OIDCAuthProvider(
        issuer_url=container.settings.oidc.issuer_url,
        enabled=container.settings.oidc.enabled,
        algorithms=container.settings.oidc.algorithms,
    )
    container.app.state.oidc = oidc
    OIDCAuth.update_model(oidc)

    # Define /me endpoint
    @container.app.get(
        "/oidc/users/me", response_model=UserClaims, tags=["OpenID Connect"]
    )
    async def show_user(user: UserClaims = get_user()) -> UserClaims:
        return user

    # Define /me endpoint
    @container.app.get("/oidc/users/me/jwt", tags=["OpenID Connect"])
    async def get_user_jwt(
        request: Request, user: UserClaims = get_user()
    ) -> PlainTextResponse:
        authorization: str = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)
        return PlainTextResponse(token)

    return [oidc]


def get_user(roles: List[str] = [], all: bool = True) -> Any:
    """Get current user"""

    async def _get_current_user_with_roles(
        user: UserClaims = Security(OIDCAuth()),
        container: Container[BaseAppSettings] = get_container(),
    ) -> UserClaims:
        if not container.settings.oidc.enabled:
            return NO_AUTH_USER_CLAIMS
        if not roles:
            return user
        try:
            user.check_roles(*roles, require_all=all)
        except NotAllowedError:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Not allowed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    return Depends(dependency=_get_current_user_with_roles)


__all__ = ["openid_connect_provider", "get_user"]
