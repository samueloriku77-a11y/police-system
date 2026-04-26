# Document Forgery Detection System - Complete Technical Documentation

## Architecture Overview

```
Client (Browser)
    ↓ AJAX Upload
Flask App (app.py)
    ├── Preprocessing (preprocessing.py)
    ├── Feature Extraction (feature_extraction.py)
    ├── Similarity Analysis (similarity.py)
    └── Database (db.py)
        ├── Users
        ├── VerificationResults  
        ├── ReferenceDocuments
        └── AuditLog
```

## Core Classes & Attributes

### 1. FeatureExtractor (feature_extraction.py)
```
Attributes:
├── model (MobileNetV2): Similarity embedding model (512-dim)
├── preprocessor: Image preprocessing
├── TRAINING_EMBEDDING_DIM = 1280
└── FEATURE_EMBEDDING_DIM = 512

Methods:
├── extract_features(path): Returns 512-dim embedding
├── _load_similarity_model(): Loads local model
├── _build_similarity_model(): Builds if model missing
└── batch_extract_features(): Processes multiple images
```

### 2. ForgeryDetector (feature_extraction.py)
```
Attributes:
├── model_path: 'models/aether_forgery_model.h5'
└── model: Forgery classification model

Methods:
├── detect_forged_regions(path): Returns forged_ratio, regions, heatmap
├── predict_whole_document(path): Returns is_forged, confidence, forged_prob
└── _build_forgery_model(): EfficientNetV2S + feature channels
```

### 3. SimilarityCalculator (similarity.py)
```
Attributes:
├── ssim_threshold = 0.85
├── euclidean_threshold = 0.85
├── cosine_threshold = 0.80
└── weights: {'ssim': 0.3, 'euclidean': 0.3, 'cosine': 0.4}

Methods:
├── calculate_ssim(): Structural similarity
├── calculate_euclidean_similarity(): Normalized Euclidean
├── calculate_cosine_similarity(): Cosine similarity
├── calculate_block_similarity(): 64x64 block heatmap
├── classify_document(similarity): AUTHENTIC/UNCERTAIN/FORGED
└── compare_with_references(): Best DB match
```

### 4. ImagePreprocessor (preprocessing.py)
```
Methods:
├── preprocess_document(): Full pipeline
├── denoise_image(): Non-local means denoising
├── enhance_contrast(): CLAHE contrast
├── extract_edges(): Canny + Sobel
└── normalize_pixels(): 0-1 normalization
```

### 5. Database Models (db.py)
```
User:
├── id (PK)
├── username
├── email (UNIQUE)
├── password_hash
├── is_admin (Boolean)
└── verification_results (relationship)

VerificationResult:
├── id (PK)
├── user_id (FK)
├── filename
├── similarity (Float)
├── status (String)
├── flagged (Boolean)
└── timestamp

ReferenceDocument:
├── id (PK)
├── name
├── file_path
└── embedding_data (BLOB)

AuditLog:
├── id (PK)
├── user_id (FK)
├── action
├── details
└── timestamp
```

## Flask Routes (app.py)

```
Authentication:
├── GET/POST /login
├── GET/POST /register  
├── GET /logout

Analysis:
├── POST /detect - Main analysis endpoint
├── GET /scan/progress - Progress simulation
├── POST /preprocess - Image preprocessing
├── POST /heatmap - Block similarity heatmap

Admin:
├── GET /admin - Dashboard
├── POST /admin/upload-original - Add reference
├── POST /admin/delete-original/:id - Remove reference
├── GET /history - Admin history page
├── POST /flag/:id - Flag result
├── POST /unflag/:id - Unflag result
└── GET /report/:id - Detailed report
```

## Analysis Pipeline

1. **Upload** → Validation (size/format)
2. **Preprocessing** → Grayscale + Denoise + Contrast
3. **Feature Extraction** → MobileNetV2 (512-dim)
4. **Reference Matching** → Cosine similarity to DB
5. **Forgery Detection** → aether_forgery_model.h5 
6. **Block Analysis** → 64x64 similarity heatmap
7. **Classification** → FORGED (0.3+), AUTHENTIC (<0.3)
8. **Visualization** → Forgery heatmap + regions
9. **Database Storage** → Result + audit log
10. **Response** → JSON with b64 heatmaps

## Model Architecture

**Similarity Model (feature_extraction.py):**
```
Input: 224x224x3 RGB
↓
EfficientNetB0 (pretrained=False)
↓
GlobalAvgPool2D
↓
Dropout(0.3)
↓
Dense(512)
Output: 512-dim embedding
```

**Forgery Model (aether_forgery_model.h5):**
```
Input: 224x224x8 (RGB + 5 edge features)
↓
Conv2D(32) + BatchNorm
↓
Conv2D(3, sigmoid)
↓
EfficientNetV2S
↓
GlobalAvgPool2D + Dropout(0.5)
↓
Dense(1, sigmoid)
Output: Forgery probability [0,1]
```

## Deployment

```
python app.py  # Development
gunicorn -w 4 app:app  # Production

Environment Variables:
├── DB_USER=root
├── DB_PASSWORD=your_password
├── DB_HOST=localhost
├── DB_PORT=3306
└── DB_NAME=document_forgery_db
```

## Testing

```bash
python tests.py
# or
pytest -v --cov
```

**Tests Include:**
- Preprocessing pipeline
- Feature extraction
- Similarity metrics
- Classification logic
- Database operations
- End-to-end workflow

## Usage Flow

1. Login (admin@example.com/admin123)
2. Upload ID image
3. View:
   - Status: FORGED/AUTHENTIC
   - Forged ratio % bar
   - Document type
   - Forgery heatmap (red = suspicious)
   - Suspicious regions list
4. Admin → History table → Flag for review

System fully operational with loader animation during analysis.
