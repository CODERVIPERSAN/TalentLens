from openai import OpenAI
from typing import List, Union
import numpy as np
from app.core.config import settings

client = OpenAI(api_key=settings.OPENAI_API_KEY)


def generate_embedding(text: Union[str, List[str]]) -> List[float]:
    """
    Generate embeddings for text using OpenAI's embedding API.
    """
    if isinstance(text, str):
        text = [text]
    
    embeddings = []
    for t in text:
        response = client.embeddings.create(
            model="text-embedding-3-small",
            input=t
        )
        embeddings.append(response.data[0].embedding)
    
    return embeddings[0] if len(embeddings) == 1 else embeddings


def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Calculate cosine similarity between two embeddings.
    """
    vec1 = np.array(embedding1)
    vec2 = np.array(embedding2)
    
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))
