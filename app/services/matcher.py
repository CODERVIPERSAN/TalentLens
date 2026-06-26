from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models.candidate import Candidate
from app.db.models.job import Job
from app.db.models.match import Match
from app.services.embedding import generate_embedding, calculate_similarity
from app.services.analysis import analyze_candidate_job_match


async def find_best_matches(
    job_id: int,
    db: AsyncSession,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Find the best matching candidates for a given job.
    """
    # Get the job
    job_result = await db.execute(select(Job).where(Job.id == job_id))
    job = job_result.scalar_one_or_none()
    
    if not job:
        return []
    
    # Get all candidates
    candidates_result = await db.execute(select(Candidate))
    candidates = candidates_result.scalars().all()
    
    matches = []
    
    for candidate in candidates:
        # Skip if candidate has no embedding
        if not candidate.embedding or not job.embedding:
            continue
        
        # Analyze match
        match_analysis = analyze_candidate_job_match(
            candidate_skills=candidate.skills or [],
            candidate_experience=candidate.experience_years or 0,
            job_requirements=job.requirements or [],
            job_min_experience=job.min_experience_years or 0,
            candidate_embedding=candidate.embedding,
            job_embedding=job.embedding
        )
        
        matches.append({
            "candidate_id": candidate.id,
            "candidate_name": candidate.name,
            "candidate_email": candidate.email,
            "match_score": match_analysis["score"],
            "analysis": match_analysis
        })
    
    # Sort by match score
    matches.sort(key=lambda x: x["match_score"], reverse=True)
    
    return matches[:limit]


async def generate_candidate_embedding(candidate: Candidate) -> List[float]:
    """
    Generate embedding for a candidate based on their profile.
    """
    text_parts = []
    
    if candidate.resume_text:
        text_parts.append(candidate.resume_text)
    
    if candidate.skills:
        text_parts.append(" ".join(candidate.skills))
    
    if candidate.name:
        text_parts.append(candidate.name)
    
    combined_text = " ".join(text_parts)
    return generate_embedding(combined_text)


async def generate_job_embedding(job: Job) -> List[float]:
    """
    Generate embedding for a job based on its description.
    """
    text_parts = []
    
    if job.description:
        text_parts.append(job.description)
    
    if job.requirements:
        text_parts.append(" ".join(job.requirements))
    
    if job.skills:
        text_parts.append(" ".join(job.skills))
    
    if job.title:
        text_parts.append(job.title)
    
    combined_text = " ".join(text_parts)
    return generate_embedding(combined_text)
