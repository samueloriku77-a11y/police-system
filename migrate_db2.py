from app import app
from db import db
from sqlalchemy import text

def migrate_tracker():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE document_tracker_logs ADD COLUMN similarity_score FLOAT;"))
            db.session.commit()
            print("✅ Successfully injected `similarity_score` into `document_tracker_logs` table.")
        except Exception as e: pass

        try:
            db.session.execute(text("ALTER TABLE document_tracker_logs ADD COLUMN forgery_confidence FLOAT;"))
            db.session.commit()
            print("✅ Successfully injected `forgery_confidence` into `document_tracker_logs` table.")
        except Exception as e: pass

if __name__ == "__main__":
    migrate_tracker()
