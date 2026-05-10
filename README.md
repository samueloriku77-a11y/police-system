# Zero-Trust Document Integrity System

A folder-based, forensic-level document forgery detection system. It turns your physical master references into a dynamic "Source of Truth" to automatically block digitally altered or structurally shifted documents.

## 🎯 How It Works (The "Police" Engine)

1. **Folder-as-Category Logic**: 
   The system monitors the `master_references/` directory. Each sub-folder (e.g., `/Contracts`, `/Invoices`) acts as a 'Document Category'. 

2. **Master Anchoring**: 
   When a user uploads a document, they select the category. The system instantly retrieves the corresponding 'Master' file from the physical folder.

3. **Forensic Zero-Trust Analysis**:
   - **Structural Alignment**: Checks if text blocks or signatures have been shifted using exact pixel alignment. Requires a strict `>98%` match.
   - **Error Level Analysis (ELA)**: Scans for pixel-density anomalies that indicate digital 'White-Out', re-typing, or photoshopped elements.
   - **Siamese Networks**: Utilizes deep learning to compute embedding distances between the Suspect and Master documents.

4. **The 'Document Police' Action**:
   If a discrepancy is found (e.g., `< 98%` structural match), the system instantly:
   - **Blocks** the upload.
   - **Generates** a side-by-side Comparison Heatmap showing the exact point of forgery.
   - **Logs** the user's ID and action to the Audit Database.
   - **Sends** an automated SMTP Alert to the Sudo Admin with the forensic heatmap attached.

---

## 🚀 Setup & Testing (XAMPP / Local)

### 1. Database Configuration
If you are testing this locally via XAMPP, you can use the provided `schema.sql` file to instantly structure your database:
1. Open phpMyAdmin in XAMPP.
2. Create a new database named `document_forgery_db`.
3. Go to the "Import" tab and upload `schema.sql`.

Alternatively, update your `.env` or `app.py` configuration with your MySQL credentials:
```python
app.config['SQLALCHEMY_DATABASE_URI'] = "mysql+pymysql://root:@localhost:3306/document_forgery_db"
```
*Note: Running `python app.py` will also automatically build the missing tables if your DB is empty.*

### 2. Physical Folders
Create your reference categories and add your master files. For example:
```
master_references/
├── Contracts/
│   └── master_template.pdf
└── Invoices/
    └── master_invoice.jpg
```
The frontend will dynamically read these folders by calling `GET /api/categories`.

### 3. Run the Backend
```bash
# Create virtual environment (optional)
python -m venv dvs
source dvs/bin/activate  # or .\dvs\Scripts\Activate.ps1 on Windows

# Install Dependencies
pip install -r requirements.txt

# Run
python app.py
```
The application will be running on `http://localhost:5000`.

---

## 🔗 Core API Endpoints

- `GET /api/categories` - Returns the dynamic categories based on your `master_references/` subfolders.
- `POST /api/zero-trust-upload` - Takes `document` (file) and `category` (string). Runs the Forensic Analyzer and returns `VERIFIED` or instantly blocks it with a `REJECTED` status and alignment score.
- `POST /login` - User authentication.
- `POST /register` - Creates a user account.
