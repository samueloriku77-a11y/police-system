import os
import sqlite3
import re
import cv2
import easyocr
from feature_extraction import ForgeryDetector

DB_PATH = "local_demo.db"

def init_db():
    """Initializes the SQLite database as requested."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS authentic_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            id_number TEXT,
            image_blob BLOB
        )
    ''')
    conn.commit()
    conn.close()

def verify_document(image_path: str) -> bool:
    """Uses the ForgeryDetector to return a boolean is_authentic."""
    try:
        detector = ForgeryDetector()
        results = detector.detect_forged_regions(image_path)
        verdict = results.get('verdict', 'ERROR')
        is_authentic = (verdict == 'AUTHENTIC')
        return is_authentic
    except Exception as e:
        print(f"Extraction Error: {e}")
        return False

def extract_id_number(image_path: str) -> str:
    """Uses easyocr to extract the ID number from an image independently."""
    try:
        if not os.path.exists(image_path):
            raise ValueError("Could not open image for OCR.")
            
        print("Loading EasyOCR Language Models (This may take a moment on first run)...")
        reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        result = reader.readtext(image_path, detail=0)
        text = " ".join(result)
        
        # Often ID numbers are 7-15 digits with optional letters
        potentials = re.findall(r'\b[A-Z0-9-]{6,15}\b', text)
        
        id_candidates = [p for p in potentials if any(c.isdigit() for c in p)]
        return id_candidates[0] if id_candidates else "OCR_NO_ID_FOUND"
        
    except Exception as e:
        print(f"Error during EasyOCR extraction: {e}")
        return "ERROR_READING_ID"

def save_authentic_document(image_path: str, id_number: str, db_path: str = DB_PATH):
    """Saves the extracted ID Number and the image blob to the SQLite DB."""
    try:
        with open(image_path, 'rb') as f:
            blob_data = f.read()
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO authentic_documents (id_number, image_blob)
                     VALUES (?, ?)''', (id_number, blob_data))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Database error during save: {e}")

def process_document(image_path: str):
    """Main workflow logic as requested."""
    print(f"--- Processing Document: {image_path} ---")
    if not os.path.exists(image_path):
        print("FORGERY (File not found)")
        return
        
    init_db()
    
    print("Running Forgery Detection...")
    is_authentic = verify_document(image_path)
    
    if not is_authentic:
        print("FORGERY")
        return
        
    print("Authentic Document. Extracting ID Number...")
    id_number = extract_id_number(image_path)
    
    if id_number not in ["OCR_NO_ID_FOUND", "ERROR_READING_ID", "TESSERACT_NOT_INSTALLED"]:
        print(f"Extracted ID Number: {id_number}")
    else:
        print(f"Warning: Could not read a clear ID number. Message: {id_number}")
        
    print("Saving to local SQLite database...")
    save_authentic_document(image_path, id_number)
    print(f"Success: Document verified and saved to database.")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        process_document(sys.argv[1])
    else:
        print("Usage: python document_pipeline.py path/to/image.jpg")
