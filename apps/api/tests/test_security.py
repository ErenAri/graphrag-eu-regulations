from dataclasses import dataclass

import pytest
from fastapi import HTTPException

from app.core.security import (
    Principal,
    Role,
    _parse_roles,
    get_current_principal,
    require_roles,
)


class DummyState:
    pass


class DummyRequest:
    def __init__(self) -> None:
        self.state = DummyState()


@dataclass
class DummySettings:
    auth_enabled: bool = False
    service_token: str | None = None
    oidc_provider: str = "entra"
    oidc_tenant_id: str | None = "tenant-1"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    llm_timeout_seconds: float = 5.0
    oidc_jwks_timeout_seconds: float = 5.0
    oidc_roles_claim: str = "roles"
    oidc_groups_claim: str = "groups"
    oidc_group_role_map: dict[str, str] = None

    def __post_init__(self) -> None:
        if self.oidc_group_role_map is None:
            self.oidc_group_role_map = {}


def test_get_current_principal_allows_when_auth_disabled(monkeypatch):
    monkeypatch.setattr("app.core.security.get_settings", lambda: DummySettings(auth_enabled=False))
    request = DummyRequest()
    principal = get_current_principal(request=request, authorization=None, x_service_token=None)
    assert principal.token_type == "disabled"
    assert Role.ADMIN in principal.roles


def test_get_current_principal_accepts_valid_service_token(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.get_settings",
        lambda: DummySettings(auth_enabled=True, service_token="internal-secret"),
    )
    request = DummyRequest()
    principal = get_current_principal(request=request, authorization=None, x_service_token="internal-secret")
    assert principal.token_type == "service"
    assert principal.subject == "service"
    assert Role.ADMIN in principal.roles


def test_get_current_principal_rejects_invalid_service_token(monkeypatch):
    monkeypatch.setattr(
        "app.core.security.get_settings",
        lambda: DummySettings(auth_enabled=True, service_token="internal-secret"),
    )
    request = DummyRequest()
    with pytest.raises(HTTPException) as exc:
        get_current_principal(request=request, authorization=None, x_service_token="invalid")
    assert exc.value.status_code == 401


def test_require_roles_blocks_insufficient_role():
    dependency = require_roles(Role.ADMIN)
    with pytest.raises(HTTPException) as exc:
        dependency(Principal(subject="u1", roles={Role.READ_ONLY}, token_type="user"))
    assert exc.value.status_code == 403


def test_require_roles_allows_authorized_role():
    dependency = require_roles(Role.ADMIN, Role.COMPLIANCE_ANALYST)
    principal = Principal(subject="u1", roles={Role.COMPLIANCE_ANALYST}, token_type="user")
    assert dependency(principal) == principal


def test_parse_roles_uses_canonical_roles_claim():
    settings = DummySettings(
        oidc_roles_claim="roles",
        oidc_group_role_map={"group-a": "admin"},
    )
    claims = {"roles": ["read_only"], "groups": ["group-a"]}
    parsed = _parse_roles(claims, settings)  # type: ignore[arg-type]
    assert parsed == {Role.READ_ONLY}


def test_parse_roles_falls_back_to_group_mapping():
    settings = DummySettings(
        oidc_roles_claim="roles",
        oidc_group_role_map={"group-a": "compliance_analyst"},
    )
    claims = {"groups": ["group-a", "group-b"]}
    parsed = _parse_roles(claims, settings)  # type: ignore[arg-type]
    assert parsed == {Role.COMPLIANCE_ANALYST}
