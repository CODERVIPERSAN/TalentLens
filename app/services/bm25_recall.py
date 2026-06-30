"""BM25 lexical recall with inverted index (fast on 100K+ docs)."""

from __future__ import annotations

import math
import re
from typing import Sequence


_TOKEN = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN.findall(text.lower())


class BM25Index:
    def __init__(self, corpus: Sequence[str], k1: float = 1.4, b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.docs: list[list[str]] = [_tokenize(t) for t in corpus]
        self.n = len(self.docs)
        self.avgdl = sum(len(d) for d in self.docs) / max(self.n, 1)
        self.df: dict[str, int] = {}
        self.postings: dict[str, list[tuple[int, int]]] = {}
        for i, doc in enumerate(self.docs):
            tf: dict[str, int] = {}
            for term in doc:
                tf[term] = tf.get(term, 0) + 1
            for term, freq in tf.items():
                self.df[term] = self.df.get(term, 0) + 1
                self.postings.setdefault(term, []).append((i, freq))
        self.idf: dict[str, float] = {
            t: math.log(1 + (self.n - df + 0.5) / (df + 0.5))
            for t, df in self.df.items()
        }
        self.doc_lens = [len(d) for d in self.docs]

    def score_document(self, doc_idx: int, query_terms: list[str]) -> float:
        doc = self.docs[doc_idx]
        if not doc:
            return 0.0
        dl = self.doc_lens[doc_idx]
        tf: dict[str, int] = {}
        for t in doc:
            tf[t] = tf.get(t, 0) + 1
        s = 0.0
        for term in query_terms:
            if term not in tf:
                continue
            idf = self.idf.get(term, 0.0)
            freq = tf[term]
            denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
            s += idf * (freq * (self.k1 + 1)) / denom
        return s

    def top_k(self, query: str, k: int) -> list[tuple[int, float]]:
        qterms = _tokenize(query)
        if not qterms:
            return []
        # Accumulate scores only for docs containing query terms
        accum: dict[int, float] = {}
        for term in qterms:
            idf = self.idf.get(term, 0.0)
            if idf <= 0:
                continue
            for doc_idx, freq in self.postings.get(term, []):
                dl = self.doc_lens[doc_idx]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                accum[doc_idx] = accum.get(doc_idx, 0.0) + idf * (freq * (self.k1 + 1)) / denom
        if not accum:
            return []
        scored = sorted(accum.items(), key=lambda x: -x[1])
        return scored[:k]
