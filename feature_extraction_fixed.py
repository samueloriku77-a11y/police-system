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

class FeatureExtractor:
    """Main feature extractor for similarity + training features - LOCAL ONLY"""
    TRAINING_EMBEDDING_DIM = 1280
    FEATURE_EMBEDDING_DIM = 512
    MODEL_INPUT_SIZE = (224, 224, 3)
    
    def __init__(self, model_path=None, metadata_path=None):
        self.preprocessor = ImagePreprocessor()
        self.model_path = model_path or MODEL_PATH
        self.metadata_path = metadata_path or MODEL_METADATA_PATH
        
        # Build training extractor - NO DOWNLOAD
        self.training_extractor = self._build_training_feature_extractor()
        
        # Load local classifier
        self.classifier, self.scaler = self._load_trained_classifier()
        
        # Load local similarity model
        self.model = self._load_similarity_model()
    
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
        """Build model without pretrained weights"""
        inputs = layers.Input(shape=self.MODEL_INPUT_SIZE)
        backbone = tf.keras.applications.EfficientNetB0(
            include_top=False,
            weights=None,
            input_tensor=inputs
        )
        x = backbone.output
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.3)(x)
        outputs = layers.Dense(self.FEATURE_EMBEDDING_DIM, activation=None)(x)
        model = Model(inputs, outputs)
        print("Built similarity model (NO pretrained weights)")
        return model
    
    def _build_training_feature_extractor(self):
        """Build training extractor without pretrained"""
        inputs = layers.Input(shape=self.MODEL_INPUT_SIZE)
        backbone = tf.keras.applications.EfficientNetB0(
            include_top=False,
            weights=None,
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

class ForgeryDetector:
    """Forgery detector - LOCAL ONLY"""
    def __init__(self, model_path="models/aether_forgery_model.h5"):
        self.model_path = model_path
        self.model = self._load_local_model()
    
    def _load_local_model(self):
        """Load local forgery model"""
        if os.path.exists(self.model_path):
            try:
                print(f"📦 Loading LOCAL forgery model: {self.model_path}")
                model = tf.keras.models.load_model(self.model_path, compile=False)
                print("✅ Local forgery model loaded")
                return model
            except Exception as e:
                print(f"⚠️ Local forgery model load failed: {e}")
        print("⚠️ Local forgery model not found")
        return self._build_forgery_model()
    
    def _build_forgery_model(self):
        """Build without pretrained"""
        inputs = layers.Input(shape=(224, 224, 8))
        x = layers.Conv2D(32, 3, activation='relu', padding='same')(inputs)
        x = layers.BatchNormalization()(x)
        x = layers.Conv2D(3, 1, activation='sigmoid', padding='same')(x)
        backbone = tf.keras.applications.EfficientNetV2S(weights=None, include_top=False, input_tensor=x)
        x = backbone.output
        x = layers.GlobalAveragePooling2D()(x)
        x = layers.Dropout(0.5)(x)
        outputs = layers.Dense(1, activation='sigmoid')(x)
        model = tf.keras.Model(inputs, outputs)
        print("Built forgery model (NO pretrained)")
        return model
    
    def detect_forged_regions(self, image_path):
        """Region-first detection: anomaly → contours → bbox"""
        img = cv2.imread(image_path)
        if img is None:
            return {'forged_ratio': 0.0, 'regions': [], 'heatmap_b64': ''}
        
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32) / 255.0
        
        # Edge features
        gray_uint8 = (gray * 255).astype(np.uint8)
        canny = cv2.Canny(gray_uint8, 50, 150).astype(np.float32) / 255.0
        sobelx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        sobely = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        laplacian = cv2.Laplacian(gray, cv2.CV_32F)
        
        # Normalize
        grad_mag = np.sqrt(sobelx**2 + sobely**2)
        grad_mag_norm = grad_mag / (np.max(grad_mag) + 1e-8)
        lap_norm = np.abs(laplacian) / (np.max(np.abs(laplacian)) + 1e-8)
        
        # Anomaly map (deviation from clean document patterns)
        expected_grad = np.ones_like(gray) * 0.12
        anomaly_map = np.abs(grad_mag_norm - expected_grad)
        
        # Model input
        rgb_float = img_rgb.astype(np.float32) / 255.0
        channels = [rgb_float[:,:,0], rgb_float[:,:,1], rgb_float[:,:,2], anomaly_map, lap_norm, canny, gray, grad_mag_norm]
        input_tensor = np.stack(channels, axis=-1)
        input_tensor = cv2.resize(input_tensor, (224, 224))
        input_tensor = np.expand_dims(input_tensor, 0)
        
        # Model prediction
        forged_prob = self.model.predict(input_tensor, verbose=0)[0][0]
        
        # Real region detection
        binary_anomaly = (anomaly_map > 0.5).astype(np.uint8) * 255
        contours, _ = cv2.findContours(binary_anomaly, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        regions = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if 500 < area < 10000:  # Realistic forged patches
                x, y, w, h = cv2.boundingRect(cnt)
                regions.append([int(x), int(y), int(x+w), int(y+h)])
        
        # Heatmap
        h, w = img_rgb.shape[:2]
        heatmap = anomaly_map * forged_prob  # Weighted by model confidence
        heatmap_resized = cv2.resize(heatmap, (224, 224))
        heatmap_8bit = (heatmap_resized * 255).astype(np.uint8)
        heatmap_colored = cv2.applyColorMap(heatmap_8bit, cv2.COLORMAP_JET)
        _, buffer = cv2.imencode('.png', heatmap_colored)
        heatmap_b64 = base64.b64encode(buffer).decode()
        
        print(f"🔍 {len(regions)} regions, prob={forged_prob:.3f}")
        return {
            'forged_ratio': float(forged_prob),
            'regions': regions,
            'heatmap_b64': heatmap_b64
        }
    
    def predict_whole_document(self, image_path):
        """Fallback whole-doc prediction"""
        pred = self.detect_forged_regions(image_path)
        is_forged = len(pred['regions']) > 0
        confidence = pred['forged_ratio']
        return {'is_forged': is_forged, 'confidence': confidence, 'forged_prob': pred['forged_ratio']}

print("LOCAL MODEL SYSTEM READY - NO DOWNLOADS")

