import hashlib
import math
import re
from functools import lru_cache
from typing import List, Sequence

from ingest.config import get_settings

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def embed_text(text: str) -> List[float]:
    return embed_texts([text])[0]


def embed_texts(texts: Sequence[str]) -> List[List[float]]:
    settings = get_settings()
    provider = settings.embed_provider.lower()
    if provider == "hash":
        return [hash_embedding(text, settings.vector_dimensions) for text in texts]
    if provider == "hf":
        return hf_embeddings(texts)
    raise ValueError("unknown_embed_provider")


def hash_embedding(text: str, dimensions: int) -> List[float]:
    tokens = TOKEN_RE.findall(text.lower())
    if not tokens:
        return [0.0] * dimensions
    vector = [0.0] * dimensions
    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0.0:
        return vector
    return [value / norm for value in vector]


def hf_embedding(text: str) -> List[float]:
    return hf_embeddings([text])[0]


def hf_embeddings(texts: Sequence[str]) -> List[List[float]]:
    text_values = list(texts)
    if not text_values:
        return []
    settings = get_settings()
    model = get_hf_model()
    vectors = model.encode(
        text_values,
        batch_size=max(1, settings.embed_batch_size),
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    embeddings = vectors.tolist()
    for embedding in embeddings:
        if len(embedding) != settings.vector_dimensions:
            raise ValueError("embedding_dimension_mismatch")
    return embeddings


def resolve_hf_device(configured_device: str | None) -> str:
    if configured_device:
        return configured_device
    try:
        import torch

        if torch.cuda.is_available():
            return "cuda"
    except Exception:
        pass
    return "cpu"


@lru_cache
def get_hf_model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    device = resolve_hf_device(settings.embed_device)
    return SentenceTransformer(settings.embed_model, device=device)
