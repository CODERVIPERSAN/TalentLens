"""Memory-efficient BM25 — build stats in one pass, score in a second."""

from __future__ import annotations

import math
import re
from collections import Counter
from typing import Iterator, Sequence


_TOKEN = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class StreamingBM25:
    """BM25 scorer built from corpus statistics (no full corpus stored)."""

    def __init__(
        self,
        n_docs: int,
        avgdl: float,
        doc_freq: Counter[str],
        k1: float = 1.4,
        b: float = 0.75,
    ) -> None:
        self.n = n_docs
        self.avgdl = avgdl
        self.k1 = k1
        self.b = b
        self.idf = {
            t: math.log(1 + (n_docs - df + 0.5) / (df + 0.5))
            for t, df in doc_freq.items()
        }

    @classmethod
    def from_token_streams(cls, token_streams: Iterator[list[str]]) -> StreamingBM25:
        doc_freq: Counter[str] = Counter()
        total_len = 0
        n = 0
        for tokens in token_streams:
            n += 1
            total_len += len(tokens)
            for t in set(tokens):
                doc_freq[t] += 1
        avgdl = total_len / max(n, 1)
        return cls(n, avgdl, doc_freq)

    def score(self, tokens: list[str]) -> float:
        if not tokens:
            return 0.0
        dl = len(tokens)
        tf: Counter[str] = Counter(tokens)
        s = 0.0
        for term, freq in tf.items():
            idf = self.idf.get(term)
            if idf is None:
                continue
            denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s += idf * (freq * (self.k1 + 1)) / denom
        return s


class BM25Index:
    """In-memory BM25 for small corpora (sample pool)."""

    def __init__(self, corpus: Sequence[str], k1: float = 1.4, b: float = 0.75) -> None:
        self._bm25 = StreamingBM25.from_token_streams(tokenize(t) for t in corpus)
        self._tokenized = [tokenize(t) for t in corpus]
        self.n = len(corpus)

    def top_k(self, query: str, k: int) -> list[tuple[int, float]]:
        qterms = tokenize(query)
        if not qterms:
            return []
        scored = [
            (i, self._bm25.score(self._tokenized[i]))
            for i in range(self.n)
            if any(t in self._tokenized[i] for t in qterms)
        ]
        scored.sort(key=lambda x: -x[1])
        return scored[:k]
