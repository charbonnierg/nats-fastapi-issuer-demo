from enum import Enum
from typing import Any, Dict, List

from fastapi import HTTPException, Request
from fastapi.openapi.models import OAuth2 as OAuth2Model
from fastapi.openapi.models import (
    OAuthFlowAuthorizationCode,
    OAuthFlowClientCredentials,
    OAuthFlowImplicit,
    OAuthFlowPassword,
)
from fastapi.openapi.models import OAuthFlows as OAuthFlowsModel
from fastapi.security.base import SecurityBase
from fastapi.security.utils import get_authorization_scheme_param
from starlette.status import HTTP_401_UNAUTHORIZED

from .errors import AuthorizationError, InvalidCredentialsError
from .models import NO_AUTH_USER_CLAIMS, UserClaims


class GrantType(str, Enum):
    AUTHORIZATION_CODE = "authorization_code"
    CLIENT_CREDENTIALS = "client_credentials"
    IMPLICIT = "implicit"
    PASSWORD = "password"


class Singleton(type):
    _instances: Dict["Singleton", "Singleton"] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> "Singleton":
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class OIDCAuth(SecurityBase, metaclass=Singleton):

    scheme_name = "openIdConnect"

    def __init__(self) -> None:
        self.grant_types: List[str] = [GrantType.IMPLICIT]
        flows = OAuthFlowsModel()
        self.model = OAuth2Model(flows=flows)

    async def __call__(self, request: Request) -> UserClaims:

        try:
            oidc = request.app.state.oidc
        except AttributeError:
            # We consider auth to be disabled when there is no OIDC provider
            return NO_AUTH_USER_CLAIMS
        # Bypass authentication when disabled
        if not oidc.enabled:
            return NO_AUTH_USER_CLAIMS

        authorization: str = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)

        try:
            if not authorization or scheme.lower() != "bearer":
                raise InvalidCredentialsError("No credentials found")

            return oidc.validate_token(token)  # type: ignore[no-any-return]

        except AuthorizationError:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @classmethod
    def update_model(cls, provider: Any) -> None:
        auth = cls()
        grant_types = set(provider.well_known["grant_types_supported"])
        grant_types = grant_types.intersection(auth.grant_types)

        flows = OAuthFlowsModel()

        authz_url: str = provider.well_known["authorization_endpoint"]
        token_url: str = provider.well_known["token_endpoint"]

        if GrantType.AUTHORIZATION_CODE in grant_types:
            flows.authorizationCode = OAuthFlowAuthorizationCode(
                authorizationUrl=authz_url,
                tokenUrl=token_url,
            )

        if GrantType.CLIENT_CREDENTIALS in grant_types:
            flows.clientCredentials = OAuthFlowClientCredentials(tokenUrl=token_url)

        if GrantType.PASSWORD in grant_types:
            flows.password = OAuthFlowPassword(tokenUrl=token_url)

        if GrantType.IMPLICIT in grant_types:
            flows.implicit = OAuthFlowImplicit(authorizationUrl=authz_url)

        auth.model.flows = flows  # type: ignore[attr-defined]
        # Since the class generates singleton, it should modify the value everywhere it's used
        auth.model.openIdConnectUrl = provider.issuer_url  # type: ignore[attr-defined]
