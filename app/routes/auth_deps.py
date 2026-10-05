from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.core.config import settings
from app.core.jwt import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


def get_current_account(
    request: Request,
    bearer_token: str | None = Depends(oauth2_scheme),
) -> str:
    """Extract authenticated account identity from cookie or Bearer token header."""
    cookie_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    token = cookie_token or bearer_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return decode_access_token(token)
