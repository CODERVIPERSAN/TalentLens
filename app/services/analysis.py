from functools import lru_cache
from typing import Any, Dict, List

from app.core.config import settings
from app.services.embedding import calculate_similarity


@lru_cache(maxsize=1)
def _get_client():
    """Lazily build the OpenAI client so the app can start without a key."""
    if not settings.openai_enabled:
        return None
    from openai import OpenAI

    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _normalize(skill: str) -> str:
    return skill.strip().lower()


def extract_skills_from_resume(resume_text: str) -> List[str]:
    """
    Extract skills from resume text.

    Uses OpenAI when configured; otherwise returns an empty list so callers can
    fall back to manually provided skills.
    """
    client = _get_client()
    if client is None:
        return []

    prompt = f"""
    Extract technical and soft skills from the following resume text.
    Return only a comma-separated list of skills.

    Resume:
    {resume_text}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are a skilled HR assistant."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.3,
            max_tokens=500,
        )

        skills_text = (response.choices[0].message.content or "").strip()
        return [skill.strip() for skill in skills_text.split(",") if skill.strip()]
    except Exception as e:  # noqa: BLE001 - degrade gracefully on API errors
        print(f"Error extracting skills: {e}")
        return []


def analyze_candidate_job_match(
    candidate_skills: List[str],
    candidate_experience: float,
    job_requirements: List[str],
    job_min_experience: float,
    candidate_embedding: List[float],
    job_embedding: List[float],
) -> Dict[str, Any]:
    """Analyze how well a candidate matches a job using embeddings and skills."""
    candidate_set = {_normalize(s) for s in candidate_skills}
    requirement_set = {_normalize(s) for s in job_requirements}

    matched = candidate_set & requirement_set
    missing = requirement_set - candidate_set

    skill_match = len(matched) / len(requirement_set) if requirement_set else 0.0
    experience_match = (
        min(candidate_experience / job_min_experience, 1.0)
        if job_min_experience > 0
        else 1.0
    )
    semantic_similarity = calculate_similarity(candidate_embedding, job_embedding)

    overall_score = (skill_match * 0.4) + (experience_match * 0.3) + (
        semantic_similarity * 0.3
    )

    analysis = generate_match_analysis(
        candidate_skills,
        job_requirements,
        candidate_experience,
        job_min_experience,
        overall_score,
    )

    return {
        "score": round(overall_score * 100, 2),
        "skill_match_score": round(skill_match * 100, 2),
        "experience_match_score": round(experience_match * 100, 2),
        "semantic_similarity_score": round(semantic_similarity * 100, 2),
        "analysis": analysis,
        "matched_skills": sorted(matched),
        "missing_skills": sorted(missing),
    }


def _heuristic_analysis(
    candidate_skills: List[str],
    job_requirements: List[str],
    candidate_experience: float,
    job_min_experience: float,
    score: float,
) -> str:
    matched = {_normalize(s) for s in candidate_skills} & {
        _normalize(s) for s in job_requirements
    }
    missing = {_normalize(s) for s in job_requirements} - {
        _normalize(s) for s in candidate_skills
    }

    parts = [f"Overall match score is {score * 100:.0f}%."]
    if matched:
        parts.append(f"Strengths: matches on {', '.join(sorted(matched))}.")
    if missing:
        parts.append(f"Gaps: missing {', '.join(sorted(missing))}.")
    if candidate_experience >= job_min_experience:
        parts.append(
            f"Experience requirement met ({candidate_experience:.0f} of "
            f"{job_min_experience:.0f} years)."
        )
    else:
        parts.append(
            f"Below required experience ({candidate_experience:.0f} of "
            f"{job_min_experience:.0f} years)."
        )
    return " ".join(parts)


def generate_match_analysis(
    candidate_skills: List[str],
    job_requirements: List[str],
    candidate_experience: float,
    job_min_experience: float,
    score: float,
) -> str:
    """Generate a natural language analysis of the match."""
    client = _get_client()
    if client is None:
        return _heuristic_analysis(
            candidate_skills,
            job_requirements,
            candidate_experience,
            job_min_experience,
            score,
        )

    prompt = f"""
    Analyze the following candidate-job match and provide a brief assessment.

    Candidate Skills: {', '.join(candidate_skills)}
    Job Requirements: {', '.join(job_requirements)}
    Candidate Experience: {candidate_experience} years
    Required Experience: {job_min_experience} years
    Match Score: {score * 100:.1f}%

    Provide a 2-3 sentence assessment of this match, highlighting strengths and any gaps.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an expert recruiter."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.5,
            max_tokens=300,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:  # noqa: BLE001 - degrade gracefully on API errors
        print(f"Error generating analysis: {e}")
        return _heuristic_analysis(
            candidate_skills,
            job_requirements,
            candidate_experience,
            job_min_experience,
            score,
        )
