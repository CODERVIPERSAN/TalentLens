import hashlib
import math
from functools import lru_cache
from typing import List, Optional, Union

import numpy as np

from app.core.config import settings

# Dimension used for the local fallback embeddings. Kept small but expressive
# enough for cosine-similarity comparisons when OpenAI is not configured.
LOCAL_EMBEDDING_DIM = 256


@lru_cache(maxsize=1)
def _get_client():
    """Lazily build the OpenAI client so the app can start without a key."""
    if not settings.openai_enabled:
        return None
    from openai import OpenAI

    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _local_embedding(text: str) -> List[float]:
    """
    Deterministic, dependency-free embedding used when OpenAI is unavailable.

    Hashes tokens into a fixed-size bag-of-words vector and L2-normalizes it so
    cosine similarity remains meaningful for matching.
    """
    vec = np.zeros(LOCAL_EMBEDDING_DIM, dtype=np.float64)
    tokens = [t for t in text.lower().split() if t]
    for token in tokens:
        digest = hashlib.md5(token.encode("utf-8")).hexdigest()
        index = int(digest, 16) % LOCAL_EMBEDDING_DIM
        vec[index] += 1.0

    norm = np.linalg.norm(vec)
    if norm > 0:
        vec = vec / norm
    return vec.tolist()


def _embed_one(text: str) -> List[float]:
    client = _get_client()
    if client is None:
        return _local_embedding(text)

    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


def generate_embedding(text: Union[str, List[str]]) -> Union[List[float], List[List[float]]]:
    """
    Generate embeddings for text.

    Uses OpenAI when configured, otherwise falls back to a local deterministic
    embedding so the matching pipeline works without external dependencies.
    """
    if isinstance(text, str):
        return _embed_one(text)

    return [_embed_one(t) for t in text]


def calculate_similarity(
    embedding1: Optional[List[float]], embedding2: Optional[List[float]]
) -> float:
    """Calculate cosine similarity between two embeddings."""
    if not embedding1 or not embedding2:
        return 0.0

    vec1 = np.array(embedding1, dtype=np.float64)
    vec2 = np.array(embedding2, dtype=np.float64)

    if vec1.shape != vec2.shape:
        return 0.0

    dot_product = float(np.dot(vec1, vec2))
    norm1 = float(np.linalg.norm(vec1))
    norm2 = float(np.linalg.norm(vec2))

    if norm1 == 0 or norm2 == 0:
        return 0.0

    similarity = dot_product / (norm1 * norm2)
    if math.isnan(similarity):
        return 0.0
    return float(similarity)
