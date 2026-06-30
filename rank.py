#!/usr/bin/env python3
"""
Produce a hackathon submission CSV from candidate data.

Usage:
  python rank.py --candidates ./data/sample_candidates.json --out ./submission.csv
  python rank.py --candidates ./candidates.jsonl --out ./team_xxx.csv
"""

import argparse
import sys
from pathlib import Path

from app.services.challenge_ranker import run_ranking
from app.services.ollama_reasoning import OllamaConfig, is_ollama_available


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank candidates for the Redrob JD")
    parser.add_argument(
        "--candidates",
        required=True,
        help="Path to candidates.json, .jsonl, or .jsonl.gz",
    )
    parser.add_argument(
        "--job-description",
        default="data/job_description.txt",
        help="Path to job description text file",
    )
    parser.add_argument(
        "--out",
        default="data/submission.csv",
        help="Output CSV path (default: data/submission.csv)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=100,
        help="Number of candidates to rank (default: 100)",
    )
    parser.add_argument(
        "--ollama",
        action="store_true",
        help="Enrich reasoning with local Ollama (Llama) after ranking — localhost only",
    )
    parser.add_argument(
        "--ollama-model",
        default="llama3.2",
        help="Ollama model tag (default: llama3.2)",
    )
    parser.add_argument(
        "--ollama-top-n",
        type=int,
        default=10,
        help="Rewrite reasoning for ranks 1..N via Ollama (default: 10)",
    )
    args = parser.parse_args()

    candidates_path = Path(args.candidates)
    job_path = Path(args.job_description)
    output_path = Path(args.out)

    if not candidates_path.exists():
        print(f"Error: candidates file not found: {candidates_path}", file=sys.stderr)
        return 1
    if not job_path.exists():
        print(f"Error: job description not found: {job_path}", file=sys.stderr)
        return 1

    ollama_cfg = None
    if args.ollama:
        if not is_ollama_available():
            print("Warning: Ollama not reachable at localhost:11434 — rule-based reasoning only", file=sys.stderr)
        ollama_cfg = OllamaConfig(
            enabled=True,
            model=args.ollama_model,
            top_n=args.ollama_top_n,
        )

    results = run_ranking(
        candidates_path,
        job_path,
        output_path,
        top_n=args.top_n,
        ollama=ollama_cfg,
    )
    print(f"Ranked {len(results)} candidates -> {output_path}")
    if args.ollama and ollama_cfg:
        print(f"Ollama reasoning: model={args.ollama_model}, top {args.ollama_top_n} ranks")
    if results:
        print(f"Top candidate: {results[0].candidate_id} (score={results[0].score})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
