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

    results = run_ranking(candidates_path, job_path, output_path, top_n=args.top_n)
    print(f"Ranked {len(results)} candidates -> {output_path}")
    if results:
        print(f"Top candidate: {results[0].candidate_id} (score={results[0].score})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
