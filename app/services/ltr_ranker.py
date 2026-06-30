"""
Learning-to-rank feature extraction + optional pre-trained GBM model.

Offline: scripts/precompute_ranker_assets.py trains HistGradientBoostingRegressor.
Online: loads model from data/ranker_cache/ltr_model.joblib if present.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

CACHE_DIR = Path("data/ranker_cache")
MODEL_PATH = CACHE_DIR / "ltr_model.joblib"
EMB_PATH = CACHE_DIR / "embeddings.npy"
IDS_PATH = CACHE_DIR / "candidate_ids.json"

FEATURE_NAMES = [
    "title", "career", "skills", "experience", "location", "semantic", "bm25",
    "behavioral", "penalties", "tenure", "education", "skill_trust",
    "assessment", "product_co", "ir_jobs", "open_to_work", "response_rate",
    "notice_norm", "active_norm", "fraud_risk",
]


def extract_features(
    breakdown: dict[str, float],
    bm25_score: float,
    skill_trust: float,
    assessment: float,
    product_co: float,
    ir_jobs: float,
    signals: dict[str, Any],
    fraud_risk: float,
) -> np.ndarray:
    from app.services.rank_features import parse_date
    from datetime import date

    rr = float(signals.get("recruiter_response_rate", 0.5))
    notice = float(signals.get("notice_period_days", 60))
    last = parse_date(signals.get("last_active_date"))
    days_active = (date.today() - last).days if last else 365
    active_norm = max(0.0, 1.0 - days_active / 365.0)

    return np.array([
        breakdown.get("title", 0),
        breakdown.get("career", 0),
        breakdown.get("skills", 0),
        breakdown.get("experience", 0),
        breakdown.get("location", 0),
        breakdown.get("semantic", 0),
        min(bm25_score / 40.0, 1.0),
        breakdown.get("behavioral", 1),
        breakdown.get("penalties", 1),
        breakdown.get("tenure", 0.8),
        breakdown.get("education", 0.75),
        skill_trust,
        assessment,
        product_co,
        ir_jobs,
        1.0 if signals.get("open_to_work_flag") else 0.0,
        rr,
        max(0.0, 1.0 - notice / 120.0),
        active_norm,
        fraud_risk,
    ], dtype=np.float32)


def load_ltr_model():
    if not MODEL_PATH.exists():
        return None
    try:
        import joblib
        return joblib.load(MODEL_PATH)
    except Exception:
        return None


def load_embedding_index() -> tuple[list[str], np.ndarray] | None:
    if not EMB_PATH.exists() or not IDS_PATH.exists():
        return None
    try:
        ids = json.loads(IDS_PATH.read_text(encoding="utf-8"))
        emb = np.load(EMB_PATH, mmap_mode="r")
        return ids, emb
    except Exception:
        return None


def embedding_similarity(candidate_id: str, jd_embedding: np.ndarray | None, index: tuple[list[str], np.ndarray] | None) -> float:
    if index is None or jd_embedding is None:
        return 0.0
    ids, emb = index
    try:
        idx = ids.index(candidate_id)
    except ValueError:
        return 0.0
    vec = np.asarray(emb[idx], dtype=np.float32)
    denom = (np.linalg.norm(vec) * np.linalg.norm(jd_embedding)) + 1e-9
    sim = float(np.dot(vec, jd_embedding) / denom)
    return max(0.0, (sim + 1) / 2)


def predict_ltr(model, features: np.ndarray) -> float:
    if model is None:
        return float(np.mean(features[:8]))
    pred = model.predict(features.reshape(1, -1))[0]
    return float(np.clip(pred, 0.0, 1.5))
