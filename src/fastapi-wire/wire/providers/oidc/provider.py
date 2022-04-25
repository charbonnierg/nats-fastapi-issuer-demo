import json
from typing import Any, Dict, List, Optional

import httpx
import jwt

from .errors import InvalidCredentialsError
from .models import UserClaims


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
