from __future__ import annotations

from typing import List, Optional

from pydantic import AnyHttpUrl, BaseModel, Extra

from .errors import NotAllowedError


class RealmAccess(BaseModel, extra=Extra.allow):
    """List of user roles."""

    roles: List[str]


class UserClaims(BaseModel, extra=Extra.allow):
    """Information about a user."""

    exp: int
    iat: int
    jti: str
    iss: AnyHttpUrl
    typ: str
    azp: str
    session_state: str
    acr: str
    email_verified: str
    name: Optional[str]
    preferred_username: str
    given_name: Optional[str]
    family_name: Optional[str]
    email: Optional[str]
    realm_access: RealmAccess

    def has_roles(self, *roles: str, require_all: bool = True) -> bool:
        """Return True if user has expected roles else False.

        By default, user must have all roles, but when "require_all" is set to False,
        only one role needs to be present.
        """
        if not roles:
            return True
        generator = (role in self.realm_access.roles for role in roles)
        if require_all:
            return all(generator)
        return any(generator)

    def check_roles(self, *roles: str, require_all: bool = True) -> None:
        """Check if expected roles are present, else raise NotAllowedError."""
        if not self.has_roles(*roles, require_all=require_all):
            raise NotAllowedError("User does not have required permissions")


NO_AUTH_USER_CLAIMS = UserClaims(
    exp=0,
    iat=0,
    jti=0,
    iss="http://no-auth",
    typ="no-auth",
    azp="",
    session_state="",
    acr="",
    email_verified="",
    name="no-auth",
    preferred_username="no-auth",
    email="no-auth@example.com",
    # All roles used within the application should be listed here
    realm_access=RealmAccess(roles=["read", "write", "admin"]),
)
