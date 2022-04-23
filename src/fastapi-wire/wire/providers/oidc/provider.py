import json
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
import jwt
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


class OIDCAuthProvider:
    def __init__(
        self,
        *,
        issuer_url: str,
        audience: str = "api",
        enabled: bool = True,
        algorithms: Optional[List[str]] = None,
    ) -> None:
        """Create a new OIDCAuthClient."""
        self.issuer_url = issuer_url
        self.well_known_uri = f"{issuer_url}/.well-known/openid-configuration"
        self.audience = ["account", audience]
        self.algorithms = algorithms or ["RS256"]
        self.http = httpx.Client()
        self.enabled = enabled
        # Load resources on __init__
        if self.enabled:
            self.__load_server_metadata__(self.well_known_uri)
            self.__load_public_key__()

    def __load_server_metadata__(self, well_known_uri: str) -> None:
        """Load the metadata from the well-known URI."""
        resp = self.http.get(well_known_uri)
        self.well_known: Dict[str, Any] = resp.json()

    def __load_public_key__(self) -> None:
        """Load public key used to validate tokens."""
        resp = self.http.get(self.well_known["jwks_uri"])
        jwks = resp.json()
        # Look for RS256 algorithm
        for jwk in jwks["keys"]:
            if jwk["alg"].upper() in self.algorithms:
                self.alg = jwk["alg"].upper()
                break
        else:
            raise Exception(
                f"OpenID Connect issuer does not support any of the accepted algorithms: {self.algorithms}"
            )
        # Load public key
        self.public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    def validate_token(self, token: str) -> UserClaims:
        """Validate JWT token signature and expiration"""
        try:
            return UserClaims(**self.decode_token(token))
        except (jwt.DecodeError, jwt.ExpiredSignatureError):
            raise InvalidCredentialsError("Invalid token")

    def decode_token(self, token: str) -> Dict[str, Any]:
        """Decode a given access token."""
        return dict(
            jwt.decode(
                token,
                key=self.public_key,
                algorithms=[self.alg],
                audience=self.audience,
            )
        )


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

        oidc: OIDCAuthProvider = request.app.state.oidc
        # Bypass authentication when disabled
        if not oidc.enabled:
            return NO_AUTH_USER_CLAIMS

        authorization: str = request.headers.get("Authorization")
        scheme, token = get_authorization_scheme_param(authorization)

        try:
            if not authorization or scheme.lower() != "bearer":
                raise InvalidCredentialsError("No credentials found")

            return oidc.validate_token(token)

        except AuthorizationError:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    @classmethod
    def update_model(cls, provider: OIDCAuthProvider) -> None:
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
