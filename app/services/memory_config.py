"""Low-memory helpers for ranking on constrained machines (~8GB RAM)."""

from __future__ import annotations

import gc
import os


def low_memory_mode() -> bool:
    """True when we should use streaming / reduced caches."""
    env = os.environ.get("TALENTLENS_LOW_MEMORY", "").lower()
    if env in ("1", "true", "yes"):
        return True
    if env in ("0", "false", "no"):
        return False
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    kb = int(line.split()[1])
                    return kb < 2_500_000
    except OSError:
        pass
    return False


def recall_top_k() -> int:
    return 3000 if low_memory_mode() else 5000


def tfidf_max_features() -> int:
    return 6000 if low_memory_mode() else 10000


def use_embedding_cache() -> bool:
    """Precomputed embeddings use mmap — safe even in low-memory mode."""
    return True


def release_memory() -> None:
    gc.collect()
