import os
import cv2
import numpy as np
from PIL import Image, ImageChops
import base64
import tensorflow as tf
from tensorflow.keras.models import load_model

def generate_difference_heatmap(ref_img_path, upload_img_path):
    """
    Generate a heatmap showing differences between two document images.
    """
    result = {
        'changed_regions': 0,
        'change_percentage': 0.0,
        'heatmap_b64': None
    }
    
    try:
        ref_img = cv2.imread(ref_img_path)
        upload_img = cv2.imread(upload_img_path)
        
        if ref_img is None or upload_img is None:
            return result
        
        # Resize to match
        h, w = ref_img.shape[:2]
        upload_img = cv2.resize(upload_img, (w, h))
        
        # Calculate difference
        diff = cv2.absdiff(ref_img, upload_img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        
        # Find changed regions
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result['changed_regions'] = len(contours)
        
        # Calculate percentage of changed pixels
        total_pixels = gray.size
        changed_pixels = np.count_nonzero(thresh)
        result['change_percentage'] = (changed_pixels / total_pixels) * 100
        
        # Create heatmap with highlighted changes
        changed_img = ref_img.copy()
        cv2.drawContours(changed_img, contours, -1, (0, 0, 255), 4)
        
        # Encode as base64
        _, buf = cv2.imencode('.png', changed_img)
        result['heatmap_b64'] = base64.b64encode(buf).decode()
        
    except Exception as e:
        print(f"⚠️ Heatmap generation error: {e}")
    
    return result


class DirectoryWatcher:
    """Syncs the physical 'master_references' folder with the Database."""
    def __init__(self, base_path="master_references"):
        self.base_path = base_path

    def sync_to_db(self):
        # Walk through folders (e.g., /Contracts, /Invoices)
        if not os.path.exists(self.base_path):
            os.makedirs(self.base_path)
            
        categories = [d for d in os.listdir(self.base_path) if os.path.isdir(os.path.join(self.base_path, d))]
        return categories


class ForgeryAnalyzer:
    """The 'Detective' that compares a suspect file to its master template."""
    
    def __init__(self, model_path='models/resnet50_features.h5'):
        self.model_path = model_path
        self.model = None
        
        # Check if the model exists locally
        if os.path.exists(model_path):
            try:
                # Load the pre-trained feature extractor (Siamese Backbone)
                self.model = load_model(model_path)
                print(f"✅ Loaded ResNet50 Siamese model from {model_path}")
            except Exception as e:
                print(f"⚠️ Error loading Siamese model: {e}")
        else:
            print(f"ℹ️ Model not found at {model_path}. Siamese check will be skipped.")

    def get_embedding(self, image_path):
        """Extracts 2048-dimensional embedding using the ResNet50 model."""
        if self.model is None:
            return None
            
        try:
            img = cv2.imread(image_path)
            if img is None:
                return None
                
            # ResNet50 expects 224x224 RGB images
            img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            img = cv2.resize(img, (224, 224))
            img = np.expand_dims(img, axis=0)
            img = tf.keras.applications.resnet50.preprocess_input(img)
            
            embedding = self.model.predict(img, verbose=0)
            return embedding[0]
        except Exception as e:
            print(f"⚠️ Embedding extraction error: {e}")
            return None

    def compare_embeddings(self, emb1, emb2):
        """Calculates cosine similarity between two 2048-dimensional vectors."""
        if emb1 is None or emb2 is None:
            return 0.0
        
        try:
            # Cosine similarity formula
            dot_product = np.dot(emb1, emb2)
            norm1 = np.linalg.norm(emb1)
            norm2 = np.linalg.norm(emb2)
            return dot_product / (norm1 * norm2)
        except Exception as e:
            print(f"⚠️ Similarity calculation error: {e}")
            return 0.0

    def perform_ela(self, image_path, quality=90):
        """Detects digital fingerprints of tampering using Error Level Analysis (ELA)."""
        try:
            original = Image.open(image_path).convert('RGB')
            resaved_path = 'temp_resaved.jpg'
            original.save(resaved_path, 'JPEG', quality=quality)
            resaved = Image.open(resaved_path)
            
            # Calculate the absolute difference between original and resaved
            diff = ImageChops.difference(original, resaved)
            extrema = diff.getextrema()
            max_diff = max([ex[1] for ex in extrema])
            scale = 255.0 / max_diff if max_diff != 0 else 1
            diff = ImageChops.constant(diff, scale) # Enhance visibility
            
            # Clean up temp file
            if os.path.exists(resaved_path):
                os.remove(resaved_path)
                
            return diff
        except Exception as e:
            print(f"⚠️ ELA error: {e}")
            return None

    def check_structural_alignment(self, suspect_path, master_path):
        """Advanced structural alignment using ORB (Oriented FAST and Rotated BRIEF)."""
        try:
            img1 = cv2.imread(suspect_path, 0) # Gray
            img2 = cv2.imread(master_path, 0) # Gray
            
            if img1 is None or img2 is None:
                return 0.0
                
            # Initialize ORB detector
            orb = cv2.ORB_create(1000)
            kp1, des1 = orb.detectAndCompute(img1, None)
            kp2, des2 = orb.detectAndCompute(img2, None)
            
            if des1 is None or des2 is None:
                return 0.0
                
            # Match descriptors using Hamming distance
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = bf.match(des1, des2)
            
            # Sort by distance
            matches = sorted(matches, key=lambda x: x.distance)
            
            if len(matches) < 20:
                return 0.0
                
            # Use RANSAC to find a robust homography and filter out bad matches
            src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
            dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
            
            M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
            
            if mask is None:
                return 0.0
                
            # Score is based on the ratio of inliers to total matches
            inliers = np.sum(mask)
            alignment_score = inliers / len(matches)
            
            return alignment_score 
        except Exception as e:
            print(f"⚠️ Structural alignment error: {e}")
            return 0.0
