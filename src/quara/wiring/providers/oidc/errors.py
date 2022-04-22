from __future__ import annotations


class AuthorizationError(Exception):
    code = 403
    details = "Unauthorized"


class InvalidCredentialsError(AuthorizationError):
    code = 403
    details = "Invalid credentials"


class NotAllowedError(AuthorizationError):
    code = 403
    details = "Not allowed"
