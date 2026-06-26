from typing import Dict, Any, List
from app.services.embedding import generate_embedding, calculate_similarity
from openai import OpenAI
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def extract_skills_from_resume(resume_text: str) -> List[str]:
    """
    Extract skills from resume text using AI.
    """
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
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        skills_text = response.choices[0].message.content.strip()
        skills = [skill.strip() for skill in skills_text.split(",")]
        return skills
    except Exception as e:
        print(f"Error extracting skills: {e}")
        return []


def analyze_candidate_job_match(
    candidate_skills: List[str],
    candidate_experience: float,
    job_requirements: List[str],
    job_min_experience: float,
    candidate_embedding: List[float],
    job_embedding: List[float]
) -> Dict[str, Any]:
    """
    Analyze how well a candidate matches a job using AI and embeddings.
    """
    # Calculate skill overlap
    skill_match = len(set(candidate_skills) & set(job_requirements)) / len(job_requirements) if job_requirements else 0
    
    # Calculate experience match
    experience_match = min(candidate_experience / job_min_experience, 1.0) if job_min_experience > 0 else 1.0
    
    # Calculate semantic similarity using embeddings
    semantic_similarity = calculate_similarity(candidate_embedding, job_embedding)
    
    # Calculate overall score
    overall_score = (skill_match * 0.4) + (experience_match * 0.3) + (semantic_similarity * 0.3)
    
    # Generate AI analysis
    analysis = generate_match_analysis(
        candidate_skills,
        job_requirements,
        candidate_experience,
        job_min_experience,
        overall_score
    )
    
    return {
        "score": round(overall_score * 100, 2),
        "skill_match_score": round(skill_match * 100, 2),
        "experience_match_score": round(experience_match * 100, 2),
        "semantic_similarity_score": round(semantic_similarity * 100, 2),
        "analysis": analysis,
        "matched_skills": list(set(candidate_skills) & set(job_requirements)),
        "missing_skills": list(set(job_requirements) - set(candidate_skills))
    }


def generate_match_analysis(
    candidate_skills: List[str],
    job_requirements: List[str],
    candidate_experience: float,
    job_min_experience: float,
    score: float
) -> str:
    """
    Generate a natural language analysis of the match.
    """
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
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=300
        )
        
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating analysis: {e}")
        return "Analysis unavailable due to API error."
