"""
Image Preprocessing Module
Handles image preprocessing operations for document authentication system
"""

import cv2
import numpy as np
from PIL import Image
import os
from typing import Tuple, Optional


class ImagePreprocessor:
    """Preprocesses images for feature extraction and forgery detection"""
    
    STANDARD_WIDTH = 1024
    STANDARD_HEIGHT = 768
    
    def __init__(self):
        """Initialize the preprocessor with standard parameters"""
        self.standard_size = (self.STANDARD_WIDTH, self.STANDARD_HEIGHT)
    
    @staticmethod
    def load_image(image_path: str) -> Optional[np.ndarray]:
        """
        Load image from file path
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Loaded image as numpy array or None if loading fails
        """
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"Image file not found: {image_path}")
        
        try:
            image = cv2.imread(image_path)
            if image is None:
                raise ValueError(f"Could not read image: {image_path}")
            return image
        except Exception as e:
            raise Exception(f"Error loading image: {str(e)}")
    
    @staticmethod
    def to_grayscale(image: np.ndarray) -> np.ndarray:
        """
        Convert image to grayscale
        
        Args:
            image: Input image (BGR format)
            
        Returns:
            Grayscale image
        """
        if len(image.shape) == 2:
            return image  # Already grayscale
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    
    def resize_image(self, image: np.ndarray) -> np.ndarray:
        """
        Resize image to standard dimensions (1024x768)
        
        Args:
            image: Input image
            
        Returns:
            Resized image
        """
        if len(image.shape) == 3:
            image = self.to_grayscale(image)
        
        resized = cv2.resize(image, self.standard_size, interpolation=cv2.INTER_CUBIC)
        return resized
    
    @staticmethod
    def denoise_image(image: np.ndarray, h: int = 10, template_window: int = 7, 
                     search_window: int = 21) -> np.ndarray:
        """
        Apply denoising using Non-Local Means Denoising
        
        Args:
            image: Input image (grayscale)
            h: Filter strength. Higher h value removes more noise but also removes details
            template_window: Size of template patch (should be odd)
            search_window: Size of search area (should be odd)
            
        Returns:
            Denoised image
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        denoised = cv2.fastNlMeansDenoising(image, None, h=h, 
                                            templateWindowSize=template_window,
                                            searchWindowSize=search_window)
        return denoised
    
    @staticmethod
    def apply_bilateral_filter(image: np.ndarray, d: int = 9, sigma_color: float = 75,
                              sigma_space: float = 75) -> np.ndarray:
        """
        Apply bilateral filter for edge-preserving smoothing
        
        Args:
            image: Input image
            d: Diameter of pixel neighborhood
            sigma_color: Filter sigma in the color space
            sigma_space: Filter sigma in the coordinate space
            
        Returns:
            Filtered image
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        filtered = cv2.bilateralFilter(image, d, sigma_color, sigma_space)
        return filtered
    
    @staticmethod
    def normalize_pixels(image: np.ndarray) -> np.ndarray:
        """
        Normalize pixel values to 0-1 range
        
        Args:
            image: Input image
            
        Returns:
            Normalized image (float32)
        """
        normalized = image.astype('float32') / 255.0
        return normalized
    
    @staticmethod
    def enhance_contrast(image: np.ndarray, clip_limit: float = 2.0, 
                        tile_size: Tuple[int, int] = (8, 8)) -> np.ndarray:
        """
        Enhance image contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
        
        Args:
            image: Input image (grayscale)
            clip_limit: Contrast limit threshold
            tile_size: Size of grid for histogram equalization
            
        Returns:
            Contrast-enhanced image
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
        enhanced = clahe.apply(image)
        return enhanced
    
    @staticmethod
    def extract_edges(image: np.ndarray, method: str = 'canny') -> np.ndarray:
        """
        Extract edges from image
        
        Args:
            image: Input image (grayscale)
            method: Edge detection method ('canny' or 'sobel')
            
        Returns:
            Edge map
        """
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if method == 'canny':
            image_uint8 = image.astype(np.uint8)
            edges = cv2.Canny(image_uint8, 50, 150)
        elif method == 'sobel':
            sobelx = cv2.Sobel(image, cv2.CV_64F, 1, 0, ksize=5)
            sobely = cv2.Sobel(image, cv2.CV_64F, 0, 1, ksize=5)
            edges = np.sqrt(sobelx**2 + sobely**2).astype(np.uint8)
        else:
            raise ValueError(f"Unknown edge detection method: {method}")
        
        return edges
    
    def preprocess_document(self, image_path: str, denoise: bool = True,
                           enhance_contrast: bool = True, 
                           normalize: bool = True) -> np.ndarray:
        """
        Complete preprocessing pipeline for document images
        
        Args:
            image_path: Path to input image
            denoise: Whether to apply denoising
            enhance_contrast: Whether to enhance contrast
            normalize: Whether to normalize pixel values
            
        Returns:
            Preprocessed image
        """
        # Load image
        image = self.load_image(image_path)
        
        # Convert to grayscale
        image = self.to_grayscale(image)
        
        # Resize to standard dimensions
        image = self.resize_image(image)
        
        # Denoise if requested
        if denoise:
            image = self.denoise_image(image)
        
        # Enhance contrast if requested
        if enhance_contrast:
            image = self.enhance_contrast(image)
        
        # Normalize pixel values if requested
        if normalize:
            image = self.normalize_pixels(image)
        
        return image
    
    @staticmethod
    def save_preprocessed_image(image: np.ndarray, output_path: str) -> None:
        """
        Save preprocessed image to file
        
        Args:
            image: Preprocessed image
            output_path: Path to save the image
        """
        # Convert normalized image back to 0-255 range if needed
        if image.dtype == np.float32 or image.dtype == np.float64:
            image = (image * 255).astype(np.uint8)
        
        cv2.imwrite(output_path, image)
