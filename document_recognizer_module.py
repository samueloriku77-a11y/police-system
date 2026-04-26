"""
Document Recognizer Module
Integrates document_recognizer.keras model (81% accuracy) for document extraction and recognition
"""

import tensorflow as tf
import numpy as np
import cv2
import os
from typing import Tuple, Optional, Dict, List
import json

class DocumentRecognizer:
    """
    Document Recognizer using Keras model
    - Accuracy: 81%
    - Purpose: Extract document regions and recognize document types
    - Supports: ID documents, Certificates, General documents
    """
    
    MODEL_ACCURACY = 0.81
    MODEL_PATH = 'models/document_recognizer.keras'
    INPUT_SIZE = (384, 384)  # Model expects 384x384, not 224x224
    
    # Document type classifications
    DOCUMENT_TYPES = {
        0: 'id_document',
        1: 'certificate',
        2: 'passport',
        3: 'license',
        4: 'general_document'
    }
    
    def __init__(self, model_path: str = None):
        """
        Initialize Document Recognizer
        
        Args:
            model_path: Path to document_recognizer.keras model
        """
        self.model_path = model_path or self.MODEL_PATH
        self.accuracy = self.MODEL_ACCURACY  # Set accuracy BEFORE loading model
        self.model = self._load_model()
        
    def _load_model(self):
        """Load the document recognizer model with 81% accuracy"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Document recognizer model not found: {self.model_path}")
        
        try:
            print(f"📄 Loading Document Recognizer Model (81% accuracy): {self.model_path}")
            model = tf.keras.models.load_model(self.model_path, compile=False)
            print(f"✅ Document Recognizer Model loaded successfully!")
            print(f"   Model Accuracy: {self.accuracy*100:.1f}%")
            return model
        except Exception as e:
            print(f"❌ Error loading Document Recognizer model: {e}")
            raise
    
    def extract_document_region(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """
        Extract document region from image
        
        Args:
            image_path: Path to input image
            
        Returns:
            Tuple of (extracted_document, metadata_dict)
            - extracted_document: Cropped document region
            - metadata: Contains boundaries, confidence, document type
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None, {'error': 'Could not read image', 'confidence': 0.0}
            
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            
            # Prepare for model
            img_prepared = self._prepare_image(img_rgb)
            
            # Get document region prediction
            predictions = self.model.predict(img_prepared, verbose=0)
            
            # predictions format: [class_score, bbox_coords...]
            # Assuming: [document_class_confidence, x1, y1, x2, y2, document_type]
            doc_confidence = float(predictions[0][0])
            
            # Extract document type
            doc_type_idx = np.argmax(predictions[0][1:6]) if len(predictions[0]) > 5 else 0
            doc_type = self.DOCUMENT_TYPES.get(doc_type_idx, 'general_document')
            
            # Extract bounding box if available
            if len(predictions[0]) >= 5:
                h, w = img_rgb.shape[:2]
                # Denormalize bounding box coordinates
                x1 = max(0, int(predictions[0][1] * w))
                y1 = max(0, int(predictions[0][2] * h))
                x2 = min(w, int(predictions[0][3] * w))
                y2 = min(h, int(predictions[0][4] * h))
            else:
                # Full image if no bbox
                h, w = img_rgb.shape[:2]
                x1, y1, x2, y2 = 0, 0, w, h
            
            # Extract document region
            extracted = img_rgb[y1:y2, x1:x2]
            
            metadata = {
                'confidence': doc_confidence,
                'accuracy': self.accuracy,
                'document_type': doc_type,
                'bbox': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2, 'width': x2-x1, 'height': y2-y1},
                'original_size': {'height': h, 'width': w},
                'extracted_size': {'height': extracted.shape[0], 'width': extracted.shape[1]},
                'is_valid_document': doc_confidence > 0.5
            }
            
            return extracted, metadata
            
        except Exception as e:
            print(f"❌ Error extracting document region: {e}")
            return None, {'error': str(e), 'confidence': 0.0}
    
    def recognize_document_type(self, image_path: str) -> Dict:
        """
        Recognize document type with confidence score
        
        Args:
            image_path: Path to input image
            
        Returns:
            Dictionary with document type and confidence
        """
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'error': 'Could not read image', 'confidence': 0.0}
            
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img_prepared = self._prepare_image(img_rgb)
            
            predictions = self.model.predict(img_prepared, verbose=0)
            
            # Get probabilities for each document type
            type_scores = predictions[0][1:6] if len(predictions[0]) > 5 else np.zeros(5)
            doc_type_idx = np.argmax(type_scores)
            doc_type = self.DOCUMENT_TYPES.get(doc_type_idx, 'general_document')
            confidence = float(type_scores[doc_type_idx]) if len(type_scores) > doc_type_idx else 0.0
            
            return {
                'document_type': doc_type,
                'confidence': confidence,
                'accuracy': self.accuracy,
                'all_types': {
                    self.DOCUMENT_TYPES.get(i, f'type_{i}'): float(type_scores[i]) 
                    for i in range(len(type_scores))
                }
            }
            
        except Exception as e:
            print(f"❌ Error recognizing document type: {e}")
            return {'error': str(e), 'confidence': 0.0}
    
    def extract_document_features(self, image_path: str) -> Dict:
        """
        Extract comprehensive document features using the 81% accuracy model
        
        Args:
            image_path: Path to input image
            
        Returns:
            Dictionary with document features and metrics
        """
        try:
            # Extract document region
            extracted_doc, region_metadata = self.extract_document_region(image_path)
            
            if extracted_doc is None:
                return {'error': region_metadata.get('error', 'Unknown error'), 'confidence': 0.0}
            
            # Get document type
            type_info = self.recognize_document_type(image_path)
            
            # Combine results
            features = {
                'model_accuracy': self.accuracy,
                'document_type': type_info.get('document_type', 'unknown'),
                'type_confidence': type_info.get('confidence', 0.0),
                'document_region': region_metadata,
                'quality_metrics': self._assess_document_quality(extracted_doc),
                'recognition_confidence': region_metadata.get('confidence', 0.0),
                'is_valid': region_metadata.get('is_valid_document', False),
                'timestamp': None  # Can be set externally
            }
            
            return features
            
        except Exception as e:
            print(f"❌ Error extracting document features: {e}")
            return {'error': str(e), 'confidence': 0.0}
    
    def _prepare_image(self, img: np.ndarray) -> np.ndarray:
        """
        Prepare image for model inference
        
        Args:
            img: Input image (RGB format)
            
        Returns:
            Prepared image tensor
        """
        # Resize to model input size
        resized = cv2.resize(img, self.INPUT_SIZE)
        
        # Normalize to 0-1 range
        normalized = resized.astype(np.float32) / 255.0
        
        # Add batch dimension
        batched = np.expand_dims(normalized, 0)
        
        return batched
    
    def _assess_document_quality(self, img: np.ndarray) -> Dict:
        """
        Assess document image quality
        
        Args:
            img: Document image (RGB)
            
        Returns:
            Quality metrics dictionary
        """
        try:
            gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
            
            # Sharpness (Laplacian variance)
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            sharpness = float(laplacian.var())
            
            # Contrast (standard deviation of pixel values)
            contrast = float(np.std(gray))
            
            # Brightness (mean pixel value)
            brightness = float(np.mean(gray))
            
            # Blur detection (if variance is very low)
            is_blurry = sharpness < 100  # Threshold for blur detection
            
            # Underexposed/overexposed
            is_underexposed = brightness < 80
            is_overexposed = brightness > 180
            
            quality_score = self._calculate_quality_score(sharpness, contrast, brightness)
            
            return {
                'sharpness': sharpness,
                'contrast': contrast,
                'brightness': brightness,
                'quality_score': quality_score,
                'is_blurry': is_blurry,
                'is_underexposed': is_underexposed,
                'is_overexposed': is_overexposed,
                'is_good_quality': quality_score > 0.7
            }
        except Exception as e:
            print(f"Warning: Could not assess document quality: {e}")
            return {'error': str(e)}
    
    def _calculate_quality_score(self, sharpness: float, contrast: float, brightness: float) -> float:
        """
        Calculate overall document quality score (0-1)
        
        Args:
            sharpness: Laplacian variance
            contrast: Standard deviation
            brightness: Mean pixel value
            
        Returns:
            Quality score between 0 and 1
        """
        # Normalize metrics
        sharp_score = min(sharpness / 500.0, 1.0)  # Max at 500
        contrast_score = min(contrast / 100.0, 1.0)  # Max at 100
        brightness_score = 1.0 - abs(brightness - 128) / 128.0  # Optimal at 128
        
        # Weighted average
        quality = (sharp_score * 0.4 + contrast_score * 0.4 + brightness_score * 0.2)
        
        return float(np.clip(quality, 0.0, 1.0))
    
    def enhance_extracted_document(self, image_path: str) -> Tuple[Optional[np.ndarray], Dict]:
        """
        Extract document and apply enhancement for better analysis
        
        Args:
            image_path: Path to input image
            
        Returns:
            Tuple of (enhanced_document, metadata)
        """
        extracted, metadata = self.extract_document_region(image_path)
        
        if extracted is None:
            return None, metadata
        
        try:
            # Apply enhancement
            enhanced = self._enhance_document_image(extracted)
            
            metadata['enhancement_applied'] = True
            return enhanced, metadata
            
        except Exception as e:
            print(f"Warning: Could not enhance document: {e}")
            metadata['enhancement_applied'] = False
            return extracted, metadata
    
    def _enhance_document_image(self, img: np.ndarray) -> np.ndarray:
        """
        Apply enhancement to extracted document
        
        Args:
            img: Document image
            
        Returns:
            Enhanced document image
        """
        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        enhanced = clahe.apply(gray)
        
        # Convert back to RGB for consistency
        enhanced_rgb = cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)
        
        return enhanced_rgb
    
    def get_model_info(self) -> Dict:
        """Get information about the model"""
        return {
            'name': 'Document Recognizer',
            'model_path': self.model_path,
            'accuracy': f"{self.accuracy*100:.1f}%",
            'input_size': self.INPUT_SIZE,
            'supported_types': self.DOCUMENT_TYPES,
            'model_status': 'loaded' if self.model else 'not_loaded'
        }


# Initialize global document recognizer
try:
    document_recognizer = DocumentRecognizer()
except Exception as e:
    print(f"⚠️  Document Recognizer not available: {e}")
    document_recognizer = None
