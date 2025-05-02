from dataclasses import dataclass
from typing import List
import numpy as np

@dataclass(frozen=True)
class Embedding:
    vector: List[float]
    dimension: int

    @classmethod
    def create(cls, vector: List[float]) -> 'Embedding':
        return cls(vector=vector, dimension=len(vector))

    def cosine_similarity(self, other: 'Embedding') -> float:
        if self.dimension != other.dimension:
            raise ValueError("Embeddings must have the same dimension")
        
        dot_product = np.dot(self.vector, other.vector)
        norm_a = np.linalg.norm(self.vector)
        norm_b = np.linalg.norm(other.vector)
        return dot_product / (norm_a * norm_b)