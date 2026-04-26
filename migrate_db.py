from app import app
from db import db
from sqlalchemy import text

def migrate():
    with app.app_context():
        try:
            db.session.execute(text("ALTER TABLE users ADD COLUMN organization_name VARCHAR(120);"))
            print("✅ Successfully injected `organization_name` into `users` table.")
            db.session.commit()
        except Exception as e:
            print(f"⚠️ Notice: `organization_name` column may already exist or error: {e}")
            db.session.rollback()

if __name__ == "__main__":
    migrate()
