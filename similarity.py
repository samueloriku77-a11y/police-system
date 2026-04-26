"""
Similarity Computation Module
Computes similarity between document embeddings using multiple metrics
"""

import numpy as np
import cv2
from sklearn.metrics.pairwise import euclidean_distances, cosine_similarity
from skimage.metrics import structural_similarity as ssim_metric
from typing import Dict, Tuple, Optional
from preprocessing import ImagePreprocessor


class SimilarityCalculator:
    """Computes similarity scores between document images and embeddings"""
    
    def __init__(self, ssim_threshold: float = 0.85, euclidean_threshold: float = 0.85,
                 cosine_threshold: float = 0.80):
        """
        Initialize similarity calculator with thresholds
        
        Args:
            ssim_threshold: Threshold for SSIM scores
            euclidean_threshold: Threshold for Euclidean similarity
            cosine_threshold: Threshold for Cosine similarity
        """
        self.ssim_threshold = ssim_threshold
        self.euclidean_threshold = euclidean_threshold
        self.cosine_threshold = cosine_threshold
        self.preprocessor = ImagePreprocessor()
        
        # Weights for combined score
        self.weights = {
            'ssim': 0.3,
            'euclidean': 0.3,
            'cosine': 0.4
        }
    
    @staticmethod
    def calculate_ssim(image1: np.ndarray, image2: np.ndarray, 
                      data_range: Optional[float] = None) -> float:
        """
        Calculate Structural Similarity Index (SSIM)
        
        Args:
            image1: First image
            image2: Second image
            data_range: Data range of images (default: max - min)
            
        Returns:
            SSIM score between -1 and 1 (typically 0 to 1)
        """
        # Ensure images are the same size
        if image1.shape != image2.shape:
            image2 = cv2.resize(image2, (image1.shape[1], image1.shape[0]))
        
        # Ensure images are grayscale
        if len(image1.shape) == 3:
            image1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
        if len(image2.shape) == 3:
            image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        
        # Calculate SSIM
        if data_range is None:
            data_range = max(image1.max(), image2.max()) - min(image1.min(), image2.min())
        
        score = ssim_metric(image1, image2, data_range=data_range)
        return float(score)
    
    @staticmethod
    def calculate_euclidean_similarity(vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate normalized Euclidean distance similarity
        
        Args:
            vector1: First feature vector
            vector2: Second feature vector
            
        Returns:
            Similarity score between 0 and 1 (1 = identical)
        """
        # Compute Euclidean distance
        distance = euclidean_distances([vector1], [vector2])[0][0]
        
        # Normalize to 0-1 range: smaller distance = higher similarity
        # Using 1/(1+d) normalization
        similarity = 1.0 / (1.0 + distance)
        
        return float(similarity)
    
    @staticmethod
    def calculate_cosine_similarity(vector1: np.ndarray, vector2: np.ndarray) -> float:
        """
        Calculate Cosine similarity between two vectors
        
        Args:
            vector1: First feature vector
            vector2: Second feature vector
            
        Returns:
            Similarity score between -1 and 1 (typically -0.5 to 1 for normalized vectors)
        """
        # Handle edge case of zero vectors
        if np.all(vector1 == 0) or np.all(vector2 == 0):
            return 0.0
        
        # Compute cosine similarity
        similarity = cosine_similarity([vector1], [vector2])[0][0]
        
        return float(similarity)
    
    def calculate_combined_similarity(self, image1: np.ndarray, image2: np.ndarray,
                                     embedding1: np.ndarray, embedding2: np.ndarray) -> Dict[str, float]:
        """
        Calculate combined similarity score using multiple metrics
        
        Args:
            image1: First image
            image2: Second image
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Dictionary with individual and combined scores
        """
        # Calculate individual metrics
        ssim_score = self.calculate_ssim(image1, image2)
        euclidean_score = self.calculate_euclidean_similarity(embedding1, embedding2)
        cosine_score = self.calculate_cosine_similarity(embedding1, embedding2)
        
        # Normalize cosine to 0-1 range for consistent weighting
        cosine_normalized = (cosine_score + 1.0) / 2.0
        
        # Calculate weighted combined score
        combined_score = (
            self.weights['ssim'] * ssim_score +
            self.weights['euclidean'] * euclidean_score +
            self.weights['cosine'] * cosine_normalized
        )
        
        return {
            'ssim': float(ssim_score),
            'euclidean': float(euclidean_score),
            'cosine': float(cosine_score),
            'cosine_normalized': float(cosine_normalized),
            'combined': float(combined_score)
        }
    
    def calculate_block_similarity(self, image1: np.ndarray, image2: np.ndarray,
                                  block_size: int = 64) -> Tuple[Dict, np.ndarray]:
        """
        Calculate similarity for each block in the image
        
        Args:
            image1: First image (reference)
            image2: Second image (suspect)
            block_size: Size of each block
            
        Returns:
            Tuple of (block_scores dict, heatmap array covering full image)
        """
        # Ensure same size
        if image1.shape != image2.shape:
            image2 = cv2.resize(image2, (image1.shape[1], image1.shape[0]))
        
        # Convert to grayscale
        if len(image1.shape) == 3:
            image1 = cv2.cvtColor(image1, cv2.COLOR_BGR2GRAY)
        if len(image2.shape) == 3:
            image2 = cv2.cvtColor(image2, cv2.COLOR_BGR2GRAY)
        
        height, width = image1.shape
        block_scores = {}
        heatmap = np.zeros((height, width), dtype=np.float32)
        
        # Calculate similarity for each block
        for y in range(0, height - block_size, block_size):
            for x in range(0, width - block_size, block_size):
                block1 = image1[y:y+block_size, x:x+block_size]
                block2 = image2[y:y+block_size, x:x+block_size]
                
                # Calculate block SSIM
                block_similarity = self.calculate_ssim(block1, block2)
                
                # Store score (normalize to 0-1)
                similarity_normalized = (block_similarity + 1.0) / 2.0
                block_scores[(x, y)] = similarity_normalized
                
                # Fill heatmap
                heatmap[y:y+block_size, x:x+block_size] = similarity_normalized
        
        # Fill remaining edges with average of nearby blocks
        if width % block_size != 0 or height % block_size != 0:
            # Fill right edge
            if width % block_size != 0:
                last_x = (width // block_size) * block_size
                if last_x > 0:
                    heatmap[:, last_x:] = np.mean(heatmap[:, last_x:last_x+1])
            # Fill bottom edge
            if height % block_size != 0:
                last_y = (height // block_size) * block_size
                if last_y > 0:
                    heatmap[last_y:, :] = np.mean(heatmap[last_y:last_y+1, :])
        
        return block_scores, heatmap
    
    def generate_heatmap(self, block_scores: Dict, image_shape: Tuple[int, int],
                        block_size: int = 64, colormap: str = 'hot') -> np.ndarray:
        """
        Generate heatmap visualization from block scores
        
        Args:
            block_scores: Dictionary of block coordinates to similarity scores
            image_shape: Shape of original image
            block_size: Size of each block
            colormap: OpenCV colormap name
            
        Returns:
            Colored heatmap image
        """
        height, width = image_shape[:2]
        heatmap = np.zeros((height, width), dtype=np.float32)
        
        # Fill heatmap with scores
        for (x, y), score in block_scores.items():
            heatmap[y:y+block_size, x:x+block_size] = score
        
        # Convert to 8-bit for colormapping
        heatmap_8bit = (heatmap * 255).astype(np.uint8)
        
        # Apply colormap
        colormap_id = getattr(cv2, f'COLORMAP_{colormap.upper()}', cv2.COLORMAP_HOT)
        colored_heatmap = cv2.applyColorMap(heatmap_8bit, colormap_id)
        
        return colored_heatmap
    
    def classify_document(self, similarity_score: float, uncertain_range: Tuple[float, float] = (0.70, 0.85)) -> Tuple[str, float]:
        """
        Classify document as AUTHENTIC, FORGED, or UNCERTAIN
        
        Args:
            similarity_score: Combined similarity score (0-1)
            uncertain_range: Range for uncertain classification
            
        Returns:
            Tuple of (classification, confidence)
        """
        if similarity_score >= self.ssim_threshold:
            classification = 'AUTHENTIC'
            confidence = similarity_score
        elif similarity_score >= uncertain_range[0]:
            classification = 'UNCERTAIN'
            # Confidence decreases in uncertain range
            mid_point = (self.ssim_threshold + uncertain_range[0]) / 2
            confidence = 1.0 - abs(similarity_score - mid_point) / mid_point
        else:
            classification = 'FORGED'
            confidence = 1.0 - similarity_score
        
        return classification, float(confidence)
    
    def compare_with_references(self, suspect_embedding: np.ndarray, 
                               reference_embeddings: Dict[str, np.ndarray]) -> Dict:
        """
        Compare suspect embedding against multiple reference embeddings
        
        Args:
            suspect_embedding: Feature vector of suspect document
            reference_embeddings: Dictionary of reference documents with embeddings
            
        Returns:
            Dictionary with comparison results
        """
        similarities = {}
        
        for ref_name, ref_embedding in reference_embeddings.items():
            sim = self.calculate_cosine_similarity(suspect_embedding, ref_embedding)
            similarities[ref_name] = sim
        
        # Find best match
        if similarities:
            best_match = max(similarities, key=similarities.get)
            best_similarity = similarities[best_match]
            
            return {
                'similarities': similarities,
                'best_match': best_match,
                'best_similarity': best_similarity,
                'all_matches_sorted': sorted(similarities.items(), key=lambda x: x[1], reverse=True)
            }
        
        return {
            'similarities': {},
            'best_match': None,
            'best_similarity': 0.0,
            'all_matches_sorted': []
        }
