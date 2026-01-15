import hashlib
import math
import re
from functools import lru_cache
from typing import List

from ingest.config import get_settings

TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def embed_text(text: str) -> List[float]:
    settings = get_settings()
    provider = settings.embed_provider.lower()
    if provider == "hash":
        return hash_embedding(text, settings.vector_dimensions)
    if provider == "hf":
        return hf_embedding(text)
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
    settings = get_settings()
    model = get_hf_model()
    vector = model.encode([text], normalize_embeddings=True)
    embedding = vector[0].tolist()
    if len(embedding) != settings.vector_dimensions:
        raise ValueError("embedding_dimension_mismatch")
    return embedding


@lru_cache
def get_hf_model():
    from sentence_transformers import SentenceTransformer

    settings = get_settings()
    device = settings.embed_device or "cpu"
    return SentenceTransformer(settings.embed_model, device=device)
