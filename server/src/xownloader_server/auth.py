from enum import StrEnum

from fastapi import HTTPException, Request, status
from pydantic import SecretStr

from xownloader_server.config import Settings


class Scope(StrEnum):
    CLIENT = "client"
    ADMIN = "admin"


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.environment = settings.environment
        self.client_token = self._value(settings.client_api_token)
        self.admin_token = self._value(settings.admin_api_token)

    @staticmethod
    def _value(token: SecretStr | None) -> str | None:
        return token.get_secret_value() if token else None

    def authorize(self, authorization: str | None, scope: Scope) -> None:
        if not self.client_token and not self.admin_token and self.environment == "development":
            return
        if not authorization or not authorization.startswith("Bearer "):
            raise self._unauthorized()

        token = authorization.removeprefix("Bearer ").strip()
        if token == self.admin_token:
            return
        if scope == Scope.CLIENT and token == self.client_token:
            return
        raise self._unauthorized()

    @staticmethod
    def _unauthorized() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid API token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_client_scope(request: Request) -> None:
    request.app.state.auth.authorize(request.headers.get("Authorization"), Scope.CLIENT)


def require_admin_scope(request: Request) -> None:
    request.app.state.auth.authorize(request.headers.get("Authorization"), Scope.ADMIN)
