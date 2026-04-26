import numpy as np
from PIL import Image
import os
from typing import Tuple, Optional

# MOCKING OPENCV FOR UI DEMO
class ImagePreprocessor:
    """MOCKED Image Preprocessor for UI Demo - No OpenCV required"""
    
    STANDARD_WIDTH = 1024
    STANDARD_HEIGHT = 768
    
    def __init__(self):
        self.standard_size = (self.STANDARD_WIDTH, self.STANDARD_HEIGHT)
    
    @staticmethod
    def load_image(image_path: str) -> Optional[np.ndarray]:
        # Using PIL as fallback for loading image
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        try:
            img = Image.open(image_path)
            return np.array(img)
        except Exception as e:
            raise Exception(f"Error loading image: {str(e)}")
    
    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        if len(image.shape) == 2:
            return image
        # Simple weighted average for grayscale
        return np.dot(image[...,:3], [0.2989, 0.5870, 0.1140]).astype(np.uint8)
    
    def resize_image(self, image: np.ndarray) -> np.ndarray:
        return image # Skip resize in demo
    
    @staticmethod
    def denoise_image(image: np.ndarray, h: int = 10, **kwargs) -> np.ndarray:
        return image
    
    @staticmethod
    def apply_bilateral_filter(image: np.ndarray, **kwargs) -> np.ndarray:
        return image
    
    @staticmethod
    def normalize_pixels(image: np.ndarray) -> np.ndarray:
        return image.astype('float32') / 255.0
    
    @staticmethod
    def enhance_contrast(image: np.ndarray, **kwargs) -> np.ndarray:
        return image
    
    @staticmethod
    def extract_edges(image: np.ndarray, method: str = 'canny') -> np.ndarray:
        return np.zeros_like(image)
    
    def preprocess_document(self, image_path: str, **kwargs) -> np.ndarray:
        image = self.load_image(image_path)
        image = self.to_grayscale(image)
        return self.normalize_pixels(image)
    
    @staticmethod
    def save_preprocessed_image(image: np.ndarray, output_path: str) -> None:
        if image.dtype == np.float32 or image.dtype == np.float64:
            image = (image * 255).astype(np.uint8)
        img = Image.fromarray(image)
        img.save(output_path)

print("🛠️  UI DEMO MODE: Image Preprocessor Mocked")
