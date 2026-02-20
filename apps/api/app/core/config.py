import os
from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ALLOWED_RBAC_ROLES = {"admin", "compliance_analyst", "read_only"}


class Settings(BaseSettings):
    app_name: str = "eu-fintech-reg-assistant-api"
    app_environment: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_connection_timeout_seconds: float = 10.0
    neo4j_vector_dimensions: int | None = None
    neo4j_vector_similarity: str = "cosine"
    neo4j_max_retries: int = 2
    neo4j_retry_backoff_seconds: float = 0.2
    embed_provider: str = "hash"
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    embed_device: str | None = None
    embed_batch_size: int = 16
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str | None = None
    llm_timeout_seconds: float = 30.0
    llm_max_retries: int = 2
    auth_enabled: bool = False
    oidc_provider: Literal["entra", "generic"] = "entra"
    oidc_tenant_id: str | None = None
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    oidc_jwks_timeout_seconds: float = 5.0
    oidc_roles_claim: str = "roles"
    oidc_groups_claim: str = "groups"
    oidc_group_role_map: dict[str, str] = Field(default_factory=dict)
    service_token: str | None = None
    auto_migrate_on_startup: bool = False
    rate_limit_enabled: bool = False
    rate_limit_requests_per_minute: int = 120
    rate_limit_window_seconds: int = 60
    rate_limit_backend: Literal["memory", "redis"] = "memory"
    rate_limit_redis_url: str | None = None
    rate_limit_trust_proxy: bool = True
    rate_limit_fail_open: bool = True
    rate_limit_route_limits: dict[str, int] = Field(default_factory=dict)

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def vector_dimensions(self) -> int:
        return self.neo4j_vector_dimensions or self.embed_dim

    @model_validator(mode="after")
    def validate_security(self) -> "Settings":
        if self.auth_enabled:
            if not self.oidc_issuer:
                raise ValueError("oidc_issuer_required_when_auth_enabled")
            if not self.oidc_jwks_url:
                raise ValueError("oidc_jwks_url_required_when_auth_enabled")
            if not self.oidc_audience:
                raise ValueError("oidc_audience_required_when_auth_enabled")
        if self.app_environment == "production" and not self.auth_enabled:
            raise ValueError("auth_must_be_enabled_in_production")
        if self.oidc_provider == "entra" and self.auth_enabled and not self.oidc_tenant_id:
            raise ValueError("oidc_tenant_id_required_for_entra_provider")
        for mapped_role in self.oidc_group_role_map.values():
            if mapped_role not in ALLOWED_RBAC_ROLES:
                raise ValueError("oidc_group_role_map_contains_invalid_role")
        if self.rate_limit_enabled and self.rate_limit_backend == "redis" and not self.rate_limit_redis_url:
            raise ValueError("rate_limit_redis_url_required_for_redis_backend")
        if self.rate_limit_window_seconds <= 0:
            raise ValueError("rate_limit_window_seconds_must_be_positive")
        for route_limit in self.rate_limit_route_limits.values():
            if route_limit <= 0:
                raise ValueError("rate_limit_route_limit_must_be_positive")
        if self.embed_batch_size <= 0:
            raise ValueError("embed_batch_size_must_be_positive")
        if (
            self.embed_provider.lower() == "hf"
            and self.neo4j_vector_dimensions is not None
            and self.neo4j_vector_dimensions != self.embed_dim
        ):
            raise ValueError("neo4j_vector_dimensions_must_match_embed_dim_for_hf_provider")
        return self


@lru_cache
def get_settings() -> Settings:
    env_file = os.getenv("APP_ENV_FILE", ".env")
    return Settings(_env_file=env_file)  # type: ignore[call-arg]
