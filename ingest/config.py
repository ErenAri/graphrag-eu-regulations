from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    neo4j_uri: str
    neo4j_user: str
    neo4j_password: str
    neo4j_vector_dimensions: int | None = None
    neo4j_vector_similarity: str = "cosine"
    embed_provider: str = "hash"
    embed_model: str = "BAAI/bge-m3"
    embed_dim: int = 1024
    embed_device: str | None = None

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    @property
    def vector_dimensions(self) -> int:
        return self.neo4j_vector_dimensions or self.embed_dim


@lru_cache
def get_settings() -> Settings:
    return Settings()
