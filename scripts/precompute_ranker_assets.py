#!/usr/bin/env python3
"""
Offline pre-computation for TalentLens v4 ranker (ALLOWED per challenge rules).

1. Sentence-transformer embeddings for all candidates + JD (CPU, no network after model download)
2. HistGradientBoostingRegressor trained on heuristic labels from rule-based scorer

Run once before submission:
  python scripts/precompute_ranker_assets.py

Ranking at submit time loads cache from data/ranker_cache/ — no network, <5 min.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.challenge_ranker import _candidate_text, _light_recall_text, iter_candidates, load_candidates
from app.services.ltr_ranker import CACHE_DIR, EMB_PATH, FEATURE_NAMES, IDS_PATH, MODEL_PATH, extract_features
from app.services.fraud_detector import fraud_risk_score

DATA = ROOT / "data"
CANDIDATES = DATA / "candidates.jsonl"
JOB = DATA / "job_description.txt"
SAMPLE = DATA / "sample_candidates.json"


def _train_ltr(candidates_path: Path, job_text: str) -> None:
    from sklearn.ensemble import HistGradientBoostingRegressor
    import joblib

    from app.services.challenge_ranker import (
        _assessment_boost,
        _behavioral_multiplier,
        _career_relevance_score,
        _consulting_penalty,
        _core_skill_score,
        _cv_only_penalty,
        _deep_score,
        _education_boost,
        _experience_score,
        _ghost_penalty,
        _honeypot_penalty,
        _langchain_trap_penalty,
        _location_score,
        _research_only_penalty,
        _skill_names,
        _skill_trust_multiplier,
        _tenure_stability,
        _title_score,
    )
    from app.services.bm25_recall import BM25Index

    print("Loading candidates for LTR training (streamed sample)...")
    step = 16
    candidates = []
    for i, c in enumerate(iter_candidates(candidates_path)):
        if i % step == 0:
            candidates.append(c)
        if len(candidates) >= 6000:
            break
    texts = [_candidate_text(c) for c in candidates]
    bm25 = BM25Index(texts)
    bm25_top = {i: s for i, s in bm25.top_k(job_text, min(8000, len(candidates)))}

    X, y = [], []
    step = max(1, len(candidates) // 6000)
    for i in range(0, len(candidates), step):
        c = candidates[i]
        if fraud_risk_score(c) >= 0.9:
            continue
        profile = c.get("profile", {})
        skills = _skill_names(c)
        signals = c.get("redrob_signals", {})
        skill_trust = _skill_trust_multiplier(c)
        assessment = _assessment_boost(signals)
        product_co = sum(
            1 for j in c.get("career_history", [])
            if any(pc in j.get("company", "").lower() for pc in ("swiggy", "razorpay", "flipkart", "google", "meta", "amazon"))
        ) / max(len(c.get("career_history", [])), 1)
        ir_jobs = sum(
            1 for j in c.get("career_history", [])
            if any(k in f"{j.get('title','')} {j.get('description','')}".lower()
                   for k in ("ranking", "retrieval", "recommendation", "search", "embedding"))
        ) / max(len(c.get("career_history", [])), 1)

        _, breakdown = _deep_score(c, texts[i], 0.05)
        feat = extract_features(
            breakdown, bm25_top.get(i, 0.0), skill_trust, assessment,
            product_co, ir_jobs, signals, fraud_risk_score(c),
        )
        X.append(feat)
        y.append(breakdown.get("final", 0))

    X_arr = np.vstack(X)
    y_arr = np.array(y, dtype=np.float32)
    print(f"Training LTR on {len(y_arr)} samples, {len(FEATURE_NAMES)} features...")
    model = HistGradientBoostingRegressor(
        max_depth=8, learning_rate=0.08, max_iter=200, random_state=42,
    )
    model.fit(X_arr, y_arr)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    print(f"Saved LTR model -> {MODEL_PATH}")


def _compute_embeddings(candidates_path: Path, job_text: str) -> None:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError:
        print("sentence-transformers not installed; skipping embeddings. pip install sentence-transformers")
        return

    print("Loading sentence-transformer (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    candidates = load_candidates(candidates_path)
    texts = [_candidate_text(c) for c in candidates]
    ids = [c["candidate_id"] for c in candidates]

    print(f"Encoding {len(texts)} candidates (CPU batch)...")
    t0 = time.perf_counter()
    emb = model.encode(texts, batch_size=256, show_progress_bar=True, normalize_embeddings=True)
    jd_emb = model.encode([job_text], normalize_embeddings=True)[0]
    elapsed = time.perf_counter() - t0
    print(f"Embeddings done in {elapsed:.1f}s")

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    np.save(EMB_PATH, emb.astype(np.float32))
    IDS_PATH.write_text(json.dumps(ids), encoding="utf-8")
    np.save(CACHE_DIR / "jd_embedding.npy", jd_emb.astype(np.float32))
    print(f"Saved embeddings -> {EMB_PATH}")


def main() -> int:
    path = CANDIDATES if CANDIDATES.exists() else SAMPLE
    if not path.exists():
        print("No candidate file found")
        return 1
    job_text = JOB.read_text(encoding="utf-8")
    t0 = time.perf_counter()
    _compute_embeddings(path, job_text)
    _train_ltr(path, job_text)
    print(f"Precompute total: {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
