import logging
import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any

import requests
from fastapi import Depends, Header, HTTPException, Request, status
from jose import JWTError, jwt

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_JWKS_CACHE_TTL_SECONDS = 300
_jwks_cache: dict[str, Any] = {"url": None, "expires_at": 0.0, "keys": []}


class Role(str, Enum):
    ADMIN = "admin"
    COMPLIANCE_ANALYST = "compliance_analyst"
    READ_ONLY = "read_only"


ROLE_ALIASES = {
    "admin": Role.ADMIN,
    "compliance_analyst": Role.COMPLIANCE_ANALYST,
    "compliance-analyst": Role.COMPLIANCE_ANALYST,
    "read_only": Role.READ_ONLY,
    "readonly": Role.READ_ONLY,
    "read-only": Role.READ_ONLY,
}


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: set[Role]
    token_type: str


def _parse_bearer_token(authorization: str | None) -> str | None:
    if not authorization:
        return None
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _claim_values(claims: dict[str, Any], claim_name: str) -> list[str]:
    raw_claim: Any = claims.get(claim_name)
    if raw_claim is None:
        return []
    if isinstance(raw_claim, str):
        return [value for value in re.split(r"[,\s]+", raw_claim.strip()) if value]
    if isinstance(raw_claim, list):
        return [str(value).strip() for value in raw_claim if str(value).strip()]
    return []


def _map_role_values(role_values: list[str]) -> set[Role]:
    roles: set[Role] = set()
    for value in role_values:
        role = ROLE_ALIASES.get(value.lower())
        if role:
            roles.add(role)
    return roles


def _map_group_claims_to_roles(group_values: list[str], group_role_map: dict[str, str]) -> set[Role]:
    mapped: set[Role] = set()
    for group in group_values:
        mapped_role_name = group_role_map.get(group)
        if not mapped_role_name:
            continue
        mapped_role = ROLE_ALIASES.get(mapped_role_name.lower())
        if mapped_role:
            mapped.add(mapped_role)
    return mapped


def _parse_roles(claims: dict[str, Any], settings: Settings) -> set[Role]:
    role_values = _claim_values(claims, settings.oidc_roles_claim)
    direct_roles = _map_role_values(role_values)
    if direct_roles:
        return direct_roles
    if settings.oidc_group_role_map:
        groups = _claim_values(claims, settings.oidc_groups_claim)
        return _map_group_claims_to_roles(groups, settings.oidc_group_role_map)
    return set()


def _fetch_jwks(jwks_url: str, timeout_seconds: float) -> list[dict[str, Any]]:
    now = time.time()
    if (
        _jwks_cache.get("url") == jwks_url
        and _jwks_cache.get("expires_at", 0.0) > now
        and _jwks_cache.get("keys")
    ):
        return _jwks_cache["keys"]

    response = requests.get(jwks_url, timeout=timeout_seconds)
    response.raise_for_status()
    payload = response.json()
    keys = payload.get("keys", [])
    if not isinstance(keys, list) or not keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="jwks_keys_unavailable",
        )
    _jwks_cache["url"] = jwks_url
    _jwks_cache["expires_at"] = now + _JWKS_CACHE_TTL_SECONDS
    _jwks_cache["keys"] = keys
    return keys


def _decode_user_token(token: str) -> Principal:
    settings = get_settings()
    assert settings.oidc_issuer is not None
    assert settings.oidc_audience is not None
    assert settings.oidc_jwks_url is not None

    try:
        header = jwt.get_unverified_header(token)
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token_header") from exc

    kid = header.get("kid")
    alg = header.get("alg", "RS256")
    if not kid:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token_kid")

    try:
        keys = _fetch_jwks(settings.oidc_jwks_url, settings.oidc_jwks_timeout_seconds)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("jwks_fetch_failed")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="jwks_fetch_failed") from exc

    signing_key = next((key for key in keys if key.get("kid") == kid), None)
    if signing_key is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="signing_key_not_found")

    try:
        claims = jwt.decode(
            token,
            signing_key,
            algorithms=[alg],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"verify_aud": True},
        )
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token") from exc

    subject = str(claims.get("sub", "")).strip()
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_token_subject")
    if settings.oidc_provider == "entra":
        tenant_id = str(claims.get("tid", "")).strip()
        if not tenant_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_tenant_claim")
        if settings.oidc_tenant_id and tenant_id != settings.oidc_tenant_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_tenant")

    return Principal(
        subject=subject,
        roles=_parse_roles(claims, settings),
        token_type="user",
    )


def get_current_principal(
    request: Request,
    authorization: str | None = Header(default=None),
    x_service_token: str | None = Header(default=None, alias="X-Service-Token"),
) -> Principal:
    settings = get_settings()

    if settings.service_token and x_service_token:
        if not secrets.compare_digest(x_service_token, settings.service_token):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_service_token")
        principal = Principal(subject="service", roles={Role.ADMIN}, token_type="service")
        request.state.principal = principal
        return principal

    if not settings.auth_enabled:
        principal = Principal(subject="anonymous", roles={Role.ADMIN}, token_type="disabled")
        request.state.principal = principal
        return principal

    token = _parse_bearer_token(authorization)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing_bearer_token")

    principal = _decode_user_token(token)
    request.state.principal = principal
    return principal


def require_roles(*roles: Role) -> Callable[[Principal], Principal]:
    allowed = set(roles)

    def _dependency(principal: Principal = Depends(get_current_principal)) -> Principal:
        if not allowed:
            return principal
        if principal.roles.intersection(allowed):
            return principal
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="forbidden")

    return _dependency
