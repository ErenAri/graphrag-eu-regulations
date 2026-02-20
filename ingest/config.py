import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_connection_timeout_seconds: float = 10.0
    neo4j_vector_dimensions: int | None = None
    neo4j_vector_similarity: str = "cosine"
    embed_provider: str = "hash"
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    embed_device: str | None = None
    embed_batch_size: int = 16
    http_timeout_seconds: float = 30.0
    http_max_retries: int = 2
    http_retry_backoff_seconds: float = 0.25

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")

    @property
    def vector_dimensions(self) -> int:
        return self.neo4j_vector_dimensions or self.embed_dim

    @model_validator(mode="after")
    def validate_embedding(self) -> "Settings":
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
    env_file = os.getenv("INGEST_ENV_FILE") or os.getenv("APP_ENV_FILE", ".env")
    return Settings(_env_file=env_file)  # type: ignore[call-arg]
