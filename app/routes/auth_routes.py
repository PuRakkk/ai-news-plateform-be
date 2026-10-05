from fastapi import APIRouter, Depends, Response
from app.core.config import settings
from app.core.jwt import create_access_token
from app.routes.auth_deps import get_current_account
from app.schemas.auth import AccountProfile, LoginRequest, TokenResponse

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/login", response_model=TokenResponse)
def login(request_data: LoginRequest, response: Response) -> TokenResponse:
    # In a full setup, password is verified against repository
    token = create_access_token(subject=str(request_data.email))
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite="lax",
        max_age=settings.JWT_EXPIRE_MINUTES * 60,
    )
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout(response: Response) -> dict[str, str]:
    response.delete_cookie(key=settings.AUTH_COOKIE_NAME)
    return {"status": "logged_out"}


@router.get("/me", response_model=AccountProfile)
def get_profile(current_account: str = Depends(get_current_account)) -> AccountProfile:
    return AccountProfile(email=current_account, is_active=True)
