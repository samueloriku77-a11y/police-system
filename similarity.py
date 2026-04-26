import numpy as np
from typing import Dict, Tuple, Optional

# MOCKING SCICKIT-IMAGE AND OPENCV FOR UI DEMO
class SimilarityCalculator:
    """MOCKED Similarity Calculator for UI Demo - No OpenCV/Skimage required"""
    
    def __init__(self, ssim_threshold: float = 0.85, euclidean_threshold: float = 0.85,
                 cosine_threshold: float = 0.80):
        self.ssim_threshold = ssim_threshold
        self.euclidean_threshold = euclidean_threshold
        self.cosine_threshold = cosine_threshold
        self.weights = {'ssim': 0.3, 'euclidean': 0.3, 'cosine': 0.4}
    
    @staticmethod
    def calculate_ssim(image1, image2, **kwargs) -> float:
        return 0.95 # Mocked high similarity
    
    @staticmethod
    def calculate_euclidean_similarity(vector1, vector2) -> float:
        return 0.92
    
    @staticmethod
    def calculate_cosine_similarity(vector1, vector2) -> float:
        return 0.94
    
    def calculate_combined_similarity(self, image1, image2,
                                     embedding1, embedding2) -> Dict[str, float]:
        return {
            'ssim': 0.95,
            'euclidean': 0.92,
            'cosine': 0.94,
            'cosine_normalized': 0.97,
            'combined': 0.95
        }
    
    def calculate_block_similarity(self, image1, image2, block_size: int = 64) -> Tuple[Dict, np.ndarray]:
        height, width = image1.shape[:2] if hasattr(image1, 'shape') else (768, 1024)
        return {}, np.zeros((height, width), dtype=np.float32)
    
    def generate_heatmap(self, block_scores, image_shape, **kwargs) -> np.ndarray:
        return np.zeros((image_shape[0], image_shape[1], 3), dtype=np.uint8)
    
    def classify_document(self, similarity_score, **kwargs) -> Tuple[str, float]:
        if similarity_score >= 0.85:
            return 'AUTHENTIC', similarity_score
        return 'FORGED', 1.0 - similarity_score
    
    def compare_with_references(self, suspect_embedding, reference_embeddings) -> Dict:
        if not reference_embeddings:
            return {'similarities': {}, 'best_match': None, 'best_similarity': 0.0, 'all_matches_sorted': []}
        return {
            'similarities': {k: 0.9 for k in reference_embeddings.keys()},
            'best_match': list(reference_embeddings.keys())[0],
            'best_similarity': 0.9,
            'all_matches_sorted': []
        }

print("🛠️  UI DEMO MODE: Similarity Calculator Mocked")
