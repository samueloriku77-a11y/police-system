import numpy as np
import logging

logger = logging.getLogger(__name__)

class AdvancedForgeryDetector:
    """MOCKED Multi-stage forgery detection for UI Demo - No OpenCV/TensorFlow required"""
    
    def __init__(self, embedding_model=None):
        print("🛠️  UI DEMO MODE: AdvancedForgeryDetector initialized without OpenCV")
        self.embedding_model = embedding_model
    
    def align_to_blueprint(self, target_img, blueprint_img):
        return target_img, np.eye(3)
    
    def extract_embedding(self, img, model=None):
        return np.random.rand(1280)
    
    def compare_to_blueprint(self, suspect_img, blueprint_img, embedding_model=None):
        dist = np.random.rand() * 0.5
        return dist, np.random.rand(1280), np.random.rand(1280)
    
    def get_diff_mask(self, aligned_suspect, blueprint, threshold=30):
        # Create a dummy mask
        thresh = np.zeros((100, 100), dtype=np.uint8)
        diff_visual = None
        change_regions = [{'x': 10, 'y': 10, 'width': 50, 'height': 50, 'area': 2500}]
        return thresh, diff_visual, change_regions
    
    def detect_text_regions(self, img, min_text_width=8, min_text_height=8):
        return [{'x': 20, 'y': 20, 'width': 40, 'height': 15, 'area': 600, 'solidity': 0.8, 'confidence': 0.9}]
    
    def analyze_text_forgeries(self, aligned_suspect, blueprint, text_regions, diff_mask):
        return [{'x': 20, 'y': 20, 'width': 40, 'height': 15, 'forgery_score': 85.0, 'has_changes': True, 'type': 'TEXT_FORGERY'}]
    
    def get_forged_words_visualization(self, img, forged_text_regions, color=(0, 0, 255)):
        return img
    
    def full_analysis(self, suspect_img, blueprint_img, embedding_model=None):
        return {
            'alignment_success': True,
            'embedding_distance': 0.15,
            'diff_mask': np.zeros((100, 100)),
            'diff_visual': None,
            'change_regions': [],
            'text_regions': [],
            'forged_text_regions': [],
            'text_visualization': None,
            'homography': np.eye(3),
            'forgery_confidence': 0.12
        }

def create_detector(embedding_model=None):
    return AdvancedForgeryDetector(embedding_model)

print("🛠️  UI DEMO MODE: Advanced Forgery Detector Mocked")
