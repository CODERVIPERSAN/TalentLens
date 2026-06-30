#!/usr/bin/env python3
"""
JD compliance test suite for Redrob hackathon ranker.

Validates that ranking follows the JD intent (not keyword stuffing):
- Trap candidates demoted / excluded from top ranks
- Career-history proof boosts Tier-5 profiles without buzzwords
- Ghost/inactive candidates down-weighted
- Honeypot rate in top-100 stays below 10%
- Ranking completes within CPU time budget on available pool
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.challenge_ranker import load_candidates, rank_candidates, run_ranking
from app.services.rank_auditor import audit_ranking
from app.services.rank_features import (
    has_career_ir_proof,
    is_ghost_unavailable,
    is_weak_title,
    keyword_stuffer_risk,
)

DATA = ROOT / "data"
SAMPLE = DATA / "sample_candidates.json"
FULL = DATA / "candidates.jsonl"
JOB = DATA / "job_description.txt"


def _fail(msg: str) -> None:
    print(f"  FAIL: {msg}")
    raise AssertionError(msg)


def _ok(msg: str) -> None:
    print(f"  OK: {msg}")


def test_trap_detection_logic() -> None:
    print("\n[1] Trap detection logic")
    assert keyword_stuffer_risk(0.12, 0.75, 0.15), "marketing+skills trap"
    assert not keyword_stuffer_risk(0.90, 0.75, 0.50), "strong title should pass"
    assert is_weak_title("Marketing Manager", "AI enthusiast")
    _ok("keyword stuffer + weak title detection")


def test_ghost_detection() -> None:
    print("\n[2] Ghost / unavailable detection")
    ghost = {"last_active_date": "2024-01-01", "recruiter_response_rate": 0.03}
    active = {"last_active_date": "2026-05-01", "recruiter_response_rate": 0.6}
    assert is_ghost_unavailable(ghost)
    assert not is_ghost_unavailable(active)
    _ok("6mo inactive + 5% response flagged as ghost")


def test_sample_ranking_quality() -> None:
    print("\n[3] Sample pool ranking (50 candidates)")
    if not SAMPLE.exists():
        print("  SKIP: sample_candidates.json missing")
        return

    jd = JOB.read_text(encoding="utf-8")
    t0 = time.perf_counter()
    results = rank_candidates(load_candidates(SAMPLE), jd, top_n=min(50, 50))
    elapsed = time.perf_counter() - t0

    assert len(results) > 0, "no results"
    assert elapsed < 30, f"sample rank too slow: {elapsed:.1f}s"
    _ok(f"ranked {len(results)} in {elapsed:.2f}s")

    audit_input = [
        {"rank": r.rank, "audit": r.audit, "candidate_id": r.candidate_id}
        for r in results
    ]
    report = audit_ranking(audit_input)
    print(f"       quality={report['quality_score']} honeypot_rate={report['honeypot_rate']}")
    print(f"       top10_avg_conf={report['top10_avg_confidence']} top50_avg_conf={report['top50_avg_confidence']}")

    if report["honeypot_rate"] > 0.10:
        _fail(f"honeypot rate {report['honeypot_rate']} > 10%")

    top_flags = []
    for r in results[:20]:
        top_flags.extend(r.audit.get("audit_flags", []))
    trap_in_top10 = sum(
        1 for r in results[:10]
        if "KEYWORD_STUFFER_TRAP" in r.audit.get("audit_flags", [])
        or "GHOST_UNAVAILABLE" in r.audit.get("audit_flags", [])
        or "HONEYPOT_SUSPECT" in r.audit.get("audit_flags", [])
    )
    if trap_in_top10 > 0:
        _fail(f"{trap_in_top10} trap-flagged candidates in top-10")
    _ok("no hard traps in top-10")

    # Top ranks should have career IR proof OR strong title
    weak_top = 0
    for r in results[:10]:
        title = r.profile_summary.get("title", "")
        if is_weak_title(title):
            weak_top += 1
    if weak_top > 0:
        _fail(f"{weak_top} weak-title candidates in top-10")
    _ok("top-10 free of Marketing Manager-style titles")


def test_career_history_over_keywords() -> None:
    print("\n[4] Career history beats keyword stuffing")
    if not SAMPLE.exists():
        print("  SKIP")
        return

    candidates = load_candidates(SAMPLE)
    jd = JOB.read_text(encoding="utf-8")
    results = rank_candidates(candidates, jd, top_n=50)
    by_id = {c["candidate_id"]: c for c in candidates}

    career_boosted = 0
    for r in results[:15]:
        c = by_id.get(r.candidate_id)
        if not c:
            continue
        skills = {s.get("name", "").lower() for s in c.get("skills", [])}
        ai_kw = sum(1 for s in skills if any(k in s for k in ("embed", "retriev", "rank", "llm", "rag")))
        if ai_kw < 3 and has_career_ir_proof(c) and r.rank <= 15:
            career_boosted += 1
    if career_boosted == 0:
        print("  WARN: no career-proof/low-keyword candidates in top-15 (pool may lack them)")
    else:
        _ok(f"{career_boosted} career-proof candidates in top-15 without heavy AI keywords")


def test_full_pool_if_available() -> None:
    print("\n[5] Full 100K pool (if data/candidates.jsonl exists)")
    if not FULL.exists():
        print("  SKIP: extract with scripts/extract_challenge_data.py")
        return

    t0 = time.perf_counter()
    out = ROOT / "data" / "test_submission.csv"
    results = run_ranking(FULL, JOB, output_path=out, top_n=100)
    elapsed = time.perf_counter() - t0

    assert len(results) == 100, f"expected 100 rows, got {len(results)}"
    if elapsed > 300:
        _fail(f"full rank exceeded 5min budget: {elapsed:.1f}s")
    _ok(f"100K ranked in {elapsed:.1f}s ({elapsed/60:.1f} min)")

    report = audit_ranking([{"rank": r.rank, "audit": r.audit} for r in results])
    print(f"       quality={report['quality_score']} honeypot_rate={report['honeypot_rate']}")
    print(f"       submission_ready={report['submission_ready']}")
    print(f"       recommendation: {report['recommendation']}")

    if report["honeypot_rate"] > 0.10:
        _fail("honeypot rate >10% on full pool")
    if report["top10_avg_confidence"] < 98:
        _fail(f"top-10 avg confidence {report['top10_avg_confidence']} < 98")
    if len(results) >= 50 and report["top50_avg_confidence"] < 95:
        _fail(f"top-50 avg confidence {report['top50_avg_confidence']} < 95")
    _ok(f"confidence: top10={report['top10_avg_confidence']} top50={report['top50_avg_confidence']}")


def test_submission_csv_format() -> None:
    print("\n[6] Submission CSV format")
    sub = ROOT / "data" / "test_submission.csv"
    if not sub.exists():
        print("  SKIP: run full pool test first")
        return

    lines = sub.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0] == "candidate_id,rank,score,reasoning"
    assert len(lines) == 101, f"expected 101 lines (header+100), got {len(lines)}"
    ranks = [int(l.split(",")[1]) for l in lines[1:]]
    assert ranks == list(range(1, 101)), "ranks must be 1..100"
    _ok("CSV has 100 rows with ranks 1-100")


def main() -> int:
    print("=" * 60)
    print("TalentLens JD Compliance Tests")
    print("=" * 60)
    passed = 0
    tests = [
        test_trap_detection_logic,
        test_ghost_detection,
        test_sample_ranking_quality,
        test_career_history_over_keywords,
        test_full_pool_if_available,
        test_submission_csv_format,
    ]
    for fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError:
            print(f"\n❌ {fn.__name__} failed")
            return 1
        except Exception as e:
            print(f"\n❌ {fn.__name__} error: {e}")
            return 1

    print("\n" + "=" * 60)
    print(f"All {passed}/{len(tests)} test groups passed")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
