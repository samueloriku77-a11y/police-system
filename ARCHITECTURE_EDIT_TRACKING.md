# Document Edit Tracking System - Architecture

## High-Level Flow Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                  DOCUMENT UPLOAD FLOW                        │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐
│  User Uploads    │
│   Document       │
└────────┬─────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  /detect Endpoint                    │
│  - Save file                         │
│  - Extract features (embedding)      │
│  - Run forgery detection             │
└────────┬─────────────────────────────┘
         │
         ▼
┌──────────────────────────────────────┐
│  detect_document_edits()             │
│  (NEW)                               │
│  - Get org's protected documents     │
│  - Compare embeddings                │
│  - Calculate similarity              │
└────────┬─────────────────────────────┘
         │
         ├─ Similarity < 70% ──► Standard Analysis
         │
         └─ Similarity > 70% ──┐
                               │
                               ▼
                    ┌──────────────────┐
                    │ Generate Heatmap │
                    │ (OpenCV)         │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Log to Database  │
                    │ DocumentEditLog  │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Send Email Alert │
                    │ to Admin         │
                    └────────┬─────────┘
                             │
                             ▼
                    ┌──────────────────┐
                    │ Confirmation to  │
                    │ User             │
                    └──────────────────┘
```

---

## Database Schema Diagram

```
                        USERS TABLE
                    ┌───────────────┐
                    │ id (PK)       │
                    │ username      │
                    │ email         │
                    │ is_admin      │
                    │ organization  │
                    └───────────────┘
                          │
                  ┌───────┴───────┐
                  │               │
                  ▼               ▼
    ┌─────────────────────┐  ┌────────────────┐
    │ORG_REF_DOCUMENTS    │  │ DOCUMENT_EDIT  │
    ├─────────────────────┤  │ _LOGS          │
    │ id (PK)             │  ├────────────────┤
    │ org_name (INDEX)    │◄─┤ org_name       │
    │ document_name       │  │ ref_doc_id (FK)│
    │ file_path           │  │ uploader_id (FK)
    │ embedding_data      │  │ admin_notified │
    │ should_not_edit     │  │ timestamp      │
    │ description         │  │ heatmap_b64    │
    │ uploaded_by_id (FK) │  │ similarity     │
    │ created_at          │  │ changed_regions│
    └─────────────────────┘  └────────────────┘
```

---

## Component Architecture

```
┌────────────────────────────────────────────────────────┐
│                  WEB LAYER (Flask)                      │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Routes:                                              │
│  ├─ /admin/upload-org-reference      (Upload docs)   │
│  ├─ /admin/list-org-references       (List docs)     │
│  ├─ /admin/delete-org-reference/<id> (Delete doc)    │
│  ├─ /admin/org-references            (UI page)       │
│  ├─ /admin/edit-history              (Edit UI)       │
│  ├─ /admin/edit-details/<id>         (Detail view)   │
│  ├─ /api/compare-documents           (API)           │
│  └─ /api/edit-history                (API)           │
│                                                        │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│              LOGIC LAYER (Python)                       │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Main Functions:                                      │
│  ├─ detect_document_edits()      (Core logic)        │
│  ├─ send_edit_detection_email()  (Email)             │
│  ├─ compare_documents_api()      (API)               │
│                                                        │
│  Feature Extraction:                                  │
│  ├─ feature_extractor.extract_features()             │
│  ├─ OpenCV image operations                          │
│  ├─ Embedding similarity (cosine)                    │
│                                                        │
└────────────────────────────────────────────────────────┘
                           │
                           ▼
┌────────────────────────────────────────────────────────┐
│            DATA LAYER (Database)                        │
├────────────────────────────────────────────────────────┤
│                                                        │
│  Tables:                                              │
│  ├─ organizations                    (via users)      │
│  ├─ organization_reference_documents (Protected docs) │
│  ├─ document_edit_logs               (Edit history)   │
│  ├─ users                            (Audit trail)    │
│  └─ audit_logs                       (Logging)        │
│                                                        │
└────────────────────────────────────────────────────────┘
```

---

## Feature Extraction Using Data Flow

```
Original Upload Process:
    Document → Extract Features → Use for Forgery Detection
                        │
                        └──→ Feature stored (but not used)
                                    
NEW Edit Detection Process:
    Document → Extract Features ──┐
                        │          │
                        ▼          │
                   Forgery Check   │
                        │          │
                        ▼          ▼
              Organization Protected Docs ←─ Extract Features
                        │                           │
                        └──→ Compare Embeddings ◄──┘
                                    │
                                    ▼
                            Similarity Score (0-1)
                                    │
                        ┌───────────┴────────────┐
                        │                        │
                        ▼ (> 70%)               ▼ (< 70%)
                    EDIT DETECTED          Use normally
                        │
                        ▼
                  Generate Heatmap
                        │
                        ▼
                  Send Email Alert
                        │
                        ▼
                  Log to Database
```

---

## Similarity Calculation Process

```
Embedded Document A (512 dims)     Embedded Reference Doc B (512 dims)
    [0.23, 0.45, -0.12, ...]  ──►  Cosine Similarity  ◄── [0.24, 0.43, -0.10, ...]
                                    
                                        Formula:
                                    ─────────────────────
                                    A · B
                                    ──────────────
                                    |A| × |B|
                                    
                                    Result: 0.0 to 1.0
                                    
                                    └─► > 0.70 = EDIT DETECTED
```

---

## Email Alert Flow

```
Edit Detected
    │
    ▼
┌─────────────────────────────┐
│ Create Email Object         │
│ - Organization name         │
│ - Who uploaded              │
│ - Original filename         │
│ - Edited filename           │
│ - Similarity score          │
│ - Changed regions           │
│ - Heatmap image (base64)    │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Format HTML Email           │
│ - Professional template     │
│ - Color coded metrics       │
│ - Heatmap embedded          │
│ - Call to action            │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Send via SMTP               │
│ - Gmail                     │
│ - Office365                 │
│ - Custom SMTP               │
└────────────┬────────────────┘
             │
             ▼
┌─────────────────────────────┐
│ Log Success/Failure         │
│ Update database record      │
│ Set email_sent_to_admin     │
└─────────────────────────────┘
```

---

## User Interaction Diagram

```
═══════════════════════════════════════════════════════════════

ORGANIZATION ADMIN
    │
    ├─► /admin
    │       │
    │       ├─► "Manage Protected Documents" Button
    │       │       │
    │       │       └─► /admin/org-references
    │       │               │
    │       │               ├─ Upload documents
    │       │               ├─ View protected docs
    │       │               └─ Delete docs
    │       │
    │       └─► "View Edit History" Button
    │               │
    │               └─► /admin/edit-history
    │                       │
    │                       ├─ Table of all edits
    │                       ├─ Click "View"
    │                       │
    │                       └─ Modal shows:
    │                           ├─ Who (username, email)
    │                           ├─ What (original vs edited)
    │                           ├─ Score (similarity %)
    │                           ├─ Changes (regions, %)
    │                           └─ Heatmap image

═══════════════════════════════════════════════════════════════

ORG BRANCH USER
    │
    └─► /scan (Upload Document)
            │
            ├ If matches protected doc > 70%:
            │
            └─► Success message:
                    └─ "Edit detected and admin has been notified"
                        └─ Email also sent to admin

═══════════════════════════════════════════════════════════════
```

---

## Technical Stack

```
FRONTEND:
├─ HTML5/CSS3
├─ JavaScript (Vanilla)
├─ Bootstrap 5
└─ Bootstrap Icons

BACKEND:
├─ Flask (Web Framework)
├─ SQLAlchemy (ORM)
├─ PyMySQL (Database Driver)
└─ SMTPLib (Email)

ML/CV:
├─ TensorFlow (Model Loading)
├─ NumPy (Numerical Computing)
├─ OpenCV (Image Processing)
├─ Pillow (Image Operations)
└─ SciPy (Scientific Computing)

DATABASE:
├─ MySQL 5.7+
├─ Flask-SQLAlchemy ORM
├─ Proper Indexing
└─ Referential Integrity

DEPLOYMENT:
├─ Python 3.9+
├─ Virtual Environment
├─ Environment Variables (.env)
└─ Flask Development/Production
```

---

## File Organization

```
project/
├── app.py                          ◄─ Main app (modified)
├── db.py                           ◄─ Database models (modified)
├── email_service.py                ◄─ Email service (modified)
├── tracker.py                      ◄─ Tracker helpers (modified)
├── feature_extraction.py           
├── similarity.py
├── preprocessing.py
├── config.py
│
├── templates/
│   ├── base.html
│   ├── admin.html                  ◄─ Modified
│   ├── org_references.html         ◄─ NEW
│   ├── edit_history.html           ◄─ NEW
│   ├── index.html
│   └── [other pages]
│
├── static/
│   ├── styles.css
│   └── [other assets]
│
├── uploads/                        ◄─ User uploads
├── originals/                      ◄─ Protected docs
│
├── DOCUMENT_EDIT_TRACKING.md       ◄─ NEW
├── SETUP_EDIT_TRACKING.md          ◄─ NEW
├── IMPLEMENTATION_EDIT_TRACKING.md ◄─ NEW
│
└── requirements.txt
```

---

## Security Architecture

```
┌─────────────────────────────────────────────┐
│         EXTERNAL REQUEST                    │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Flask Session Middleware                 │
│    - CSRF Protection                        │
│    - Session Validation                     │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Authentication Check                     │
│    - Is user logged in?                     │
│    - Session exists?                        │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Authorization Check                      │
│    - Is admin?                              │
│    - Same organization?                     │
│    - Has permission?                        │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Input Validation                         │
│    - File type check                        │
│    - File size limit                        │
│    - Secure filename                        │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Database Query                           │
│    - Parameterized queries                  │
│    - No SQL injection                       │
│    - Proper indexing                        │
└────────────┬────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────┐
│    Response                                 │
│    - JSON/HTML                              │
│    - Secure headers                         │
│    - No sensitive data                      │
└─────────────────────────────────────────────┘
```

---

## Deployment Checklist

- [ ] Database tables created
- [ ] .env file configured with emails
- [ ] All dependencies installed
- [ ] File permissions correct
- [ ] Upload folders writable
- [ ] SMTP credentials tested
- [ ] Organization set up
- [ ] Admin user created
- [ ] Test upload performed
- [ ] Email alert verified
- [ ] Edit history reviewed
- [ ] Heatmap displays correctly

---

## Performance Optimization Path

```
Baseline Performance:
    Document Upload: 2-3 seconds

Optimization Opportunities:
    ├─ Background Job Queue
    │   └─ Email sending (0.5s saved)
    │
    ├─ Caching Layer
    │   └─ Cache embeddings 
    │       └─ (1s saved on repeated comparisons)
    │
    ├─ Image Compression
    │   └─ Smaller heatmaps
    │       └─ (0.2s saved on heatmap generation)
    │
    └─ Database Connection Pool
        └─ Reuse connections
            └─ (0.3s saved per query)

Optimized Performance:
    Document Upload: 0.5-1 second
```

---

This architecture supports:
- ✅ Multiple organizations
- ✅ Scalable database queries
- ✅ Email notification system
- ✅ Real-time edit detection
- ✅ Audit trail maintenance
- ✅ Security and access control
- ✅ Visual proof generation
- ✅ API integration capabilities
