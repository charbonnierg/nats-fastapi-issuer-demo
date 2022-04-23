from __future__ import annotations

from typing import List

import fastapi
import fastapi.params
from fastapi.security.utils import get_authorization_scheme_param
from quara.wiring.core.container import Container
from quara.wiring.core.dependencies import get_settings
from quara.wiring.core.settings import BaseAppSettings, OIDCSettings
from starlette.status import HTTP_403_FORBIDDEN

from .errors import NotAllowedError
from .models import NO_AUTH_USER_CLAIMS, UserClaims


def openid_connect_provider(container: Container[BaseAppSettings]) -> None:
    if not container.settings.oidc.enabled:
        return
    from quara.wiring.providers.oidc.provider import OIDCAuth, OIDCAuthProvider

    # Create oidc provider
    oidc = OIDCAuthProvider(
        issuer_url=container.settings.oidc.issuer_url,
        enabled=container.settings.oidc.enabled,
        algorithms=container.settings.oidc.algorithms,
    )
    # Always attach OIDC provider to app (it won't be started if not enabled)
    container.app.state.oidc = oidc
    OIDCAuth.update_model(oidc)

    # Define /me endpoint
    @container.app.get(
        "/oidc/users/me", response_model=UserClaims, tags=["OpenID Connect"]
    )
    async def show_user(user: UserClaims = get_user()) -> UserClaims:
        return user

    # Define /me endpoint
    @container.app.get(
        "/oidc/users/me/jwt", response_model=UserClaims, tags=["OpenID Connect"]
    )
    async def get_user_jwt(
        request: fastapi.Request, user: UserClaims = get_user()
    ) -> UserClaims:
        authorization: str = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)
        return fastapi.responses.PlainTextResponse(token)

    return [oidc]


def get_user(roles: List[str] = [], all: bool = True) -> fastapi.params.Depends:
    """Get current user"""

    from quara.wiring.providers.oidc.provider import OIDCAuth

    async def _get_current_user_with_roles(
        user: UserClaims = fastapi.Security(OIDCAuth()),
        settings: OIDCSettings = get_settings(OIDCSettings),
    ) -> UserClaims:
        if not settings.enabled:
            return NO_AUTH_USER_CLAIMS
        if not roles:
            return user
        try:
            user.check_roles(*roles, require_all=all)
        except NotAllowedError:
            raise fastapi.HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="Not allowed",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user

    return fastapi.Depends(_get_current_user_with_roles)


__all__ = ["openid_connect_provider", "get_user"]
