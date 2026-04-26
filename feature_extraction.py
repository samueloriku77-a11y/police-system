from tensorflow.keras.preprocessing import image as keras_image
from tensorflow.keras import layers, Model
import pickle
import os
import numpy as np
import tensorflow as tf
import cv2
from typing import Optional, Tuple, List, Dict
from preprocessing import ImagePreprocessor
from sklearn.svm import SVC
from sklearn.preprocessing import StandardScaler
import json
from config import MODEL_PATH, MODEL_METADATA_PATH
import base64

try:
    from document_recognizer_module import DocumentRecognizer
    DOCUMENT_RECOGNIZER_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Warning: Document Recognizer not available: {e}")
    DOCUMENT_RECOGNIZER_AVAILABLE = False

class FeatureExtractor:
    """Main feature extractor for similarity + training features - LOCAL ONLY"""
    TRAINING_EMBEDDING_DIM = 1280
    FEATURE_EMBEDDING_DIM = 512
    MODEL_INPUT_SIZE = (224, 224, 3)
    
    def __init__(self, model_path=None, metadata_path=None):
        self.preprocessor = ImagePreprocessor()
        self.model_path = model_path or MODEL_PATH
        self.metadata_path = metadata_path or MODEL_METADATA_PATH
        
        # Build training extractor
        self.training_extractor = self._build_training_feature_extractor()
        
        # Load local classifier
        self.classifier, self.scaler = self._load_trained_classifier()
        
        # Load local similarity model
        self.model = self._load_similarity_model()
        
        # Load document recognizer (81% accuracy) for enhanced document analysis
        self.document_recognizer = self._init_document_recognizer()
    
    def _init_document_recognizer(self):
        """Initialize document recognizer with 81% accuracy"""
        if DOCUMENT_RECOGNIZER_AVAILABLE:
            try:
                recognizer = DocumentRecognizer()
                print(f"✅ Document Recognizer initialized (81% accuracy)")
                return recognizer
            except Exception as e:
                print(f"⚠️  Document Recognizer initialization failed: {e}")
                return None
        return None
    
    def _load_similarity_model(self):
        """Load local similarity model - NO DOWNLOAD"""
        if os.path.exists(self.model_path):
            try:
                print(f"📦 Loading LOCAL model: {self.model_path}")
                custom_objects = {}
                if os.path.exists(self.metadata_path):
                    with open(self.metadata_path, 'r') as f:
                        metadata = json.load(f)
                    custom_objects = metadata.get('custom_objects', {})
                model = tf.keras.models.load_model(self.model_path, custom_objects=custom_objects, compile=False)
                print(f"✅ LOCAL model loaded successfully!")
                
                # Validate for similarity model (3 channels)
                if model.input_shape[-1] != 3:
                    print(f"⚠️ Local model input channels {model.input_shape[-1]} != 3, using built similarity model")
                    return self._build_similarity_model()
                return model
            except Exception as e:
                print(f"⚠️ Local model load failed: {e} - using built model")
        print("⚠️ Local model not found - using built model")
        return self._build_similarity_model()
    
    def _load_trained_classifier(self):
        """Load local SVM classifier"""
        try:
            with open('models/classifier.pkl', 'rb') as f:
                clf = pickle.load(f)
            with open('models/scaler.pkl', 'rb') as f:
                scaler = pickle.load(f)
            print("✅ Local classifier loaded")
            return clf, scaler
        except Exception as e:
            print(f"⚠️ Local classifier load failed: {e}")
            return None, None
    
    def _build_similarity_model(self):
        """Build model with pretrained weights"""
        inputs = layers.Input(shape=self.MODEL_INPUT_SIZE)
        backbone = tf.keras.applications.EfficientNetB0(
            include_top=False,
            weights="imagenet",
            input_tensor=inputs
        )
        x = backbone.output
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.3)(x)
        outputs = layers.Dense(self.FEATURE_EMBEDDING_DIM, activation=None)(x)
        model = Model(inputs, outputs)
        print("Built similarity model with ImageNet weights")
        return model
    
    def _build_training_feature_extractor(self):
        """Build training extractor with pretrained weights"""
        inputs = layers.Input(shape=self.MODEL_INPUT_SIZE)
        backbone = tf.keras.applications.EfficientNetB0(
            include_top=False,
            weights="imagenet",
            input_tensor=inputs
        )
        x = backbone.output
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.3)(x)
        outputs = layers.Dense(self.TRAINING_EMBEDDING_DIM, activation=None)(x)
        model = Model(inputs, outputs)
        return model
    
    def prepare_image_for_model(self, img):
        img = cv2.resize(img, self.MODEL_INPUT_SIZE[:2])
        img = img.astype(np.float32) / 255.0
        img = np.expand_dims(img, 0)
        return img
    
    def extract_features(self, image_path, preprocess=True):
        img = cv2.imread(image_path)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if preprocess:
            gray = self.preprocessor.enhance_contrast(img)
            img = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        features = self.model.predict(self.prepare_image_for_model(img), verbose=0)[0]
        return features
    
    def extract_enhanced_features(self, image_path: str) -> Tuple[np.ndarray, Dict]:
        """
        Extract features with document recognition enhancement (81% accuracy)
        
        Args:
            image_path: Path to image
            
        Returns:
            Tuple of (feature_vector, document_metadata)
        """
        document_metadata = {'document_recognizer_available': False}
        
        # Try to enhance with document recognizer
        if self.document_recognizer:
            try:
                extracted_doc, metadata = self.document_recognizer.enhance_extracted_document(image_path)
                document_metadata = metadata
                document_metadata['document_recognizer_available'] = True
                document_metadata['model_accuracy'] = 0.81
                
                if extracted_doc is not None:
                    # Use enhanced document for feature extraction
                    enhanced_rgb = cv2.cvtColor(extracted_doc, cv2.COLOR_RGB2BGR)
                    features = self.extract_features_from_array(enhanced_rgb)
                    return features, document_metadata
            except Exception as e:
                print(f"⚠️  Document enhancement failed: {e}. Using standard extraction.")
        
        # Fallback to standard extraction
        features = self.extract_features(image_path, preprocess=True)
        return features, document_metadata
    
    def extract_features_from_array(self, img_array: np.ndarray) -> np.ndarray:
        """
        Extract features from image array (not file)
        
        Args:
            img_array: Image array (BGR format)
            
        Returns:
            Feature vector
        """
        img_rgb = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
        gray = self.preprocessor.enhance_contrast(img_rgb)
        img_rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        features = self.model.predict(self.prepare_image_for_model(img_rgb), verbose=0)[0]
        return features

class ForgeryDetector:
    """Forgery detector with pretrained weights, metrics, patterns"""
    def __init__(self, model_path="models/aether_forgery_model.h5"):
        self.model_path = model_path
        self.model = self._load_local_model()
        self.preprocessor = ImagePreprocessor()
        # Initialize document recognizer for enhanced detection
        self.document_recognizer = self._init_document_recognizer()
    
    def _init_document_recognizer(self):
        """Initialize document recognizer with 81% accuracy"""
        if DOCUMENT_RECOGNIZER_AVAILABLE:
            try:
                recognizer = DocumentRecognizer()
                print(f"✅ Document Recognizer linked to ForgeryDetector (81% accuracy)")
                return recognizer
            except Exception as e:
                print(f"⚠️  Document Recognizer not available in ForgeryDetector: {e}")
                return None
        return None
    
    def _load_local_model(self):
        """Load local forgery model"""
        if os.path.exists(self.model_path):
            try:
                print(f" Loading LOCAL forgery model: {self.model_path}")
                model = tf.keras.models.load_model(self.model_path, compile=False)
                print(" Local forgery model loaded")
                return model
            except Exception as e:
                print(f" Local model load failed: {e}")
        print(" Local model not found - using pretrained build")
        return self._build_forgery_model()
    
    def _build_forgery_model(self):
        """Build with pretrained EfficientNetV2S"""
        inputs = layers.Input(shape=(224, 224, 8))
        x = layers.Conv2D(32, 3, activation='relu', padding='same')(inputs)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(3, 1, activation='sigmoid', padding='same')(x)
        backbone = tf.keras.applications.EfficientNetV2S(weights="imagenet", include_top=False, input_tensor=x)
        x = backbone.output
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.5)(x)
        outputs = layers.Dense(1, activation='sigmoid')(x)
        model = tf.keras.Model(inputs, outputs)
        print("Built forgery model with ImageNet pretrained weights")
        return model
    
    def normalize(self, ch):
        """Normalize channel to 0-1"""
        ch_min, ch_max = ch.min(), ch.max()
        if ch_max > ch_min:
            return (ch - ch_min) / (ch_max - ch_min)
        return ch
    
    def _extract_metrics(self, gray, grad_mag, laplacian, canny):
        """Extract explicit forgery metrics"""
        # ELA-like residual (simplified)
        ela = np.abs(np.gradient(gray)[0]) + np.abs(np.gradient(gray)[1])
        ela_norm = np.mean(ela) / 255.0 if ela.max() > 0 else 0.0
        
        # Edge density
        edge_density = np.mean(canny)
        
        # Laplacian variance (sharpness/blur)
        lap_var = np.var(laplacian)
        lap_var_norm = lap_var / (np.var(laplacian) + 1e-8)  # Normalized
        
        # Noise level proxy (high freq)
        noise_level = np.std(grad_mag)
        
        return {
            'ela_norm': float(ela_norm),
            'edge_density': float(edge_density),
            'lap_var': float(lap_var_norm),
            'noise_level': float(noise_level)
        }
    
    def detect_forged_regions(self, image_path):
        try:
            img = cv2.imread(image_path)
            if img is None:
                return {'forged_ratio': 0.0, 'regions': [], 'heatmap_b64': '', 'metrics': {}, 'verdict': 'AUTHENTIC'}
            
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
            
            gray_uint8 = (gray * 255).astype(np.uint8)
            canny = cv2.Canny(gray_uint8, 50, 150).astype(np.float32) / 255.0
            sobelx = self.normalize(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3))
            sobely = self.normalize(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
            laplacian = self.normalize(cv2.Laplacian(gray, cv2.CV_32F))
            edges2 = self.normalize(cv2.Sobel(gray, cv2.CV_32F, 1, 1, ksize=3))
            grad_mag = np.sqrt(sobelx**2 + sobely**2)
            grad_mag_norm = grad_mag  # Use raw normalized gradient magnitude
            lap_norm = laplacian
            
            # Extract metrics FIRST
            metrics = self._extract_metrics(gray, grad_mag_norm, laplacian, canny)
            
            # 8-channel input - consistent with training: RGB + gradients/edges
            rgb_float = img_rgb.astype(np.float32) / 255.0
            resized_channels = []
            for c in [rgb_float[:,:,0], rgb_float[:,:,1], rgb_float[:,:,2], grad_mag_norm, lap_norm, canny, gray, edges2]:
                resized_channels.append(cv2.resize(c, (224, 224)))
            input_tensor = np.stack(resized_channels, axis=-1)
            input_tensor = np.expand_dims(input_tensor, 0)
            
            forged_prob = self.model.predict(input_tensor, verbose=0)[0][0]
            
            # Probability calibration
            forged_prob = np.clip(forged_prob, 0.0, 1.0)
            forged_prob = (forged_prob - 0.5) * 1.5 + 0.5
            forged_prob = np.clip(forged_prob, 0.0, 1.0)
            
            binary_anomaly = (grad_mag_norm > 0.75).astype(np.uint8) * 255
            contours, _ = cv2.findContours(binary_anomaly, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            regions = []
            img_area = img.shape[0] * img.shape[1]
            min_area = img_area * 0.0005  # 0.05% of image
            max_area = img_area * 0.2     # 20% of image
            
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if min_area < area < max_area:
                    x, y, w, h = cv2.boundingRect(cnt)
                    regions.append([int(x), int(y), int(x+w), int(y+h)])
            
            # Sanity check - low prob and no regions = clean
            if forged_prob < 0.3 and len(regions) == 0:
                print(" Sanity check: Low probability and clean metrics, marking AUTHENTIC")
                return {
                    'forged_ratio': 0.0,
                    'regions': [],
                    'heatmap_b64': '',
                    'metrics': metrics,
                    'verdict': 'AUTHENTIC',
                    'pattern_check': False,
                    'calibrated_prob': float(forged_prob)
                }
            
            # Pattern check: high calibrated prob + bad metrics
            pattern_check = (forged_prob > 0.6) and (
                metrics['ela_norm'] > 0.08 or 
                metrics['edge_density'] > 0.25 or 
                metrics['noise_level'] > 0.15
            )
            

            
            forged_ratio = forged_prob if (pattern_check or len(regions) > 1) else 0.0
            verdict = 'FORGED' if forged_ratio > 0.6 else 'AUTHENTIC'
            
            # Real heatmap from anomaly
            h, w = img_rgb.shape[:2]
            max_dim = 800
            scale = min(max_dim/w, max_dim/h) if max(w, h) > max_dim else 1.0
            new_w, new_h = int(w * scale), int(h * scale)
            
            heatmap = cv2.resize(grad_mag_norm, (new_w, new_h))
            heatmap_8bit = (heatmap * 255).astype(np.uint8)
            heatmap_colored = cv2.applyColorMap(heatmap_8bit, cv2.COLORMAP_JET)
            _, buffer = cv2.imencode('.jpg', heatmap_colored, [cv2.IMWRITE_JPEG_QUALITY, 65])
            heatmap_b64 = base64.b64encode(buffer).decode()
            
            # Annotated image for client presentation
            annotated_img = img.copy()
            for (x1, y1, x2, y2) in regions:
                cv2.rectangle(annotated_img, (x1, y1), (x2, y2), (0, 0, 255), 4)
                cv2.putText(annotated_img, "Suspicious Region", (x1, max(y1 - 10, 0)), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            
            annotated_resized = cv2.resize(annotated_img, (new_w, new_h))
            _, buffer_anno = cv2.imencode('.jpg', annotated_resized, [cv2.IMWRITE_JPEG_QUALITY, 65])
            annotated_b64 = base64.b64encode(buffer_anno).decode()
            
            print(f"🔍 Calib Prob: {forged_prob:.3f}, Regions: {len(regions)}, Pattern: {pattern_check}, Metrics: {metrics}, Verdict: {verdict}")
            
            return {
                'forged_ratio': float(forged_ratio),
                'regions': regions,
                'heatmap_b64': heatmap_b64,
                'annotated_b64': annotated_b64,
                'metrics': metrics,
                'verdict': verdict,
                'pattern_check': bool(pattern_check),
                'calibrated_prob': float(forged_prob)
            }
        except Exception as e:
            print(f'Forgery detection error: {e}')
            return {'forged_ratio': 0.0, 'regions': [], 'heatmap_b64': '', 'metrics': {}, 'verdict': 'ERROR', 'calibrated_prob': 0.0, 'pattern_check': False}
    
    def predict_whole_document(self, image_path):
        """Whole doc prediction with metrics"""
        results = self.detect_forged_regions(image_path)
        return {
            'is_forged': bool(results.get('verdict', 'ERROR') == 'FORGED'),
            'confidence': float(results.get('forged_ratio', 0.0)),
            'forged_prob': float(results.get('calibrated_prob', 0.0)),
            'metrics': results.get('metrics', {}),
            'regions': results.get('regions', [])
        }
    
print("FORGERY DETECTOR READY - PRETRAINED WEIGHTS + METRICS + PATTERNS + CALIBRATION")
