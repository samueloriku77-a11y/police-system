"""
Advanced Multi-Stage Forgery Detection System
Cell 1-4: Image Alignment, Embedding Extraction, Blueprint Comparison, Pixel Subtraction
"""

import cv2
import numpy as np
from scipy.spatial import distance
import logging

logger = logging.getLogger(__name__)

class AdvancedForgeryDetector:
    """Multi-stage forgery detection with alignment, embeddings, and pixel analysis"""
    
    def __init__(self, embedding_model=None):
        """
        Initialize the detector
        
        Args:
            embedding_model: Pre-trained embedding model (EfficientNet-B0)
        """
        self.embedding_model = embedding_model
        self.orb = cv2.ORB_create(1000)
        # Tesseract path for Windows (optional, for advanced OCR)
        self.use_tesseract = False
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.use_tesseract = True
        except:
            pass  # Fallback to contour-based text detection
    
    def align_to_blueprint(self, target_img, blueprint_img):
        """
        CELL 1: Image Alignment - Align suspect image to reference using ORB keypoints
        
        Handles rotation, zoom, skew by finding homography transformation.
        
        Args:
            target_img: Suspect/uploaded image
            blueprint_img: Reference/original image from database
            
        Returns:
            aligned_img: Target image warped to match blueprint geometry
            h: Homography matrix (can be saved for forensics)
        """
        try:
            # Detect keypoints
            kp1, des1 = self.orb.detectAndCompute(target_img, None)
            kp2, des2 = self.orb.detectAndCompute(blueprint_img, None)
            
            if des1 is None or des2 is None or len(kp1) < 4 or len(kp2) < 4:
                logger.warning("Not enough keypoints for alignment")
                return target_img, None
            
            # Match features using BFMatcher
            bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
            matches = sorted(bf.match(des1, des2), key=lambda x: x.distance)
            
            if len(matches) < 4:
                logger.warning("Not enough matches for homography")
                return target_img, None
            
            # Extract matched points
            points1 = np.zeros((len(matches), 2), dtype=np.float32)
            points2 = np.zeros((len(matches), 2), dtype=np.float32)
            
            for i, match in enumerate(matches):
                points1[i, :] = kp1[match.queryIdx].pt
                points2[i, :] = kp2[match.trainIdx].pt
            
            # Find homography transformation (the "blueprint" transformation)
            h, mask = cv2.findHomography(points1, points2, cv2.RANSAC)
            
            if h is None:
                logger.warning("Could not compute homography")
                return target_img, None
            
            # Warp target image to match blueprint's perspective
            height, width = blueprint_img.shape[:2]
            aligned_img = cv2.warpPerspective(target_img, h, (width, height))
            
            logger.info(f"✓ Image aligned: {len(matches)} matches found")
            return aligned_img, h
            
        except Exception as e:
            logger.error(f"Alignment error: {e}")
            return target_img, None
    
    def extract_embedding(self, img, model=None):
        """
        CELL 2: Embedding Extraction - Extract 1280-dim feature vector using EfficientNet-B0
        
        Stops at global average pooling layer (before classification head).
        L2 normalized for Euclidean distance comparison.
        
        Args:
            img: Input image (BGR)
            model: Pre-trained embedding model
            
        Returns:
            embedding: 1280-dimensional L2-normalized feature vector
        """
        try:
            if model is None:
                model = self.embedding_model
            
            if model is None:
                logger.warning("No embedding model available")
                return None
            
            # Prepare image
            if len(img.shape) == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
            
            # Resize to model input
            img_resized = cv2.resize(img, (224, 224))
            img_normalized = img_resized / 255.0  # Normalize to [0, 1]
            
            # Add batch dimension and predict
            img_batch = np.expand_dims(img_normalized, 0)
            embedding = model.predict(img_batch, verbose=0)
            
            # Return normalized embedding
            return embedding[0]
            
        except Exception as e:
            logger.error(f"Embedding extraction error: {e}")
            return None
    
    def compare_to_blueprint(self, suspect_img, blueprint_img, embedding_model=None):
        """
        CELL 3: Blueprint Comparator - Euclidean distance between embeddings
        
        Lower score = more similar to original
        Higher score = likely forged/edited
        
        Args:
            suspect_img: Uploaded image (should be aligned first)
            blueprint_img: Reference image from database
            embedding_model: Model to use for extraction
            
        Returns:
            dist: Euclidean distance (0 = identical, higher = different)
            vec_suspect: Suspect embedding vector
            vec_blueprint: Blueprint embedding vector
        """
        try:
            # Extract embeddings
            vec_suspect = self.extract_embedding(suspect_img, embedding_model)
            vec_blueprint = self.extract_embedding(blueprint_img, embedding_model)
            
            if vec_suspect is None or vec_blueprint is None:
                logger.warning("Could not extract embeddings")
                return None, None, None
            
            # Calculate Euclidean distance
            try:
                norm_product = np.linalg.norm(vec_suspect) * np.linalg.norm(vec_blueprint)
                if norm_product == 0:
                    dist = float('inf')
                else:
                    dist = distance.euclidean(vec_suspect, vec_blueprint)
            except:
                # Fallback to cosine similarity if Euclidean fails
                dist = distance.cosine(vec_suspect, vec_blueprint)
            
            logger.info(f"✓ Embedding distance: {dist:.4f}")
            return dist, vec_suspect, vec_blueprint
            
        except Exception as e:
            logger.error(f"Blueprint comparison error: {e}")
            return None, None, None
    
    def get_diff_mask(self, aligned_suspect, blueprint, threshold=30):
        """
        CELL 4: Pixel-Level Blueprint Subtraction
        
        Highlights exactly where forgery occurred by comparing pixel values.
        High-difference areas = edited/forged regions (e.g., rubbed digits).
        
        Args:
            aligned_suspect: Aligned suspect image
            blueprint: Reference image
            threshold: Sensitivity (lower = more sensitive to changes)
            
        Returns:
            thresh: Binary mask showing changed regions
            diff_visual: Heatmap showing intensity of differences
            change_regions: List of bounding boxes for changed areas
        """
        try:
            # Ensure same dimensions
            if aligned_suspect.shape != blueprint.shape:
                blueprint = cv2.resize(blueprint, (aligned_suspect.shape[1], aligned_suspect.shape[0]))
            
            # Convert to grayscale
            if len(aligned_suspect.shape) == 3:
                gray_suspect = cv2.cvtColor(aligned_suspect, cv2.COLOR_BGR2GRAY)
            else:
                gray_suspect = aligned_suspect
            
            if len(blueprint.shape) == 3:
                gray_blueprint = cv2.cvtColor(blueprint, cv2.COLOR_BGR2GRAY)
            else:
                gray_blueprint = blueprint
            
            # Absolute difference (pixel-level comparison)
            diff = cv2.absdiff(gray_suspect, gray_blueprint)
            
            # Create binary mask of significant differences
            _, thresh = cv2.threshold(diff, threshold, 255, cv2.THRESH_BINARY)
            
            # Create heatmap visualization
            diff_visual = cv2.applyColorMap((diff / 2.0).astype(np.uint8), cv2.COLORMAP_HOT)
            
            # Find contours (changed regions)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            change_regions = []
            
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                if w > 5 and h > 5:  # Filter small noise
                    change_regions.append({
                        'x': int(x),
                        'y': int(y),
                        'width': int(w),
                        'height': int(h),
                        'area': int(w * h)
                    })
            
            logger.info(f"✓ Diff mask created: {len(change_regions)} regions detected")
            return thresh, diff_visual, change_regions
            
        except Exception as e:
            logger.error(f"Diff mask error: {e}")
            return None, None, []
    
    def detect_text_regions(self, img, min_text_width=8, min_text_height=8):
        """
        CELL 5: Text Detection - Identify word and text regions using contour analysis
        
        Finds connected components that are likely text by analyzing contour properties.
        Works without Tesseract as a fallback.
        
        Args:
            img: Input image (BGR)
            min_text_width: Minimum width for text region
            min_text_height: Minimum height for text region
            
        Returns:
            text_regions: List of dicts with coordinates and properties
                [{x, y, width, height, area, confidence}, ...]
        """
        try:
            # Convert to grayscale and binary
            if len(img.shape) == 3:
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            else:
                gray = img
            
            # Apply morphological operations to enhance text
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
            morph = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel, iterations=1)
            
            # Threshold for text detection
            _, binary = cv2.threshold(morph, 150, 255, cv2.THRESH_BINARY)
            
            # Find contours (text characters/words)
            contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            text_regions = []
            for contour in contours:
                x, y, w, h = cv2.boundingRect(contour)
                
                # Filter by size (text regions)
                if w >= min_text_width and h >= min_text_height:
                    # Calculate solidity to filter text-like shapes
                    area = cv2.contourArea(contour)
                    hull_area = cv2.contourArea(cv2.convexHull(contour))
                    solidity = area / hull_area if hull_area > 0 else 0
                    
                    # Text typically has 0.5-0.95 solidity
                    if 0.3 < solidity < 0.98:
                        text_regions.append({
                            'x': int(x),
                            'y': int(y),
                            'width': int(w),
                            'height': int(h),
                            'area': int(area),
                            'solidity': float(solidity),
                            'confidence': min(1.0, solidity)  # 0-1 confidence
                        })
            
            logger.info(f"✓ Text detection: {len(text_regions)} text regions found")
            return text_regions
            
        except Exception as e:
            logger.error(f"Text detection error: {e}")
            return []
    
    def analyze_text_forgeries(self, aligned_suspect, blueprint, text_regions, diff_mask):
        """
        CELL 6: Text-Focused Forgery Analysis
        
        Analyzes only text regions for forgeries. Identifies which specific words/areas
        have been edited by comparing changes in text regions.
        
        Args:
            aligned_suspect: Aligned suspect image
            blueprint: Reference image
            text_regions: List of text region coordinates
            diff_mask: Binary mask from pixel-level analysis
            
        Returns:
            forged_text_regions: List of text regions with forgery evidence
                [{x, y, width, height, forgery_score, has_changes}, ...]
        """
        try:
            forged_text_regions = []
            
            if diff_mask is None or len(text_regions) == 0:
                return forged_text_regions
            
            # Analyze each text region for changes
            for region in text_regions:
                x, y, w, h = region['x'], region['y'], region['width'], region['height']
                
                # Extract region from diff mask
                diff_region = diff_mask[y:y+h, x:x+w]
                
                # Calculate percentage of changed pixels in this region
                if diff_region.size > 0:
                    changed_pixels = np.count_nonzero(diff_region)
                    change_percentage = (changed_pixels / diff_region.size) * 100
                else:
                    change_percentage = 0
                
                # If > 15% of text region is changed, flag as forged
                if change_percentage > 15:
                    forged_text_regions.append({
                        'x': region['x'],
                        'y': region['y'],
                        'width': region['width'],
                        'height': region['height'],
                        'area': region['area'],
                        'forgery_score': min(100.0, change_percentage),
                        'has_changes': True,
                        'changed_pixels': int(changed_pixels),
                        'total_pixels': int(diff_region.size),
                        'type': 'TEXT_FORGERY'
                    })
            
            logger.info(f"✓ Text forgery analysis: {len(forged_text_regions)} forged text regions")
            return forged_text_regions
            
        except Exception as e:
            logger.error(f"Text forgery analysis error: {e}")
            return []
    
    def get_forged_words_visualization(self, img, forged_text_regions, color=(0, 0, 255)):
        """
        Create visualization highlighting forged text regions with coordinates
        
        Args:
            img: Original image
            forged_text_regions: List of forged text regions with coordinates
            color: BGR color for highlighting (default: red)
            
        Returns:
            annotated_img: Image with forged regions marked and labeled
        """
        try:
            annotated_img = img.copy()
            
            for i, region in enumerate(forged_text_regions, 1):
                x, y, w, h = region['x'], region['y'], region['width'], region['height']
                score = region.get('forgery_score', 0)
                
                # Draw bounding box
                cv2.rectangle(annotated_img, (x, y), (x+w, y+h), color, 2)
                
                # Draw label with coordinates and score
                label = f"FORGED#{i} ({x},{y}) Score:{score:.1f}%"
                cv2.putText(annotated_img, label, (x, y-5), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
                
                # Inner text showing dimensions
                dim_label = f"{w}x{h}px"
                cv2.putText(annotated_img, dim_label, (x+5, y+h-5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.35, color, 1)
            
            return annotated_img
            
        except Exception as e:
            logger.error(f"Visualization error: {e}")
            return img
    
    def full_analysis(self, suspect_img, blueprint_img, embedding_model=None):
        """
        Complete 4-cell analysis pipeline
        
        Args:
            suspect_img: Uploaded image
            blueprint_img: Reference image
            embedding_model: EfficientNet model
            
        Returns:
            results: Dict with alignment, embedding distance, and diff mask
        """
        try:
            results = {
                'alignment_success': False,
                'embedding_distance': None,
                'diff_mask': None,
                'diff_visual': None,
                'change_regions': [],
                'text_regions': [],
                'forged_text_regions': [],
                'text_visualization': None,
                'homography': None,
                'forgery_confidence': 0.0
            }
            
            # CELL 1: Alignment
            aligned_suspect, h = self.align_to_blueprint(suspect_img, blueprint_img)
            results['alignment_success'] = h is not None
            results['homography'] = h
            
            # CELL 3: Embedding comparison
            dist, vec_s, vec_b = self.compare_to_blueprint(
                aligned_suspect, 
                blueprint_img, 
                embedding_model or self.embedding_model
            )
            
            if dist is not None:
                # Normalize distance to forgery confidence (0-1 scale)
                # Assuming distance typically ranges 0-2.0, cap at 1.0
                results['embedding_distance'] = float(dist)
                results['forgery_confidence'] = min(1.0, dist / 2.0)
            
            # CELL 4: Pixel-level analysis
            thresh, diff_visual, regions = self.get_diff_mask(aligned_suspect, blueprint_img)
            results['diff_mask'] = thresh
            results['diff_visual'] = diff_visual
            results['change_regions'] = regions
            
            # CELL 5: Text Detection - Find all text regions
            text_regions = self.detect_text_regions(aligned_suspect)
            results['text_regions'] = text_regions
            
            # CELL 6: Text-Focused Analysis - Check which text regions have forgeries
            if thresh is not None and len(text_regions) > 0:
                forged_text = self.analyze_text_forgeries(aligned_suspect, blueprint_img, text_regions, thresh)
                results['forged_text_regions'] = forged_text
                
                # Create visualization showing forged text with coordinates
                if len(forged_text) > 0:
                    viz = self.get_forged_words_visualization(aligned_suspect, forged_text)
                    results['text_visualization'] = viz
                    logger.info(f"✓ Found {len(forged_text)} forged text regions with coordinates")
            else:
                results['forged_text_regions'] = []
            
            return results
            
        except Exception as e:
            logger.error(f"Full analysis error: {e}")
            return None


# Helper function for integration
def create_detector(embedding_model=None):
    """Factory function to create Advanced Forgery Detector"""
    return AdvancedForgeryDetector(embedding_model)
