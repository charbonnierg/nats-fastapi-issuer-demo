from __future__ import annotations

from typing import List

import fastapi
from fastapi.security.utils import get_authorization_scheme_param
from starlette.status import HTTP_403_FORBIDDEN

from demo_app.container import AppContainer
from demo_app.providers.oidc.errors import NotAllowedError
from demo_app.settings import AppSettings

from .models import UserClaims
from .provider import OIDCAuth, OIDCAuthProvider

current_user = OIDCAuth()


def get_user(roles: List[str] = [], all: bool = True):  # type: ignore[no-untyped-def]
    async def _get_current_user_with_roles(
        user: UserClaims = fastapi.Security(current_user),
    ) -> UserClaims:
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


def oidc_provider(container: AppContainer[AppSettings]) -> None:
    if container.settings.oidc.enabled:
        # Set client ID on swagger UI
        container.app.swagger_ui_init_oauth[  # type: ignore[index]
            "clientId"
        ] = container.settings.oidc.client_id
    # Create oidc provider
    oidc = OIDCAuthProvider(
        issuer_url=container.settings.oidc.issuer_url,
        enabled=container.settings.oidc.enabled,
        algorithms=container.settings.oidc.algorithms,
    )
    if oidc.enabled:
        OIDCAuth.update_model(oidc)
    # Attach oidc provider to app
    container.app.state.oidc = oidc

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
        request: fastapi.Request, _: UserClaims = get_user()
    ) -> UserClaims:
        authorization: str = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)
        return fastapi.responses.PlainTextResponse(token)


__all__ = ["oidc_provider", "current_user", "get_user"]
