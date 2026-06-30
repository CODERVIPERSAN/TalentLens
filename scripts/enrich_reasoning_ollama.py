#!/usr/bin/env python3
"""
Rewrite submission reasoning with local Ollama (Llama) — offline post-pass.

Does not re-score candidates. Loads profiles from jsonl/json and updates the
reasoning column for ranks 1..top_n.

Usage:
  python scripts/enrich_reasoning_ollama.py \\
    --input data/submission.csv \\
    --candidates data/candidates.jsonl \\
    --top-n 10 \\
    --model llama3.2
"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.challenge_ranker import RankedCandidate, find_candidate_by_id, write_submission
from app.services.ollama_reasoning import OllamaConfig, enrich_ranked_reasoning, is_ollama_available
from app.services.rank_auditor import cross_check_candidate
from app.services.reasoning_builder import build_reasoning


def load_submission(path: Path) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "candidate_id": row["candidate_id"],
                "rank": int(row["rank"]),
                "score": float(row["score"]),
                "reasoning": row["reasoning"],
            })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Enrich submission reasoning via local Ollama")
    parser.add_argument("--input", default="data/submission.csv", help="Submission CSV path")
    parser.add_argument("--candidates", required=True, help="Candidates json/jsonl path")
    parser.add_argument("--out", default=None, help="Output CSV (default: overwrite --input)")
    parser.add_argument("--top-n", type=int, default=10, help="Enrich ranks 1..N (default: 10)")
    parser.add_argument("--model", default="llama3.2", help="Ollama model tag")
    parser.add_argument("--timeout", type=float, default=20.0, help="Per-candidate timeout (seconds)")
    args = parser.parse_args()

    input_path = Path(args.input)
    candidates_path = Path(args.candidates)
    output_path = Path(args.out) if args.out else input_path

    if not input_path.exists():
        print(f"Error: submission not found: {input_path}", file=sys.stderr)
        return 1
    if not candidates_path.exists():
        print(f"Error: candidates not found: {candidates_path}", file=sys.stderr)
        return 1
    if not is_ollama_available():
        print("Error: Ollama not running — start with: ollama serve", file=sys.stderr)
        return 1

    submission_rows = load_submission(input_path)
    results: list[RankedCandidate] = []
    ollama_rows: list[tuple[RankedCandidate, dict, dict, dict]] = []

    for row in submission_rows:
        cid = str(row["candidate_id"])
        rank = int(row["rank"])
        candidate = find_candidate_by_id(candidates_path, cid)
        if candidate is None:
            print(f"Warning: candidate {cid} not found — keeping existing reasoning", file=sys.stderr)
            results.append(RankedCandidate(
                candidate_id=cid,
                rank=rank,
                score=float(row["score"]),
                reasoning=str(row["reasoning"]),
                profile_summary={},
            ))
            continue

        breakdown = {"title": 0.5, "career": 0.5, "skills": 0.5, "location": 0.5, "behavioral": 0.5, "jd_fit": 0.5}
        audit = cross_check_candidate(candidate, breakdown, rank=rank)
        reasoning = build_reasoning(candidate, breakdown, audit, rank)
        ranked = RankedCandidate(
            candidate_id=cid,
            rank=rank,
            score=float(row["score"]),
            reasoning=reasoning,
            profile_summary={},
        )
        results.append(ranked)
        if rank <= args.top_n:
            ollama_rows.append((ranked, candidate, breakdown, audit))

    cfg = OllamaConfig(enabled=True, model=args.model, top_n=args.top_n, timeout=args.timeout)
    enriched, fallback = enrich_ranked_reasoning(ollama_rows, model=cfg.model, top_n=cfg.top_n, host=cfg.host, timeout=cfg.timeout)
    print(f"Enriched {enriched} rows via Ollama ({cfg.model}), {fallback} fallbacks")

    write_submission(results, output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
