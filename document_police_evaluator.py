"""
Context-Aware Document Police Evaluator
Implements forensic document analysis with Siamese networks, ELA, and zone-based validation.
"""

import numpy as np
import cv2
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers
import base64
import io
from PIL import Image


# ============================================================================
# ENUMS & DATA STRUCTURES
# ============================================================================

class DocumentTypeEnum(str, Enum):
    """Supported document types with predefined zone configurations."""
    INVOICE = "Invoice"
    CONTRACT = "Contract"
    ID_CARD = "ID_Card"
    CHECK = "Check"
    PASSPORT = "Passport"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    CLEAN = "clean"


@dataclass
class ProtectedZone:
    """Represents a protected zone in a document."""
    zone_id: str
    zone_name: str
    document_type: str
    coordinates: Tuple[int, int, int, int]  # (x1, y1, x2, y2)
    similarity_threshold: float = 0.95
    priority: str = "critical"
    description: str = ""
    

@dataclass
class ForensicResult:
    """Complete forensic analysis result."""
    document_id: str
    document_type: str
    overall_similarity: float
    ela_score: float
    structural_alignment_score: float
    siamese_confidence: float
    zone_violations: List[Dict[str, Any]] = field(default_factory=list)
    anomaly_regions: List[Dict[str, Any]] = field(default_factory=list)
    alert_severity: AlertSeverity = AlertSeverity.CLEAN
    heatmap_b64: str = ""
    ela_heatmap_b64: str = ""
    structural_heatmap_b64: str = ""
    timestamp: str = ""
    forensic_report: str = ""


@dataclass
class DocumentTypeConfig:
    """Configuration for a specific document type."""
    document_type: str
    protected_zones: List[ProtectedZone] = field(default_factory=list)
    similarity_threshold: float = 0.95
    ela_sensitivity: float = 0.7
    structural_tolerance: float = 0.1
    description: str = ""


# ============================================================================
# 1. DOCUMENT TYPE MAPPER
# ============================================================================

class DocumentTypeMapper:
    """Maps document types to their configurations and protected zones."""
    
    def __init__(self):
        self.type_configs = self._initialize_document_types()
    
    def _initialize_document_types(self) -> Dict[str, DocumentTypeConfig]:
        """Initialize predefined document type configurations."""
        configs = {}
        
        # ===== INVOICE =====
        invoice_zones = [
            ProtectedZone(
                zone_id="bank_details",
                zone_name="Bank Details",
                document_type=DocumentTypeEnum.INVOICE,
                coordinates=(50, 300, 550, 450),
                similarity_threshold=0.98,
                priority="critical",
                description="Bank account and routing information"
            ),
            ProtectedZone(
                zone_id="totals",
                zone_name="Totals Section",
                document_type=DocumentTypeEnum.INVOICE,
                coordinates=(400, 500, 550, 600),
                similarity_threshold=0.97,
                priority="critical",
                description="Invoice total amounts"
            ),
            ProtectedZone(
                zone_id="dates",
                zone_name="Invoice Date",
                document_type=DocumentTypeEnum.INVOICE,
                coordinates=(50, 50, 200, 100),
                similarity_threshold=0.95,
                priority="high",
                description="Invoice date and number"
            ),
        ]
        configs[DocumentTypeEnum.INVOICE] = DocumentTypeConfig(
            document_type=DocumentTypeEnum.INVOICE,
            protected_zones=invoice_zones,
            similarity_threshold=0.95,
            ela_sensitivity=0.7,
            description="Invoice document with bank details and amount zones"
        )
        
        # ===== CONTRACT =====
        contract_zones = [
            ProtectedZone(
                zone_id="signature_block",
                zone_name="Signature Block",
                document_type=DocumentTypeEnum.CONTRACT,
                coordinates=(50, 700, 550, 850),
                similarity_threshold=0.99,
                priority="critical",
                description="Signature block area"
            ),
            ProtectedZone(
                zone_id="party_names",
                zone_name="Party Names",
                document_type=DocumentTypeEnum.CONTRACT,
                coordinates=(50, 50, 550, 150),
                similarity_threshold=0.97,
                priority="critical",
                description="Contracting parties identification"
            ),
            ProtectedZone(
                zone_id="terms",
                zone_name="Terms and Conditions",
                document_type=DocumentTypeEnum.CONTRACT,
                coordinates=(50, 200, 550, 600),
                similarity_threshold=0.95,
                priority="high",
                description="Contract terms section"
            ),
        ]
        configs[DocumentTypeEnum.CONTRACT] = DocumentTypeConfig(
            document_type=DocumentTypeEnum.CONTRACT,
            protected_zones=contract_zones,
            similarity_threshold=0.95,
            ela_sensitivity=0.8,
            description="Contract document with signature and party name zones"
        )
        
        # ===== ID_CARD =====
        id_card_zones = [
            ProtectedZone(
                zone_id="photo",
                zone_name="Photo",
                document_type=DocumentTypeEnum.ID_CARD,
                coordinates=(20, 40, 120, 160),
                similarity_threshold=0.98,
                priority="critical",
                description="Person identification photo"
            ),
            ProtectedZone(
                zone_id="id_number",
                zone_name="ID Number",
                document_type=DocumentTypeEnum.ID_CARD,
                coordinates=(130, 40, 250, 80),
                similarity_threshold=0.99,
                priority="critical",
                description="Unique identification number"
            ),
            ProtectedZone(
                zone_id="expiry_date",
                zone_name="Expiry Date",
                document_type=DocumentTypeEnum.ID_CARD,
                coordinates=(130, 150, 250, 170),
                similarity_threshold=0.96,
                priority="high",
                description="ID expiry date"
            ),
        ]
        configs[DocumentTypeEnum.ID_CARD] = DocumentTypeConfig(
            document_type=DocumentTypeEnum.ID_CARD,
            protected_zones=id_card_zones,
            similarity_threshold=0.96,
            ela_sensitivity=0.75,
            description="ID Card with photo, number, and date zones"
        )
        
        # ===== CHECK =====
        check_zones = [
            ProtectedZone(
                zone_id="signature",
                zone_name="Signature",
                document_type=DocumentTypeEnum.CHECK,
                coordinates=(350, 150, 550, 200),
                similarity_threshold=0.99,
                priority="critical",
                description="Signed authorization area"
            ),
            ProtectedZone(
                zone_id="amount",
                zone_name="Amount Field",
                document_type=DocumentTypeEnum.CHECK,
                coordinates=(350, 90, 550, 130),
                similarity_threshold=0.97,
                priority="critical",
                description="Check amount in numbers"
            ),
            ProtectedZone(
                zone_id="date_check",
                zone_name="Check Date",
                document_type=DocumentTypeEnum.CHECK,
                coordinates=(50, 50, 200, 100),
                similarity_threshold=0.96,
                priority="high",
                description="Check issue date"
            ),
        ]
        configs[DocumentTypeEnum.CHECK] = DocumentTypeConfig(
            document_type=DocumentTypeEnum.CHECK,
            protected_zones=check_zones,
            similarity_threshold=0.96,
            ela_sensitivity=0.8,
            description="Check with signature and amount zones"
        )
        
        return configs
    
    def get_document_type_config(self, doc_type: str) -> DocumentTypeConfig:
        """Retrieve configuration for a document type."""
        doc_enum = DocumentTypeEnum(doc_type)
        if doc_enum not in self.type_configs:
            raise ValueError(f"Unknown document type: {doc_type}")
        return self.type_configs[doc_enum]
    
    def get_protected_zones(self, doc_type: str) -> List[ProtectedZone]:
        """Get all protected zones for a document type."""
        config = self.get_document_type_config(doc_type)
        return config.protected_zones
    
    def get_similarity_threshold(self, doc_type: str) -> float:
        """Get similarity threshold for document type."""
        config = self.get_document_type_config(doc_type)
        return config.similarity_threshold


# ============================================================================
# 2. REFERENCE TEMPLATE MANAGER
# ============================================================================

class ReferenceTemplateManager:
    """Manages retrieval and caching of reference templates."""
    
    def __init__(self):
        self.template_cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        self.template_metadata: Dict[str, Dict[str, Any]] = {}
    
    def fetch_template(self, document_type: str, from_db: Optional[Any] = None) -> np.ndarray:
        """
        Fetch reference template from cache or database.
        
        Args:
            document_type: Type of document
            from_db: Optional database connection/loader function
            
        Returns:
            Template image as numpy array
        """
        # Check cache first
        if document_type in self.template_cache:
            return self.template_cache[document_type][0]
        
        # Load from database (mock implementation)
        template_image = self._load_template_from_db(document_type, from_db)
        
        # Extract features and cache
        features = self.extract_template_features(template_image)
        self.template_cache[document_type] = (template_image, features)
        
        return template_image
    
    def _load_template_from_db(self, document_type: str, db_loader: Optional[Any] = None) -> np.ndarray:
        """Load template from database (mock implementation)."""
        # In production, this would query the database for the reference template
        # For now, return a placeholder
        return np.zeros((800, 600, 3), dtype=np.uint8)
    
    def extract_template_features(self, template_image: np.ndarray) -> np.ndarray:
        """Extract features from template image."""
        # Normalize and prepare
        if len(template_image.shape) == 2:
            template_image = cv2.cvtColor(template_image, cv2.COLOR_GRAY2RGB)
        
        # Resize to standard size
        template_resized = cv2.resize(template_image, (224, 224))
        
        # Normalize to [0, 1]
        template_normalized = template_resized.astype(np.float32) / 255.0
        
        return template_normalized
    
    def validate_template(self, template: np.ndarray) -> bool:
        """Validate template integrity and format."""
        if template is None:
            return False
        if not isinstance(template, np.ndarray):
            return False
        if template.size == 0:
            return False
        if len(template.shape) not in [2, 3]:
            return False
        return True
    
    def update_template(self, doc_type: str, new_template: np.ndarray, version: str = "1.0"):
        """Update template with version tracking."""
        if not self.validate_template(new_template):
            raise ValueError("Invalid template")
        
        # Clear cache for this type
        if doc_type in self.template_cache:
            del self.template_cache[doc_type]
        
        # Update metadata
        self.template_metadata[doc_type] = {
            "version": version,
            "updated_at": datetime.now().isoformat(),
            "hash": hashlib.md5(new_template.tobytes()).hexdigest()
        }


# ============================================================================
# 3. SIAMESE NETWORK COMPARATOR
# ============================================================================

class SiameseNetworkComparator:
    """Siamese neural network for document comparison."""
    
    def __init__(self, input_shape: Tuple[int, int, int] = (224, 224, 3)):
        self.input_shape = input_shape
        self.model = self._build_siamese_model()
    
    def _build_siamese_model(self) -> keras.Model:
        """Build Siamese network architecture."""
        input_a = keras.Input(shape=self.input_shape, name="input_reference")
        input_b = keras.Input(shape=self.input_shape, name="input_received")
        
        # Shared CNN backbone
        backbone = self._build_backbone()
        
        # Process both inputs through same backbone
        features_a = backbone(input_a)
        features_b = backbone(input_b)
        
        # Distance computation (Euclidean)
        distance = layers.Lambda(
            lambda x: tf.sqrt(tf.reduce_sum(tf.square(x[0] - x[1]), axis=-1, keepdims=True))
        )([features_a, features_b])
        
        # Similarity output (inverse of distance)
        similarity = layers.Lambda(
            lambda x: 1.0 / (1.0 + x),
            name="similarity"
        )(distance)
        
        model = keras.Model(
            inputs=[input_a, input_b],
            outputs=similarity,
            name="siamese_network"
        )
        
        return model
    
    def _build_backbone(self) -> keras.Model:
        """Build CNN backbone for feature extraction."""
        model = keras.Sequential([
            layers.Conv2D(64, (3, 3), padding='same', activation='relu'),
            layers.MaxPooling2D((2, 2)),
            layers.Conv2D(128, (3, 3), padding='same', activation='relu'),
            layers.MaxPooling2D((2, 2)),
            layers.Conv2D(256, (3, 3), padding='same', activation='relu'),
            layers.MaxPooling2D((2, 2)),
            layers.GlobalAveragePooling2D(),
            layers.Dense(512, activation='relu'),
            layers.Dropout(0.5),
        ], name="feature_backbone")
        
        return model
    
    def compare_documents(
        self,
        reference_image: np.ndarray,
        received_image: np.ndarray
    ) -> Tuple[float, np.ndarray, np.ndarray]:
        """
        Compare reference and received documents.
        
        Returns:
            similarity_score: 0-1 confidence
            reference_features: Feature map from reference
            received_features: Feature map from received
        """
        # Preprocess images
        ref_processed = self._preprocess_image(reference_image)
        rec_processed = self._preprocess_image(received_image)
        
        # Get similarity score
        similarity_score = float(self.model.predict([ref_processed, rec_processed])[0][0])
        
        # Extract feature maps (from backbone)
        backbone_model = keras.Model(
            inputs=self.model.input,
            outputs=self.model.layers[2].output  # Output of backbone
        )
        
        ref_features = backbone_model.predict(ref_processed)[0]
        rec_features = backbone_model.predict(rec_processed)[0]
        
        return similarity_score, ref_features, rec_features
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """Preprocess image for model input."""
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Resize to model input shape
        image = cv2.resize(image, (self.input_shape[0], self.input_shape[1]))
        
        # Normalize to [0, 1]
        image = image.astype(np.float32) / 255.0
        
        # Add batch dimension
        image = np.expand_dims(image, axis=0)
        
        return image
    
    def extract_dense_features(self, image: np.ndarray) -> np.ndarray:
        """Extract 512-dim embedding from image."""
        processed = self._preprocess_image(image)
        
        # Use backbone to get features
        backbone_model = keras.Model(
            inputs=self.model.get_layer("feature_backbone").input,
            outputs=self.model.get_layer("feature_backbone").output
        )
        
        features = backbone_model.predict(processed)[0]
        return features


# ============================================================================
# 4. PIXEL-LEVEL ELA ANALYZER
# ============================================================================

class PixelLevelELAAnalyzer:
    """Error Level Analysis for compression and pixel-level anomalies."""
    
    def __init__(self, quality_range: range = range(70, 101)):
        self.quality_range = quality_range
    
    def compute_error_level_analysis(
        self,
        image: np.ndarray,
        reference_image: Optional[np.ndarray] = None
    ) -> Tuple[float, List[Dict[str, Any]], np.ndarray]:
        """
        Compute Error Level Analysis (ELA).
        
        Returns:
            ela_score: 0-1 anomaly score
            anomaly_regions: List of detected anomalies with coordinates
            heatmap: ELA visualization
        """
        # Convert to RGB if needed
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB)
        
        # Find optimal quality level where differences appear
        ela_heatmap = self._compute_ela_heatmap(image)
        
        # Normalize heatmap to [0, 1]
        ela_heatmap_normalized = ela_heatmap / (np.max(ela_heatmap) + 1e-8)
        ela_score = float(np.mean(ela_heatmap_normalized))
        
        # Detect anomalous regions
        anomaly_regions = self._identify_edited_regions(ela_heatmap_normalized)
        
        return ela_score, anomaly_regions, ela_heatmap
    
    def _compute_ela_heatmap(self, image: np.ndarray) -> np.ndarray:
        """Compute ELA heatmap by testing different compression levels."""
        # Start with original image
        original_height, original_width = image.shape[:2]
        
        # Save at lower quality and reload to detect re-compression
        encoded_quality_90 = cv2.imencode('.jpg', image, [cv2.IMWRITE_JPEG_QUALITY, 90])[1]
        compressed_90 = cv2.imdecode(encoded_quality_90, cv2.IMREAD_COLOR)
        
        # Resize back to original if needed
        if compressed_90.shape[:2] != image.shape[:2]:
            compressed_90 = cv2.resize(compressed_90, (original_width, original_height))
        
        # Compute difference (error level)
        image_float = image.astype(np.float32)
        compressed_float = compressed_90.astype(np.float32)
        
        error_level = np.abs(image_float - compressed_float)
        
        # Convert to grayscale for heatmap
        error_gray = cv2.cvtColor(error_level.astype(np.uint8), cv2.COLOR_BGR2GRAY)
        
        return error_gray
    
    def _identify_edited_regions(
        self,
        ela_heatmap: np.ndarray,
        threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """Identify edited regions from ELA heatmap."""
        anomalies = []
        
        # Threshold to binary
        _, binary = cv2.threshold(
            (ela_heatmap * 255).astype(np.uint8),
            int(255 * threshold),
            255,
            cv2.THRESH_BINARY
        )
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Extract anomaly regions
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            area = cv2.contourArea(contour)
            
            if area > 100:  # Filter small noise
                anomalies.append({
                    "coordinates": (x, y, x + w, y + h),
                    "area": float(area),
                    "anomaly_score": float(np.mean(ela_heatmap[y:y+h, x:x+w]))
                })
        
        return anomalies
    
    def analyze_jpeg_artifacts(self, image: np.ndarray) -> float:
        """Detect JPEG recompression patterns."""
        # Convert to DCT-based analysis if JPEG
        # This is a simplified approach
        
        # Compute DCT blocks
        h, w = image.shape[:2]
        
        # Analyze 8x8 blocks for JPEG artifacts
        block_size = 8
        artifact_score = 0.0
        block_count = 0
        
        for y in range(0, h - block_size, block_size):
            for x in range(0, w - block_size, block_size):
                block = image[y:y+block_size, x:x+block_size].astype(np.float32)
                
                # Compute variance (JPEG blocking creates artificial uniformity)
                variance = np.var(block)
                if variance < 5.0:  # Suspicious uniformity
                    artifact_score += 1.0
                
                block_count += 1
        
        return artifact_score / (block_count + 1e-8)


# ============================================================================
# 5. STRUCTURAL ALIGNMENT ANALYZER
# ============================================================================

class StructuralAlignmentAnalyzer:
    """Detects structural changes (text block movement, resizing)."""
    
    def __init__(self):
        self.orb = cv2.ORB_create()
    
    def detect_text_blocks(self, image: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detect text regions using contours."""
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Threshold
        _, binary = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        text_blocks = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            
            # Filter by size (text blocks)
            if 50 < w * h < 100000:
                text_blocks.append((x, y, x + w, y + h))
        
        return text_blocks
    
    def extract_geometric_features(
        self,
        reference_image: np.ndarray,
        received_image: np.ndarray
    ) -> Tuple[List[Dict], List[Dict]]:
        """Extract geometric features from both images."""
        ref_blocks = self.detect_text_blocks(reference_image)
        rec_blocks = self.detect_text_blocks(received_image)
        
        ref_features = [
            {
                "coordinates": block,
                "area": (block[2] - block[0]) * (block[3] - block[1]),
                "center": ((block[0] + block[2]) / 2, (block[1] + block[3]) / 2)
            }
            for block in ref_blocks
        ]
        
        rec_features = [
            {
                "coordinates": block,
                "area": (block[2] - block[0]) * (block[3] - block[1]),
                "center": ((block[0] + block[2]) / 2, (block[1] + block[3]) / 2)
            }
            for block in rec_blocks
        ]
        
        return ref_features, rec_features
    
    def compare_geometric_alignment(
        self,
        reference_features: List[Dict],
        received_features: List[Dict],
        tolerance: float = 0.1
    ) -> Tuple[float, List[str], List[str]]:
        """Compare geometric alignment between reference and received."""
        moved_blocks = []
        resized_blocks = []
        
        # Simple matching based on area
        for i, ref_feat in enumerate(reference_features):
            if i < len(received_features):
                rec_feat = received_features[i]
                
                # Check position change
                ref_center = ref_feat["center"]
                rec_center = rec_feat["center"]
                
                position_diff = np.sqrt(
                    (ref_center[0] - rec_center[0]) ** 2 +
                    (ref_center[1] - rec_center[1]) ** 2
                )
                
                if position_diff > 50:  # Threshold
                    moved_blocks.append(f"block_{i}")
                
                # Check size change
                ref_area = ref_feat["area"]
                rec_area = rec_feat["area"]
                
                size_ratio = rec_area / (ref_area + 1e-8)
                if size_ratio < (1 - tolerance) or size_ratio > (1 + tolerance):
                    resized_blocks.append(f"block_{i}")
        
        # Compute alignment score (0-1, higher is better)
        alignment_score = 1.0 - (len(moved_blocks) + len(resized_blocks)) / (
            len(reference_features) + 1e-8
        )
        
        return alignment_score, moved_blocks, resized_blocks
    
    def compute_structural_similarity(
        self,
        reference_image: np.ndarray,
        received_image: np.ndarray
    ) -> float:
        """Compute structural similarity (SSIM-like metric)."""
        # Resize to same dimensions
        h, w = reference_image.shape[:2]
        received_resized = cv2.resize(received_image, (w, h))
        
        # Convert to grayscale
        if len(reference_image.shape) == 3:
            ref_gray = cv2.cvtColor(reference_image, cv2.COLOR_BGR2GRAY)
        else:
            ref_gray = reference_image
        
        if len(received_resized.shape) == 3:
            rec_gray = cv2.cvtColor(received_resized, cv2.COLOR_BGR2GRAY)
        else:
            rec_gray = received_resized
        
        # Compute mean squared error (MSE)
        mse = np.mean((ref_gray.astype(np.float32) - rec_gray.astype(np.float32)) ** 2)
        
        # Convert to similarity (0-1)
        # Higher MSE = lower similarity
        similarity = np.exp(-mse / 10000.0)
        
        return float(similarity)


# ============================================================================
# 6. ZONE-BASED VALIDATOR
# ============================================================================

class ZoneBasedValidator:
    """Validates protected zones with document-type-specific rules."""
    
    def validate_protected_zones(
        self,
        zones: List[ProtectedZone],
        similarity_matrix: np.ndarray,
        image_shape: Tuple[int, int]
    ) -> List[Dict[str, Any]]:
        """
        Validate all protected zones.
        
        Returns:
            List of zone violations
        """
        violations = []
        
        for zone in zones:
            x1, y1, x2, y2 = zone.coordinates
            
            # Extract zone from similarity matrix
            # Resize if needed
            if similarity_matrix.shape != image_shape:
                zone_similarity = self._extract_zone_similarity(
                    similarity_matrix, zone.coordinates, image_shape
                )
            else:
                zone_similarity = similarity_matrix[y1:y2, x1:x2]
            
            # Compute average similarity in zone
            zone_avg_similarity = float(np.mean(zone_similarity))
            
            # Check threshold
            if zone_avg_similarity < zone.similarity_threshold:
                violations.append({
                    "zone_id": zone.zone_id,
                    "zone_name": zone.zone_name,
                    "priority": zone.priority,
                    "threshold": zone.similarity_threshold,
                    "actual_similarity": zone_avg_similarity,
                    "coordinates": zone.coordinates,
                    "violation_severity": self._compute_violation_severity(
                        zone_avg_similarity, zone.similarity_threshold
                    )
                })
        
        return violations
    
    def _extract_zone_similarity(
        self,
        similarity_matrix: np.ndarray,
        coordinates: Tuple[int, int, int, int],
        target_shape: Tuple[int, int]
    ) -> np.ndarray:
        """Extract zone from similarity matrix with proper scaling."""
        h, w = target_shape
        
        # Scale coordinates to matrix dimensions
        scale_x = similarity_matrix.shape[1] / w
        scale_y = similarity_matrix.shape[0] / h
        
        x1, y1, x2, y2 = coordinates
        x1_scaled = int(x1 * scale_x)
        y1_scaled = int(y1 * scale_y)
        x2_scaled = int(x2 * scale_x)
        y2_scaled = int(y2 * scale_y)
        
        return similarity_matrix[y1_scaled:y2_scaled, x1_scaled:x2_scaled]
    
    def _compute_violation_severity(
        self,
        actual: float,
        threshold: float
    ) -> str:
        """Compute severity of violation."""
        diff = threshold - actual
        
        if diff > 0.10:
            return "critical"
        elif diff > 0.05:
            return "high"
        elif diff > 0.02:
            return "medium"
        else:
            return "low"
    
    def generate_zone_heatmap(
        self,
        image: np.ndarray,
        violations: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Generate heatmap highlighting violated zones."""
        heatmap = image.copy().astype(np.float32)
        
        # Red overlay for violations
        red_overlay = np.zeros_like(heatmap)
        red_overlay[:, :, 2] = 255  # Red channel
        
        for violation in violations:
            x1, y1, x2, y2 = violation["coordinates"]
            severity = violation["violation_severity"]
            
            # Set alpha based on severity
            alpha_map = {
                "critical": 0.7,
                "high": 0.5,
                "medium": 0.3,
                "low": 0.1
            }
            
            alpha = alpha_map.get(severity, 0.3)
            
            # Blend overlay
            heatmap[y1:y2, x1:x2] = (
                heatmap[y1:y2, x1:x2] * (1 - alpha) +
                red_overlay[y1:y2, x1:x2] * alpha
            )
        
        return heatmap.astype(np.uint8)


# ============================================================================
# 7. ALERT ENGINE
# ============================================================================

class AlertEngine:
    """Generates fraud alerts and notifications."""
    
    def trigger_fraud_alert(
        self,
        forensic_result: ForensicResult,
        violations: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate fraud alert based on violations."""
        # Determine severity
        if not violations:
            severity = AlertSeverity.CLEAN
        else:
            critical_violations = [v for v in violations if v["priority"] == "critical"]
            if critical_violations:
                severity = AlertSeverity.CRITICAL
            else:
                high_violations = [v for v in violations if v["priority"] == "high"]
                severity = AlertSeverity.HIGH if high_violations else AlertSeverity.MEDIUM
        
        alert = {
            "alert_id": hashlib.md5(str(datetime.now()).encode()).hexdigest(),
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "violations": violations,
            "forensic_summary": {
                "overall_similarity": forensic_result.overall_similarity,
                "ela_score": forensic_result.ela_score,
                "structural_alignment": forensic_result.structural_alignment_score
            }
        }
        
        return alert
    
    def generate_forensic_heatmap(
        self,
        image: np.ndarray,
        violations: List[Dict[str, Any]],
        ela_heatmap: Optional[np.ndarray] = None,
        structural_heatmap: Optional[np.ndarray] = None
    ) -> np.ndarray:
        """Generate multi-layer forensic heatmap."""
        result_image = image.copy().astype(np.float32)
        
        # Layer 1: Zone violations (red)
        zone_heatmap = np.zeros_like(result_image)
        zone_heatmap[:, :, 2] = 255  # Red channel
        
        for violation in violations:
            x1, y1, x2, y2 = violation["coordinates"]
            alpha = 0.5 if violation["priority"] == "critical" else 0.3
            result_image[y1:y2, x1:x2] = (
                result_image[y1:y2, x1:x2] * (1 - alpha) +
                zone_heatmap[y1:y2, x1:x2] * alpha
            )
        
        # Layer 2: ELA anomalies (yellow)
        if ela_heatmap is not None:
            ela_normalized = (ela_heatmap / (np.max(ela_heatmap) + 1e-8) * 255).astype(np.uint8)
            ela_binary = cv2.threshold(ela_normalized, 50, 255, cv2.THRESH_BINARY)[1]
            
            ela_color = np.zeros_like(result_image)
            ela_color[:, :, 1:3] = 255  # Yellow
            
            for y in range(ela_binary.shape[0]):
                for x in range(ela_binary.shape[1]):
                    if ela_binary[y, x] > 0:
                        result_image[y, x] = (
                            result_image[y, x] * 0.7 + ela_color[y, x] * 0.3
                        )
        
        return result_image.astype(np.uint8)
    
    def create_forensic_report(
        self,
        forensic_result: ForensicResult,
        alert: Dict[str, Any]
    ) -> str:
        """Create comprehensive text forensic report."""
        report = f"""
========== FORENSIC ANALYSIS REPORT ==========

Document Type: {forensic_result.document_type}
Analysis Timestamp: {forensic_result.timestamp}

OVERALL METRICS:
  Overall Similarity Score: {forensic_result.overall_similarity:.2%}
  ELA Anomaly Score: {forensic_result.ela_score:.2%}
  Structural Alignment Score: {forensic_result.structural_alignment_score:.2%}
  Siamese Network Confidence: {forensic_result.siamese_confidence:.2%}

ALERT INFORMATION:
  Alert Severity: {alert['severity']}
  Alert ID: {alert['alert_id']}
  
ZONE VIOLATIONS ({len(alert['violations'])} detected):
"""
        for i, violation in enumerate(alert["violations"], 1):
            report += f"""
  [{i}] {violation['zone_name']}
      Zone ID: {violation['zone_id']}
      Priority: {violation['priority']}
      Similarity: {violation['actual_similarity']:.2%} (Threshold: {violation['threshold']:.2%})
      Violation Severity: {violation['violation_severity']}
      Location: {violation['coordinates']}
"""
        
        report += "\n========== END OF REPORT ==========\n"
        return report


# ============================================================================
# 8. MAIN DOCUMENT POLICE EVALUATOR
# ============================================================================

class DocumentPoliceEvaluator:
    """
    Main orchestrator for Context-Aware Document Police System.
    
    Integrates all components: DocumentTypeMapper, ReferenceTemplateManager,
    SiameseNetworkComparator, PixelLevelELAAnalyzer, StructuralAlignmentAnalyzer,
    ZoneBasedValidator, and AlertEngine.
    """
    
    def __init__(self):
        self.document_type_mapper = DocumentTypeMapper()
        self.reference_template_manager = ReferenceTemplateManager()
        self.siamese_comparator = SiameseNetworkComparator()
        self.ela_analyzer = PixelLevelELAAnalyzer()
        self.structural_analyzer = StructuralAlignmentAnalyzer()
        self.zone_validator = ZoneBasedValidator()
        self.alert_engine = AlertEngine()
    
    def evaluate_document(
        self,
        document_path: str,
        document_type: str,
        reference_template_path: Optional[str] = None
    ) -> ForensicResult:
        """
        Main evaluation pipeline.
        
        Args:
            document_path: Path to document to analyze
            document_type: Type of document (Invoice, Contract, etc.)
            reference_template_path: Optional explicit path to reference template
            
        Returns:
            Complete ForensicResult with all analysis data
        """
        # Load document
        received_image = cv2.imread(document_path)
        if received_image is None:
            raise FileNotFoundError(f"Document not found: {document_path}")
        
        # Retrieve reference template
        if reference_template_path:
            reference_image = cv2.imread(reference_template_path)
        else:
            reference_image = self.reference_template_manager.fetch_template(document_type)
        
        # Get document type configuration
        doc_config = self.document_type_mapper.get_document_type_config(document_type)
        
        # Execute forensic pipeline
        result = self._execute_forensic_pipeline(
            received_image, reference_image, document_type, doc_config
        )
        
        return result
    
    def _execute_forensic_pipeline(
        self,
        received_image: np.ndarray,
        reference_image: np.ndarray,
        document_type: str,
        doc_config: DocumentTypeConfig
    ) -> ForensicResult:
        """Execute complete forensic analysis pipeline."""
        
        # Step 1: Siamese Network Comparison
        siamese_similarity, ref_features, rec_features = self.siamese_comparator.compare_documents(
            reference_image, received_image
        )
        
        # Step 2: Pixel-Level ELA Analysis
        ela_score, ela_anomalies, ela_heatmap = self.ela_analyzer.compute_error_level_analysis(
            received_image, reference_image
        )
        
        # Step 3: Structural Alignment Analysis
        ref_geom_features, rec_geom_features = self.structural_analyzer.extract_geometric_features(
            reference_image, received_image
        )
        
        alignment_score, moved_blocks, resized_blocks = (
            self.structural_analyzer.compare_geometric_alignment(
                ref_geom_features, rec_geom_features, doc_config.structural_tolerance
            )
        )
        
        # Step 4: Zone-Based Validation
        # Create similarity matrix for zone validation
        h, w = received_image.shape[:2]
        similarity_matrix = np.ones((h, w)) * siamese_similarity
        
        zone_violations = self.zone_validator.validate_protected_zones(
            doc_config.protected_zones, similarity_matrix, (h, w)
        )
        
        # Step 5: Alert Generation
        forensic_result = ForensicResult(
            document_id=hashlib.md5(str(datetime.now()).encode()).hexdigest(),
            document_type=document_type,
            overall_similarity=siamese_similarity,
            ela_score=ela_score,
            structural_alignment_score=alignment_score,
            siamese_confidence=siamese_similarity,
            zone_violations=zone_violations,
            anomaly_regions=ela_anomalies,
            timestamp=datetime.now().isoformat()
        )
        
        # Determine alert severity
        alert = self.alert_engine.trigger_fraud_alert(forensic_result, zone_violations)
        forensic_result.alert_severity = alert["severity"]
        
        # Generate heatmaps
        zone_heatmap = self.zone_validator.generate_zone_heatmap(received_image, zone_violations)
        forensic_heatmap = self.alert_engine.generate_forensic_heatmap(
            received_image, zone_violations, ela_heatmap
        )
        
        # Convert heatmaps to base64
        forensic_result.heatmap_b64 = self._image_to_base64(forensic_heatmap)
        forensic_result.zone_violations_b64 = self._image_to_base64(zone_heatmap)
        forensic_result.ela_heatmap_b64 = self._image_to_base64(
            (ela_heatmap * 255).astype(np.uint8)
        )
        
        # Generate text report
        forensic_result.forensic_report = self.alert_engine.create_forensic_report(
            forensic_result, alert
        )
        
        return forensic_result
    
    def _image_to_base64(self, image: np.ndarray) -> str:
        """Convert image to base64 string."""
        _, buffer = cv2.imencode('.png', image)
        base64_image = base64.b64encode(buffer).decode('utf-8')
        return base64_image
    
    def retrieve_reference_template(self, document_type: str) -> np.ndarray:
        """Public method to retrieve reference template."""
        return self.reference_template_manager.fetch_template(document_type)
    
    def get_document_type_info(self, document_type: str) -> Dict[str, Any]:
        """Get configuration info for a document type."""
        config = self.document_type_mapper.get_document_type_config(document_type)
        zones_info = [
            {
                "zone_id": zone.zone_id,
                "zone_name": zone.zone_name,
                "coordinates": zone.coordinates,
                "similarity_threshold": zone.similarity_threshold,
                "priority": zone.priority
            }
            for zone in config.protected_zones
        ]
        
        return {
            "document_type": document_type,
            "description": config.description,
            "overall_threshold": config.similarity_threshold,
            "protected_zones": zones_info,
            "ela_sensitivity": config.ela_sensitivity
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    # Initialize evaluator
    evaluator = DocumentPoliceEvaluator()
    
    # Example: Analyze an invoice
    print("Document Police Evaluator - Example Usage\n")
    
    # Get document type information
    invoice_info = evaluator.get_document_type_info("Invoice")
    print("Invoice Configuration:")
    print(json.dumps(invoice_info, indent=2))
    
    # In production, you would call:
    # result = evaluator.evaluate_document(
    #     document_path="uploads/invoice.jpg",
    #     document_type="Invoice"
    # )
    # print(f"\nForensic Report:\n{result.forensic_report}")
