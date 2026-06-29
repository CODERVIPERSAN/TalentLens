# TalentLens Pro — Pipeline & Hackathon Pitch Guide

> **Goal:** Win the Redrob ₹5L hackathon by ranking the right candidates — not the ones who keyword-stuffed their skills.

This document explains **what makes our solution stand out**, how each file works, and how to present it to judges.

---

## 1. Why this can win (our edge)

Most teams will build: *"count AI keywords in skills → sort descending"*

**That fails.** The challenge explicitly says:
- Marketing Manager with 9 AI skills = **trap**
- Tier-5 candidate who built recommendation systems but never says "RAG" = **real fit**
- Perfect profile + 5% response rate + inactive 6 months = **not hireable**
- >10% honeypots in top-100 = **disqualified**

### What TalentLens Pro does differently

| Feature | Others | TalentLens Pro |
|---------|--------|----------------|
| Primary signal | Skills keyword count | **Title + career history** |
| Keyword stuffers | Rank high | **Detected & demoted** |
| Behavioral signals | Ignored | **23 Redrob signals as multiplier** |
| Honeypots | Missed | **Timeline validation + audit** |
| Scale (100K) | Slow / API calls | **2-stage CPU pipeline < 5 min** |
| Explainability | Generic | **Per-candidate reasoning + confidence %** |
| Self-check | None | **Cross-check auditor + quality score** |
| Submission safety | Manual guess | **Honeypot rate + submission_ready flag** |

---

## 2. Architecture (3-stage pipeline)

```
┌─────────────────────────────────────────────────────────────────┐
│  INPUT: candidates.jsonl (100K) + job_description.txt           │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 1 — RECALL (fast, all 100K candidates)                   │
│  • TF-IDF semantic similarity to JD                             │
│  • Quick title score (kill Marketing Manager early)             │
│  • Honeypot pre-filter (impossible timelines → score 0)         │
│  • Keep top 2,500 for deep scoring                              │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 2 — PRECISION (deep scoring on 2,500 finalists)          │
│  • 8 base components (title 30%, career 24%, skills 18%...)    │
│  • Behavioral multiplier (response rate, notice, last active)   │
│  • Trap penalties (consulting, CV-only, LangChain, honeypot)   │
│  • Demote KEYWORD_STUFFER_TRAP to bottom of list                │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  STAGE 3 — AUDIT (cross-check every ranked candidate)           │
│  • Confidence score (signal agreement between title/career/skill)│
│  • Fit tier: Strong Fit / Good Fit / Borderline / Concern       │
│  • Flag traps: KEYWORD_STUFFER, HONEYPOT, LOW_ENGAGEMENT        │
│  • Quality report: honeypot rate, submission_ready               │
└────────────────────────────┬────────────────────────────────────┘
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│  OUTPUT: Top 100 CSV + UI matches + quality report              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. File-by-file reference

### Data (`data/`)

| File | What | Edit when |
|------|------|-----------|
| `sample_candidates.json` | 50 candidates for UI demo | Never — from challenge zip |
| `candidates.jsonl` | 100,000 candidates for submission | Extract from zip |
| `job.json` | Structured job listing (must-haves, disqualifiers) | Change job metadata |
| `job_description.txt` | Full JD text for ranker | Rarely — from challenge docx |
| `candidate_schema.json` | Schema reference | Reference only |

### Core engine

| File | What | Edit when |
|------|------|-----------|
| **`app/services/challenge_ranker.py`** | **Main ranker — Stage 1+2** | Change scoring weights/logic |
| **`app/services/rank_auditor.py`** | **Cross-check + confidence — Stage 3** | Change audit rules |
| `app/services/challenge_data.py` | Load data from zip/JSON | Change data paths |
| `rank.py` | CLI: produce submission CSV | Change CLI args |
| `validate_submission.py` | Official format validator | Don't edit |

### API

| File | What | Edit when |
|------|------|-----------|
| `app/api/v1/endpoints/challenge.py` | All `/challenge/*` endpoints | Add new API routes |
| `app/main.py` | FastAPI startup | CORS, app config |

### Frontend

| File | What | Edit when |
|------|------|-----------|
| `frontend/src/pages/Matches.jsx` | Ranker UI + quality report | Change match display |
| `frontend/src/pages/Jobs.jsx` | Job listing page | Job UI |
| `frontend/src/pages/Candidates.jsx` | Candidate table | Table columns |
| `frontend/src/api/client.js` | API calls | New endpoints |

### Scripts

| File | What |
|------|------|
| `scripts/extract_challenge_data.py` | Extract zip → `data/` |

---

## 4. Ranking formula (deep dive)

### Stage 2 base score (weights tuned for challenge traps)

```
base = title      × 0.30   ← DECISIVE (kills keyword stuffers)
     + career     × 0.24   ← IR/ranking/production in job descriptions
     + skills     × 0.18   ← core skills × trust multiplier
     + experience × 0.10   ← sweet spot 5–9 years
     + location   × 0.08   ← India cities preferred
     + semantic   × 0.06   ← TF-IDF vs JD
     + tenure     × 0.02   ← anti title-chaser
     + education  × 0.02   ← tier boost
```

### Then multiply:

```
final = base × behavioral × penalties
```

**Behavioral** (`redrob_signals`): response rate, notice period, last active date, recruiter saves, profile completeness, GitHub activity.

**Penalties**: consulting-only career (×0.45), CV-only without NLP (×0.40), LangChain-only (×0.55), honeypot (×0.03).

### Skill trust (anti keyword-stuffing)

```
IF endorsements > 30 AND duration_months < 6  → skill is STUFFED (ignored)
IF 3+ stuffed skills                          → trust × 0.7
```

### Career relevance (finds hidden gems)

Looks in `career_history[].description` for:
- `ranking`, `retrieval`, `recommendation`, `embedding`, `a/b test`, `ndcg`
- Product companies: Swiggy, Razorpay, Flipkart, etc.

A candidate who **never lists "RAG"** but describes building a recommendation system at Swiggy scores high on **career** — exactly what the JD hackathon note asks for.

---

## 5. Cross-check auditor (Stage 3)

File: `app/services/rank_auditor.py`

For each ranked candidate, checks **consistency** between independent signals:

| Flag | Meaning | Action |
|------|---------|--------|
| `KEYWORD_STUFFER_TRAP` | High skills, wrong title | Demoted in final sort |
| `SKILLS_WITHOUT_CAREER_PROOF` | Skills listed, no career evidence | Flagged |
| `HONEYPOT_SUSPECT` | Impossible timeline | Score near zero |
| `LOW_ENGAGEMENT` | Bad behavioral signals | Flagged |
| `CONSULTING_HEAVY` | Mostly services companies | Penalized |
| `TITLE_CHASER_PATTERN` | Many <15 month stints | Flagged |
| `LONG_NOTICE_PERIOD` | >90 days notice | Noted in reasoning |

### Confidence score (0–100%)

```
agreement = how closely title, career, skills scores align
confidence = agreement×35% + signal_mean×35% + final×20% + behavioral×10%
           - 8% per audit flag (max 4 flags)
```

### Fit tiers

| Tier | Criteria |
|------|----------|
| **Strong Fit** | confidence ≥78%, final ≥0.55, ≤1 flag |
| **Good Fit** | confidence ≥58%, final ≥0.40 |
| **Borderline** | confidence ≥38% |
| **Concern** | honeypot, keyword stuffer, or low confidence |

### Quality report (for whole ranking)

```json
{
  "quality_score": 100,
  "avg_confidence": 61.8,
  "strong_fit_count": 1,
  "honeypot_rate": 0.0,
  "honeypot_safe": true,
  "submission_ready": true,
  "recommendation": "EXCELLENT: High-confidence ranking ready for submission."
}
```

**Critical:** `honeypot_rate > 0.10` → `submission_ready: false` → blocked from submit.

---

## 6. API endpoints

| Endpoint | Method | Returns |
|----------|--------|---------|
| `/api/v1/challenge/job` | GET | Full job listing |
| `/api/v1/challenge/candidates` | GET | Paginated candidates |
| `/api/v1/challenge/rank` | POST | Job + matches + **quality_report** |
| `/api/v1/challenge/rankings` | GET | Cached last ranking |
| `/api/v1/challenge/audit` | GET | Audit report only |
| `/api/v1/challenge/export-csv` | GET | Download submission CSV |

### Rank request
```json
{ "use_sample": true, "top_n": 50 }
```

### Rank response (key fields)
```json
{
  "quality_report": { "quality_score": 100, "submission_ready": true, ... },
  "matches": [{
    "rank": 1,
    "score": 1.0,
    "reasoning": "Recommendation Systems Engineer at Swiggy with 6.0 yrs; ...",
    "audit": {
      "confidence": 82.2,
      "fit_tier": "Strong Fit",
      "audit_flags": []
    },
    "score_breakdown": { "title": 1.0, "career": 0.75, "skills": 0.82, ... }
  }]
}
```

---

## 7. UI walkthrough (for demo to judges)

1. **Dashboard** — shows 50 sample / 100K full pool stats
2. **Jobs** — real Senior AI Engineer listing from challenge data
3. **Candidates** — browse JSON candidates with skills/titles
4. **Matches** — click **Run Pro Ranker**:
   - Shows job being ranked against
   - **Quality Report** panel (score, confidence, honeypot rate)
   - Ranked list with **Strong Fit / Good Fit** badges
   - Expandable score breakdown per candidate
   - **Export CSV** button for submission

### Example top result (what judges should see)
```
#1 Recommendation Systems Engineer @ Swiggy
   Strong Fit · 82.2% confidence
   "shipped ranking/retrieval/production systems in career history"
   Flags: none
```

vs a trap candidate that other teams might rank high:
```
#47 Marketing Manager @ Some Corp
   Concern · 31% confidence
   Flags: KEYWORD_STUFFER_TRAP
```

---

## 8. How to run

### First-time data setup (challenge zip is NOT in git)

The PUB challenge bundle (~500MB) stays **on your machine only**. After cloning:

```bash
# Place the zip in project root (download from hackathon portal), then:
python scripts/extract_challenge_data.py --root .

# This creates:
#   data/sample_candidates.json   (tracked in git — small)
#   data/candidates.jsonl         (ignored — large, local only)
#   data/job_description.txt      (from docx if missing)
```

Or manually unzip `[PUB] India_runs_data_and_ai_challenge.zip` and copy `sample_candidates.json` into `data/`.

```bash
# Backend
cd TalentLens && source venv/bin/activate
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# Frontend
cd frontend && npm run dev -- --host 127.0.0.1 --port 3000

# Full submission (100K pool)
python rank.py --candidates data/candidates.jsonl --out team_xxx.csv --top-n 100
python validate_submission.py team_xxx.csv
```

---

## 9. Pitch script (30 seconds for judges)

> "We built a 3-stage CPU ranker for 100K candidates. Stage 1 does fast TF-IDF recall. Stage 2 deep-scores using title and career history — not keyword lists — because the challenge explicitly traps keyword stuffers. Stage 3 cross-checks every match for confidence, honeypots, and engagement signals. Our top pick is a Recommendation Systems Engineer at Swiggy with 82% confidence — someone who actually built ranking systems, not a Marketing Manager with 'LLM' in their skills. The UI shows a quality report with honeypot rate before you submit, so you never get disqualified for >10% honeypots."

---

## 10. What to improve next (priority order)

| # | Task | Impact on winning |
|---|------|-------------------|
| 1 | Run `rank.py` on full 100K, validate CSV | **Required to submit** |
| 2 | Deploy sandbox (HuggingFace Spaces) | **Required by challenge** |
| 3 | Pre-compute sentence-transformer embeddings offline | Better NDCG@10 |
| 4 | XGBoost LTR on feature vectors | Stronger precision |
| 5 | Fill `submission_metadata.yaml` with methodology | Stage 3/4 review |
| 6 | A/B compare vs naive keyword ranker in demo | Shows your edge visually |

---

## 11. Quick edit guide

| I want to… | Edit this file |
|------------|----------------|
| Change scoring weights | `app/services/challenge_ranker.py` → `_deep_score()` |
| Change trap detection rules | `app/services/rank_auditor.py` → `cross_check_candidate()` |
| Add API endpoint | `app/api/v1/endpoints/challenge.py` |
| Change job listing | `data/job.json` |
| Change match UI | `frontend/src/pages/Matches.jsx` |
| Change candidate table | `frontend/src/pages/Candidates.jsx` |
| Extract data from zip | `scripts/extract_challenge_data.py` |
| Produce submission CSV | `rank.py` |
| Validate submission | `validate_submission.py` |

---

## 12. Project structure

```
TalentLens/
├── data/                          # Challenge data from PUB zip
├── rank.py                        # CLI submission generator
├── validate_submission.py         # Official CSV validator
├── PIPELINE.md                    # This file
├── app/
│   ├── main.py
│   ├── api/v1/endpoints/
│   │   └── challenge.py           # REST API
│   └── services/
│       ├── challenge_data.py      # Data loader
│       ├── challenge_ranker.py    # ★ Stage 1+2 ranker
│       └── rank_auditor.py        # ★ Stage 3 auditor
├── scripts/
│   └── extract_challenge_data.py
└── frontend/src/
    ├── api/client.js
    └── pages/
        ├── Matches.jsx            # ★ Main demo page
        ├── Jobs.jsx
        └── Candidates.jsx
```
