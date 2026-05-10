import os
import cv2
import numpy as np
from PIL import Image, ImageChops
from feature_extraction import ForgeryDetector, FeatureExtractor
from db import db, ReferenceDocument, DocumentEditLog

class DirectoryWatcher:
    """Syncs the physical 'master_references' folder with the Database."""
    def __init__(self, base_path="master_references"):
        self.base_path = base_path

    def sync_to_db(self):
        # Walk through folders (e.g., /Contracts, /Invoices)
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
            
        categories = [d for d in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, d))]
        # Logic to ensure these exist in your 'OrganizationReferenceDocument' table or similar
        return categories

class ForgeryAnalyzer:
    """The 'Detective' that compares a suspect file to its master template."""
    
    def perform_ela(self, image_path, quality=90):
        """Detects if parts of the image have different compression levels (tampering)."""
        original = Image.open(image_path).convert('RGB')
        resaved_path = 'temp_resaved.jpg'
        original.save(resaved_path, 'JPEG', quality=quality)
        resaved = Image.open(resaved_path)
        
        # Calculate the absolute difference
        diff = ImageChops.difference(original, resaved)
        extrema = diff.getextrema()
        max_diff = max([ex[1] for ex in extrema])
        scale = 255.0 / max_diff if max_diff != 0 else 1
        diff = ImageChops.constant(diff, scale) # Enhance visibility
        
        # Clean up temp file
        try:
            os.remove(resaved_path)
        except OSError:
            pass
            
        return diff

    def check_structural_alignment(self, suspect_path, master_path):
        """Ensures text blocks haven't been shifted (98% threshold)."""
        img1 = cv2.imread(suspect_path, 0)
        img2 = cv2.imread(master_path, 0)
        
        if img1 is None or img2 is None:
            return 0.0
            
        # Resize suspect to match master if dimensions differ
        if img1.shape != img2.shape:
            img1 = cv2.resize(img1, (img2.shape[1], img2.shape[0]))
        
        # Simple template matching to check alignment
        res = cv2.matchTemplate(img1, img2, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(res)
        return max_val  # Returns 0.0 to 1.0 (e.g., 0.985)
