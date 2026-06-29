"""Load challenge assets from the PUB India hackathon bundle."""

from __future__ import annotations

import gzip
import json
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
ZIP_PATH = DATA_DIR.parent / "[PUB] India_runs_data_and_ai_challenge.zip"
BUNDLE_PREFIX = "[PUB] India_runs_data_and_ai_challenge/India_runs_data_and_ai_challenge"

SAMPLE_CANDIDATES = DATA_DIR / "sample_candidates.json"
FULL_CANDIDATES = DATA_DIR / "candidates.jsonl"
JOB_JSON = DATA_DIR / "job.json"
JOB_DESCRIPTION = DATA_DIR / "job_description.txt"


def ensure_challenge_data() -> None:
    """Extract key files from the PUB zip if missing."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ZIP_PATH.exists():
        return

    targets = {
        "sample_candidates.json": SAMPLE_CANDIDATES,
        "candidate_schema.json": DATA_DIR / "candidate_schema.json",
        "validate_submission.py": DATA_DIR.parent / "validate_submission.py",
    }

    with zipfile.ZipFile(ZIP_PATH) as zf:
        for name, dest in targets.items():
            if dest.exists():
                continue
            src = f"{BUNDLE_PREFIX}/{name}"
            if src in zf.namelist():
                dest.write_bytes(zf.read(src))

        if not FULL_CANDIDATES.exists() and not FULL_CANDIDATES.is_symlink():
            src = f"{BUNDLE_PREFIX}/candidates.jsonl"
            if src in zf.namelist():
                with zf.open(src) as src_f, open(FULL_CANDIDATES, "wb") as dst_f:
                    while chunk := src_f.read(8 * 1024 * 1024):
                        dst_f.write(chunk)


def get_job() -> dict[str, Any]:
    ensure_challenge_data()
    job = json.loads(JOB_JSON.read_text(encoding="utf-8"))
    if JOB_DESCRIPTION.exists():
        job["description"] = JOB_DESCRIPTION.read_text(encoding="utf-8")
    return job


def get_candidates_path(use_sample: bool = False) -> Path:
    """Return candidate file path. Default: full pool if available."""
    ensure_challenge_data()
    if use_sample and SAMPLE_CANDIDATES.exists():
        return SAMPLE_CANDIDATES
    if FULL_CANDIDATES.exists():
        return FULL_CANDIDATES
    if SAMPLE_CANDIDATES.exists():
        return SAMPLE_CANDIDATES
    raise FileNotFoundError("No candidate data found. Extract the PUB challenge zip into data/")


def pool_info() -> dict[str, Any]:
    ensure_challenge_data()
    sample_available = SAMPLE_CANDIDATES.exists()
    full_available = FULL_CANDIDATES.exists()
    sample_count = 0
    full_count = 0

    if sample_available:
        with open(SAMPLE_CANDIDATES, encoding="utf-8") as f:
            sample_count = len(json.load(f))
    if full_available:
        with open(FULL_CANDIDATES, encoding="utf-8") as f:
            full_count = sum(1 for line in f if line.strip())

    return {
        "sample_available": sample_available,
        "full_available": full_available,
        "sample_count": sample_count,
        "full_count": full_count,
    }


def load_candidates_page(path: Path, skip: int = 0, limit: int = 50) -> tuple[list[dict[str, Any]], int]:
    """Load a page of candidates without reading entire jsonl into memory."""
    suffixes = "".join(path.suffixes).lower()
    if suffixes == ".json":
        with open(path, encoding="utf-8") as f:
            all_c = json.load(f)
        if not isinstance(all_c, list):
            all_c = [all_c]
        return all_c[skip : skip + limit], len(all_c)

    page: list[dict[str, Any]] = []
    total = 0
    opener = gzip.open(path, "rt", encoding="utf-8") if suffixes.endswith(".gz") else open(path, encoding="utf-8")
    with opener as f:
        for line in f:
            if not line.strip():
                continue
            if total >= skip and len(page) < limit:
                page.append(json.loads(line))
            total += 1
    return page, total


def get_data_sources() -> dict[str, Any]:
    """Report which files exist, sizes, and last modified times."""
    ensure_challenge_data()
    sources = {}
    for key, path in [
        ("sample_candidates", SAMPLE_CANDIDATES),
        ("full_candidates", FULL_CANDIDATES),
        ("job_json", JOB_JSON),
        ("job_description", JOB_DESCRIPTION),
    ]:
        if path.exists():
            stat = path.stat()
            sources[key] = {
                "path": str(path),
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            }
        else:
            sources[key] = None

    pools = pool_info()
    return {
        **pools,
        "sources": sources,
        "default_pool": "full" if pools["full_available"] else "sample",
        "active_ranker_file": str(get_candidates_path(use_sample=False)),
    }
