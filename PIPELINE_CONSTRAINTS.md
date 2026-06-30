# PUB Challenge Constraints (TalentLens v4)

> Source: `[PUB] India_runs_data_and_ai_challenge/` + `submission_metadata_template.yaml` + JD `job_description.txt`

## Hard constraints (must follow or submission is invalid)

| Constraint | Rule | How we comply |
|------------|------|---------------|
| **CPU only** | No GPU during ranking | `uses_gpu_for_inference: false` — sklearn + BM25 + optional ST embeddings on CPU |
| **Time limit** | ≤ 5 minutes on 100K | Benchmark: **~2.5 min** with LTR; **~1.9 min** without embeddings |
| **Memory** | ≤ 16 GB RAM | Stream jsonl load; shortlist 5K for deep scoring; mmap embeddings |
| **No network** | Zero API calls during `rank.py` | No OpenAI/LLM at rank time; precompute offline only |
| **Output format** | CSV: `candidate_id,rank,score,reasoning` × 100 rows | `validate_submission.py` passes |
| **Honeypots** | ~80 fraud profiles; **>10% in top-100 = disqualified** | `fraud_detector.py` — timeline, notice>180d, endorsement fraud |
| **Filename** | `team_xxx.csv` (participant ID) | Rename at submit |

## What is allowed offline (before ranking)

- Train LTR model: `python scripts/precompute_ranker_assets.py`
- Pre-compute sentence-transformer embeddings (all-MiniLM-L6-v2)
- Download model weights once (not during ranking)
- Use LLMs for **development** only — never feed candidate data to APIs at rank time

## JD traps (accuracy matters more than keywords)

| Trap type | Example | Detection |
|-----------|---------|-------------|
| Keyword stuffer | Marketing Manager + 5 AI skills | `KEYWORD_STUFFER_TRAP` — title gate + demotion |
| Hidden gem | Recsys engineer at Swiggy, no "RAG" in skills | Career-history boost ×1.18 |
| Ghost | Inactive 6+ mo + ≤5% response rate | `GHOST_UNAVAILABLE` — ×0.06 penalty |
| Honeypot | 13 yrs exp but 11 months total jobs | `HONEYPOT_SUSPECT` — ×0.02 penalty |
| Consulting-only | Entire career at TCS/Infosys | `CONSULTING_ONLY` — ×0.42 |
| CV-only | Vision/robotics, no NLP/IR | `CV_ONLY_PROFILE` — ×0.38 |
| LangChain-only | LangChain demos, no production ML | LangChain trap — ×0.55 |
| Research-only | PhD lab, no shipped systems | `RESEARCH_ONLY` — ×0.50 |

## Confidence targets (our quality gates)

| Band | Target | v4 result (100K pool) |
|------|--------|----------------------|
| Top 10 | **100%** confidence | ✅ 100.0% avg |
| Top 50 | **95%** confidence | ✅ 96.1% avg |
| Honeypot rate | < 10% | ✅ 0% |

## Low-memory mode (~8GB RAM)

Auto-enabled when `MemAvailable` &lt; 2.5GB (or `TALENTLENS_LOW_MEMORY=1`):

| Behavior | Detail |
|----------|--------|
| Streaming rank | 3-pass jsonl — never loads 100K profiles at once |
| Persist submission | Auto-writes `data/submission.csv` after UI rank or `rank.py` |
| Recall shortlist | 3000 (vs 5000) |
| TF-IDF features | 6000 (vs 10000) |
| Embedding cache | Skipped at rank time |

```bash
# Force low-memory behavior
TALENTLENS_LOW_MEMORY=1 python rank.py --candidates data/candidates.jsonl --out team_xxx.csv
```


```bash
# One-time offline (allowed)
python scripts/precompute_ranker_assets.py

# Submission (must finish ≤5 min, no network)
python rank.py --candidates data/candidates.jsonl --out team_xxx.csv --top-n 100
python validate_submission.py team_xxx.csv

# Compliance tests
python scripts/test_jd_compliance.py
```
