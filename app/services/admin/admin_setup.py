from typing import Optional
from fastapi import FastAPI
from starlette.requests import Request
from starlette.responses import Response
from starlette_admin.contrib.sqla import Admin
from starlette_admin.auth import AdminUser, AuthProvider
from starlette_admin.exceptions import FormValidationError

from app.core.config import settings
from app.core.database import engine


class AdminAuthProvider(AuthProvider):
    async def login(
        self,
        username: str,
        password: str,
        remember_me: bool,
        request: Request,
        response: Response,
    ) -> Response:
        if password == settings.ADMIN_AUTH_SECRET:
            request.session.update({"admin_user": username})
            return response
        raise FormValidationError({"password": "Invalid admin credentials"})

    async def is_authenticated(self, request: Request) -> bool:
        return request.session.get("admin_user") is not None

    def get_admin_user(self, request: Request) -> Optional[AdminUser]:
        username = request.session.get("admin_user")
        if username:
            return AdminUser(username=username)
        return None

    async def logout(self, request: Request, response: Response) -> Response:
        request.session.clear()
        return response


def setup_admin(app: FastAPI) -> Admin:
    """Configure and mount StarletteAdmin dashboard at /admin."""
    auth_provider = AdminAuthProvider()
    admin = Admin(
        engine,
        title="AI News Admin",
        base_url="/admin",
        auth_provider=auth_provider,
    )
    admin.mount_to(app)
    return admin
