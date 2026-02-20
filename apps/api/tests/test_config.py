import pytest

from app.core.config import Settings


def base_settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "neo4j_uri": "bolt://localhost:7687",
        "neo4j_user": "neo4j",
        "neo4j_password": "password",
    }
    defaults.update(overrides)
    return Settings(**defaults)


def test_embed_batch_size_must_be_positive():
    with pytest.raises(ValueError, match="embed_batch_size_must_be_positive"):
        base_settings(embed_batch_size=0)


def test_hf_provider_requires_matching_vector_dimensions():
    with pytest.raises(ValueError, match="neo4j_vector_dimensions_must_match_embed_dim_for_hf_provider"):
        base_settings(
            embed_provider="hf",
            neo4j_vector_dimensions=1536,
            embed_dim=1024,
        )


def test_hf_provider_allows_matching_vector_dimensions():
    settings = base_settings(
        embed_provider="hf",
        neo4j_vector_dimensions=1024,
        embed_dim=1024,
    )
    assert settings.vector_dimensions == 1024
