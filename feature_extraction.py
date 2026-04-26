import pickle
import os
import numpy as np
import json
import base64
from typing import Optional, Tuple, List, Dict

# MOCKING DEEP LEARNING LIBRARIES FOR UI DEMO
class MockModel:
    def predict(self, x, verbose=0):
        return np.random.rand(1, 512)

class FeatureExtractor:
    """MOCKED Feature Extractor for UI Demo - No TensorFlow required"""
    TRAINING_EMBEDDING_DIM = 1280
    FEATURE_EMBEDDING_DIM = 512
    MODEL_INPUT_SIZE = (224, 224, 3)
    
    def __init__(self, model_path=None, metadata_path=None):
        print("🛠️  UI DEMO MODE: FeatureExtractor initialized without TensorFlow")
        self.model = MockModel()
        self.document_recognizer = None
    
    def extract_features(self, image_path, preprocess=True):
        return np.random.rand(512)
    
    def extract_enhanced_features(self, image_path: str) -> Tuple[np.ndarray, Dict]:
        return np.random.rand(512), {
            'document_recognizer_available': True,
            'model_accuracy': 0.81,
            'document_type': 'ID Card',
            'confidence': 0.94
        }
    
    def extract_features_from_array(self, img_array: np.ndarray) -> np.ndarray:
        return np.random.rand(512)

class ForgeryDetector:
    """MOCKED Forgery Detector for UI Demo - No TensorFlow required"""
    def __init__(self, model_path="models/aether_forgery_model.h5"):
        print("🛠️  UI DEMO MODE: ForgeryDetector initialized without TensorFlow")
    
    def detect_forged_regions(self, image_path):
        # Return a random result for demo purposes
        is_forged = np.random.rand() > 0.5
        return {
            'forged_ratio': 0.85 if is_forged else 0.1,
            'regions': [[50, 50, 150, 150]] if is_forged else [],
            'heatmap_b64': '',
            'annotated_b64': '',
            'metrics': {
                'ela_norm': 0.12,
                'edge_density': 0.15,
                'lap_var': 0.8,
                'noise_level': 0.05
            },
            'verdict': 'FORGED' if is_forged else 'AUTHENTIC',
            'pattern_check': is_forged,
            'calibrated_prob': 0.88 if is_forged else 0.12
        }
    
    def predict_whole_document(self, image_path):
        results = self.detect_forged_regions(image_path)
        return {
            'is_forged': results['verdict'] == 'FORGED',
            'confidence': results['forged_ratio'],
            'forged_prob': results['calibrated_prob'],
            'metrics': results['metrics'],
            'regions': results['regions']
        }

print("🛠️  UI DEMO MODE: Police System Machine Learning Mocked")
