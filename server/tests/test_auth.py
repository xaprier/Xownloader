import pytest
from fastapi import HTTPException
from pydantic import SecretStr

from xownloader_server.auth import AuthService, Scope
from xownloader_server.config import Settings


def test_client_token_cannot_access_admin_scope() -> None:
    service = AuthService(
        Settings(
            environment="production",
            client_api_token=SecretStr("client-token"),
            admin_api_token=SecretStr("admin-token"),
        )
    )

    service.authorize("Bearer client-token", Scope.CLIENT)
    with pytest.raises(HTTPException) as error:
        service.authorize("Bearer client-token", Scope.ADMIN)

    assert error.value.status_code == 401


def test_admin_token_can_access_client_scope() -> None:
    service = AuthService(
        Settings(
            environment="production",
            client_api_token=SecretStr("client-token"),
            admin_api_token=SecretStr("admin-token"),
        )
    )

    service.authorize("Bearer admin-token", Scope.CLIENT)
    service.authorize("Bearer admin-token", Scope.ADMIN)


def test_production_requires_token() -> None:
    service = AuthService(Settings(environment="production"))

    with pytest.raises(HTTPException) as error:
        service.authorize(None, Scope.CLIENT)

    assert error.value.status_code == 401
