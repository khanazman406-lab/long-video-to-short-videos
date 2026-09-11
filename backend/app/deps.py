"""Shared FastAPI dependencies: auth-ready user stub, friendly errors."""

from __future__ import annotations

from fastapi import Header

from .utils.security import ValidationError


async def get_current_user(authorization: str | None = Header(default=None)) -> dict | None:
    """Authentication integration point.

    Returns None (anonymous) today. To add auth, validate the bearer token
    here and return the user record; all routes already accept this dependency.
    """
    _ = authorization
    return None


def to_user_error(exc: Exception) -> tuple[int, str]:
    if isinstance(exc, ValidationError):
        msg = str(exc)
        if "not found" in msg.lower():
            return 404, msg
        return 400, msg
    return 500, "Something went wrong. Please try again."
