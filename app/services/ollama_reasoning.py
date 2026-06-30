"""
Local Ollama (Llama) reasoning — localhost only, no external APIs.

Use after ranking or with rank.py --ollama. Falls back to rule-based text on
timeout or when Ollama is unavailable.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.services.reasoning_builder import build_reasoning

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
DEFAULT_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.2")
DEFAULT_TOP_N = int(os.environ.get("TALENTLENS_OLLAMA_TOP_N", "10"))
DEFAULT_TIMEOUT = float(os.environ.get("TALENTLENS_OLLAMA_TIMEOUT", "20"))


@dataclass
class OllamaConfig:
    enabled: bool = False
    model: str = DEFAULT_MODEL
    top_n: int = DEFAULT_TOP_N
    timeout: float = DEFAULT_TIMEOUT
    host: str = OLLAMA_HOST


def ollama_config_from_env() -> OllamaConfig:
    flag = os.environ.get("TALENTLENS_OLLAMA", "").lower() in ("1", "true", "yes")
    return OllamaConfig(
        enabled=flag,
        model=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL),
        top_n=int(os.environ.get("TALENTLENS_OLLAMA_TOP_N", str(DEFAULT_TOP_N))),
        timeout=float(os.environ.get("TALENTLENS_OLLAMA_TIMEOUT", str(DEFAULT_TIMEOUT))),
        host=OLLAMA_HOST,
    )


def is_ollama_available(host: str = OLLAMA_HOST, timeout: float = 2.0) -> bool:
    try:
        response = httpx.get(f"{host}/api/tags", timeout=timeout)
        return response.status_code == 200
    except (httpx.HTTPError, OSError):
        return False


def _profile_block(candidate: dict[str, Any]) -> str:
    profile = candidate.get("profile", {})
    skills = [s.get("name", "") for s in candidate.get("skills", [])[:10] if s.get("name")]
    signals = candidate.get("redrob_signals", {})
    lines = [
        f"Title: {profile.get('current_title', 'N/A')}",
        f"Company: {profile.get('current_company', 'N/A')}",
        f"Location: {profile.get('location', 'N/A')}",
        f"Experience: {profile.get('years_of_experience', 'N/A')} yrs",
        f"Headline: {profile.get('headline', '')}",
        f"Skills: {', '.join(skills) if skills else 'N/A'}",
        f"Response rate: {signals.get('recruiter_response_rate', 'N/A')}",
        f"Notice (days): {signals.get('notice_period_days', 'N/A')}",
        f"Open to work: {signals.get('open_to_work_flag', 'N/A')}",
    ]
    career_bits: list[str] = []
    for job in candidate.get("career_history", [])[:3]:
        career_bits.append(
            f"- {job.get('title', '?')} @ {job.get('company', '?')} "
            f"({job.get('duration_months', '?')} mo)"
        )
    if career_bits:
        lines.append("Recent roles:\n" + "\n".join(career_bits))
    return "\n".join(lines)


def build_ollama_prompt(
    candidate: dict[str, Any],
    breakdown: dict[str, float],
    audit: dict[str, Any],
    rank: int,
    rule_based: str,
) -> str:
    flags = audit.get("audit_flags") or []
    tier = audit.get("fit_tier", "Good Fit")
    breakdown_line = ", ".join(f"{k}={v}" for k, v in sorted(breakdown.items()) if k != "final")
    return f"""You write one unique ranking justification for a Senior AI Engineer founding-team hire.

JD focus: Python, embeddings, retrieval/ranking, vector search, RAG, LLM fine-tuning, production ML.
Location: India (Pune/Noida). Experience sweet spot: 5–9 years.

Candidate rank: #{rank}
Fit tier: {tier}
Score breakdown: {breakdown_line}
Audit flags: {', '.join(flags) if flags else 'none'}

Profile:
{_profile_block(candidate)}

Accurate fact draft (rewrite in your own words — do not invent facts):
{rule_based}

Rules:
- Output ONLY the final reasoning paragraph (no preamble, no bullets).
- Mention rank #{rank} explicitly.
- Rank 1–10: cite concrete strengths AND why not higher if rank > 1.
- Rank 11–50: one strength + primary gap.
- Rank 51–100: one sentence strength + one sentence limitation.
- Max 110 words. Plain English. No markdown."""


def _clean_response(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^[\"']|[\"']$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:900]


def generate_ollama_reasoning(
    candidate: dict[str, Any],
    breakdown: dict[str, float],
    audit: dict[str, Any],
    rank: int,
    *,
    model: str = DEFAULT_MODEL,
    host: str = OLLAMA_HOST,
    timeout: float = DEFAULT_TIMEOUT,
    rule_based: str | None = None,
) -> str | None:
    baseline = rule_based or build_reasoning(candidate, breakdown, audit, rank)
    prompt = build_ollama_prompt(candidate, breakdown, audit, rank, baseline)
    num_predict = 140 if rank <= 10 else (100 if rank <= 50 else 70)
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"num_predict": num_predict, "temperature": 0.35},
    }
    try:
        response = httpx.post(
            f"{host}/api/generate",
            json=payload,
            timeout=timeout,
        )
        response.raise_for_status()
        body = response.json()
        text = _clean_response(body.get("response", ""))
        return text if len(text) >= 40 else None
    except (httpx.HTTPError, OSError, ValueError):
        return None


def enrich_ranked_reasoning(
    rows: list[tuple[Any, dict[str, Any], dict[str, float], dict[str, Any]]],
    *,
    model: str = DEFAULT_MODEL,
    top_n: int = DEFAULT_TOP_N,
    host: str = OLLAMA_HOST,
    timeout: float = DEFAULT_TIMEOUT,
) -> tuple[int, int]:
    """
    Rewrite reasoning for ranks 1..top_n via Ollama.
    Each row: (ranked_result, candidate, breakdown, audit).
    Mutates ranked_result.reasoning in place. Returns (enriched_count, fallback_count).
    """
    if not is_ollama_available(host):
        return 0, min(len(rows), top_n)

    enriched = 0
    fallback = 0
    for ranked, candidate, breakdown, audit in rows[:top_n]:
        rank = getattr(ranked, "rank", 0)
        baseline = ranked.reasoning
        llm_text = generate_ollama_reasoning(
            candidate,
            breakdown,
            audit,
            rank,
            model=model,
            host=host,
            timeout=timeout,
            rule_based=baseline,
        )
        if llm_text:
            ranked.reasoning = llm_text
            ranked.reasoning_source = "ollama"
            enriched += 1
        else:
            ranked.reasoning_source = "rule_based"
            fallback += 1
    return enriched, fallback