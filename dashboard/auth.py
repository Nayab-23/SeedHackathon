"""Token-based authentication middleware.

Supports Bearer token in Authorization header or openclaw_token cookie.
"""

from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

_admin_token: str = ""


def set_admin_token(token: str):
    """Set the admin token for authentication."""
    global _admin_token
    _admin_token = token


def get_admin_token() -> str:
    """Return the configured admin token."""
    return _admin_token


_bearer_scheme = HTTPBearer(auto_error=False)


async def verify_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> bool:
    """Verify authentication from Bearer header or cookie.

    Raises HTTPException 401 if not authenticated.
    """
    # Check Bearer header first
    if credentials and credentials.credentials == _admin_token:
        return True

    # Check cookie
    cookie_token = request.cookies.get("openclaw_token")
    if cookie_token and cookie_token == _admin_token:
        return True

    raise HTTPException(status_code=401, detail="invalid token")
