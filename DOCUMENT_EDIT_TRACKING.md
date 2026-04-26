# Document Edit Detection & Tracking Feature

## Overview

This document describes the newly implemented feature for detecting when protected reference documents are edited and notifying administrators automatically. This system is designed for organizations where certain documents (like official templates, IDs, certificates) should never be modified without knowledge.

---

## How It Works

### 1. **Organization Admin Uploads Protected Documents**

- Admin navigates to: `/admin/org-references` 
- Uploads a reference document (JPG, PNG, BMP, PDF)
- Marks it as "Protected from edits" with optional description
- Document is stored and its features are extracted via embedding

### 2. **User Uploads a Document**

- Regular user uploads a document via `/detect` endpoint
- System compares the document against all protected reference documents for that organization
- If similarity > 70%, system detects it as a potential edited version

### 3. **Edit Detection Triggered**

When an edit is detected:
- Visual diff heatmap is generated showing exactly what changed
- Changed regions are counted and percentage calculated
- Edit details logged to database: `DocumentEditLog`
- Admin email alert automatically sent
- User receives upload confirmation

### 4. **Admin Receives Email Alert**

Email includes:
- ✏️ Which original document was edited
- 👤 Who uploaded the edited version (username, office)
- 📊 Similarity score (how similar to original)
- 🖼️ Changed regions count and percentage
- 🔗 Instructions to review in Tracker Dashboard

### 5. **Admin Reviews Edit History**

- Navigate to: `/admin/edit-history`
- View all detected edits with details:
  - Original vs edited filenames
  - Who edited (office location)
  - Similarity percentage
  - Number of changed regions
  - When it was detected
  - Visual heatmap of changes

---

## Database Schema

### New Tables

#### 1. **OrganizationReferenceDocument**
Stores protected documents at the organization level:
```
id: Primary key
organization_name: Organization this document belongs to
document_name: File name
file_path: Location on disk
embedding_data: Serialized feature vector
should_not_edit: Boolean (True = protect from edits)
description: Admin notes about this document
uploaded_by_id: User who uploaded it
created_at: When uploaded
```

#### 2. **DocumentEditLog**
Records every detected edit:
```
id: Primary key
organization_name: Which organization
ref_document_id: Link to the protected document
original_filename: Name of protected template
uploaded_filename: Name of edited version uploaded
uploader_id: User who uploaded edited version
uploader_office: Office/branch of uploader
similarity_score: 0-1 similarity with original
changed_regions_count: Number of changed areas
changed_regions_percentage: % of document changed
diff_heatmap_b64: Base64 encoded heatmap image
change_details: JSON with detailed change info
email_sent_to_admin: Whether alert was sent
admin_notified_id: Admin who was notified
timestamp: When detected
```

---

## API Endpoints

### Admin Endpoints

#### **Upload Protected Document**
```
POST /admin/upload-org-reference
Required: Admin user, part of organization

Form Data:
- file: Document file (JPG/PNG/BMP/PDF)
- description: (optional) Purpose of document
- should_not_edit: (optional, default=true) Protect from edits

Response:
{
  "success": true,
  "message": "Organization reference document uploaded successfully",
  "filename": "...",
  "doc_id": 123,
  "should_not_edit": true
}
```

#### **List Organization Reference Documents**
```
GET /admin/list-org-references
Required: Admin user

Response:
{
  "success": true,
  "documents": [
    {
      "id": 123,
      "document_name": "passport_template.jpg",
      "should_not_edit": true,
      "description": "Official passport template",
      "created_at": "2024-01-15T10:30:00"
    }
  ]
}
```

#### **Delete Organization Reference Document**
```
POST /admin/delete-org-reference/<doc_id>
Required: Admin user

Response:
{
  "success": true,
  "message": "Reference document deleted successfully"
}
```

#### **Get Edit History**
```
GET /api/edit-history
Required: Admin user

Response:
{
  "success": true,
  "edits": [
    {
      "id": 456,
      "organization_name": "ABC Corp",
      "original_filename": "passport_template.jpg",
      "uploaded_filename": "passport_template_edited.jpg",
      "uploader_office": "Branch A",
      "similarity_score": 0.85,
      "changed_regions_count": 3,
      "changed_regions_percentage": 12.5,
      "email_sent_to_admin": true,
      "timestamp": "2024-01-20T14:22:00"
    }
  ]
}
```

#### **Get Edit Details with Heatmap**
```
GET /admin/edit-details/<edit_log_id>
Required: Admin user

Response:
{
  "success": true,
  "edit_log": {...},
  "uploader": {
    "username": "john_branch_a",
    "email": "john@company.com"
  },
  "heatmap_b64": "base64_encoded_png_image_data..."
}
```

### Document Comparison API

#### **Compare Document with Reference**
```
POST /api/compare-documents
Required: Admin user

Form Data:
- file: Document to compare
- ref_doc_id: Reference document ID

Response:
{
  "success": true,
  "comparison": {
    "reference_document": {...},
    "similarity_score": 0.92,
    "changed_regions": 5,
    "change_percentage": 18.3,
    "heatmap_b64": "...",
    "is_edited": true
  }
}
```

---

## UI Pages

### 1. **Organization Reference Documents** (`/admin/org-references`)
- Upload new protected documents
- View all protected documents
- Delete documents
- Set protection status

### 2. **Edit History** (`/admin/edit-history`)
- Table of all detected edits
- Sort by date, similarity, changed regions
- Click "View" to see detailed heatmap
- Shows: original doc, edited doc, who did it, similarity score

### 3. **Admin Dashboard** (`/admin`)
- Added new buttons:
  - "Manage Protected Documents" → org_references
  - "View Edit History" → edit_history

---

## Detection Logic

### Similarity Threshold: 70%

When document is uploaded:

1. Extract features from uploaded document
2. Get all protected documents for organization
3. Calculate embedding-based cosine similarity with each
4. If any similarity > 0.70:
   - Mark as "edited"
   - Generate visual diff
   - Log to database
   - Send email alert

### Visual Diff Generation

- Resize both images to same dimensions
- Calculate absolute difference
- Apply threshold to find changed regions
- Count number of changed areas
- Calculate percentage of pixels changed
- Draw red boxes around changed regions
- Encode as base64 PNG for email/display

---

## Email Alerts

### Edit Detection Email

**Subject:** `⚠️ DOCUMENT EDIT DETECTED: {original_filename}`

**Content:**
- Organization name
- Who uploaded the edit (username, office)
- Original document name
- Edited version filename
- Similarity score with color coding
- Number of changed regions
- Percentage of document changed
- Call to action: Review in Tracker Dashboard
- Heatmap image (if available)

---

## Feature Extraction Usage

The system now fully utilizes feature extraction data:

- **For normal users:** Results displayed in UI
- **For organizations:** Results used to:
  - Compare uploaded documents against protected templates
  - Generate similarity scores
  - Detect edits automatically
  - Track who edited what and when
  - Create audit trail

---

## Implementation Example

### Scenario: ABC Corp with 2 Branches

**Setup:**
1. Admin uploads: `passport_template.jpg` (marked as protected)
2. System extracts embedding and stores in DB

**Branch A uploads `passport_edited.jpg`:**
1. System extracts features
2. Compares with `passport_template.jpg`
3. Similarity: 0.88 (> 70% threshold)
4. Creates heatmap showing 3 regions changed
5. Logs to `DocumentEditLog`
6. Sends email to admin with details
7. Admin reviews in `/admin/edit-history`
8. Admin sees heatmap showing exact changes

---

## Error Handling

- PDF conversion fails → falls back to PNG
- Embedding extraction fails → document skipped from comparison
- File operations fail → logged with error details
- Email sending fails → error logged, edits still recorded

---

## Security Considerations

- ✓ Admin-only access to protected document management
- ✓ Organization-scoped visibility (admins only see their org's documents)
- ✓ Edit history only visible to organization admin
- ✓ Audit trail of all operations logged
- ✓ File paths validated before access

---

## Future Enhancements

- [ ] Webhook notifications on edit detection
- [ ] Bulk upload of protected documents
- [ ] Edit detection rules (notify only if > X% changed)
- [ ] Integration with document signing/certification
- [ ] Historical comparison (track all versions of document)
- [ ] Admin approval workflow for edits
- [ ] CSV export of edit history
- [ ] OCR to detect text changes specifically

---

## Configuration

In `.env` file:

```
# Email settings
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_PROVIDER=gmail
#

# Organization settings
ORGANIZATION_NAME=Your Organization
ADMIN_EMAIL=admin@yourorg.com
```

---

## Troubleshooting

### Issue: Edit not detected on similar document
**Solution:** Threshold is 70% similarity. Increase threshold in code if needed:
- Find: `if similarity > 0.70:`
- Change to higher value (e.g., 0.85)

### Issue: Email not sending
**Solution:** 
- Verify `.env` credentials
- Check if 2FA is enabled (use app password for Gmail)
- Verify SMTP server and port settings

### Issue: Heatmap not showing
**Solution:**
- Check if PDF conversion is supported (requires poppler-utils)
- Verify OpenCV is properly installed
- Check file permissions on disk

---

## Summary

This feature enhances your document forgery detection system by:
- ✅ Automatically detecting when protected documents are edited
- ✅ Tracking who edited them and what changed
- ✅ Alerting admins via email with visual proof
- ✅ Maintaining audit trail for compliance
- ✅ Utilizing feature extraction data for document comparison
- ✅ Providing admin dashboard for review and management
