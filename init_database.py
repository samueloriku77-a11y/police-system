"""
Database initialization script
This script creates the SQLite database and populates it with reference images
"""

import os
import sys
from app import app, db
from db import User, VerificationResult, ReferenceDocument, AuditLog
import pickle
import json

def init_database():
    """Initialize database tables"""
    with app.app_context():
        print("Creating database tables...")
        db.create_all()
        print("✓ Database tables created successfully")
        
        # Create default admin user if it doesn't exist
        admin_user = User.query.filter_by(email='admin@example.com').first()
        if not admin_user:
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_admin=True
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("✓ Admin user created: admin@example.com / admin123")
        else:
            print("✓ Admin user already exists")


def load_reference_images():
    """Load reference images from originals folder into database"""
    with app.app_context():
        originals_folder = 'originals'
        
        if not os.path.exists(originals_folder):
            print(f"! {originals_folder}/ folder not found. Creating it...")
            os.makedirs(originals_folder, exist_ok=True)
            print(f"✓ Created {originals_folder}/ folder")
            print(f"  (Place your reference images here)")
            return
        
        # Get list of image files
        supported_formats = ('.jpg', '.jpeg', '.png', '.bmp', '.gif', '.tiff')
        image_files = [f for f in os.listdir(originals_folder) 
                      if f.lower().endswith(supported_formats)]
        
        if not image_files:
            print(f"! No image files found in {originals_folder}/")
            print(f"  Place reference images in the {originals_folder}/ folder")
            return
        
        print(f"\nFound {len(image_files)} reference image(s)")
        
        for filename in image_files:
            filepath = os.path.join(originals_folder, filename)
            
            # Check if already in database
            existing = ReferenceDocument.query.filter_by(name=filename).first()
            if existing:
                print(f"  ∘ {filename} (already in database)")
                continue
            
            try:
                # Read image file
                with open(filepath, 'rb') as f:
                    image_data = f.read()
                
                # Create reference document record
                ref_doc = ReferenceDocument(
                    name=filename,
                    file_path=filepath,
                    embedding_data=image_data
                )
                db.session.add(ref_doc)
                print(f"  ✓ {filename} (added to database)")
            except Exception as e:
                print(f"  ✗ {filename} (error: {e})")
        
        db.session.commit()
        print(f"\n✓ Reference images loaded successfully")


def load_embeddings_to_database():
    """Load pre-computed embeddings from models/embeddings.json if available"""
    with app.app_context():
        embeddings_file = 'models/embeddings.json'
        
        if not os.path.exists(embeddings_file):
            print(f"! No embeddings file found at {embeddings_file}")
            return
        
        try:
            with open(embeddings_file, 'r') as f:
                embeddings_data = json.load(f)
            
            print(f"\nFound embeddings for {len(embeddings_data)} image(s)")
            print("✓ Embeddings metadata loaded (embeddings stored with reference images)")
        except Exception as e:
            print(f"! Error loading embeddings: {e}")


def display_database_summary():
    """Display summary of database contents"""
    with app.app_context():
        print("\n" + "="*60)
        print("DATABASE SUMMARY")
        print("="*60)
        
        user_count = User.query.count()
        ref_count = ReferenceDocument.query.count()
        result_count = VerificationResult.query.count()
        log_count = AuditLog.query.count()
        
        print(f"Users:                 {user_count}")
        print(f"Reference Documents:   {ref_count}")
        print(f"Verification Results:  {result_count}")
        print(f"Audit Logs:            {log_count}")
        
        if ref_count > 0:
            print("\nReference Documents in Database:")
            refs = ReferenceDocument.query.all()
            for ref in refs:
                size_kb = len(ref.embedding_data) / 1024 if ref.embedding_data else 0
                print(f"  - {ref.name} ({size_kb:.1f} KB)")
        
        print("="*60)


if __name__ == '__main__':
    print("=" * 60)
    print("DOCUMENT FORGERY DETECTION SYSTEM - DATABASE INITIALIZATION")
    print("=" * 60)
    
    # Initialize database
    init_database()
    
    # Load reference images
    load_reference_images()
    
    # Load embeddings
    load_embeddings_to_database()
    
    # Display summary
    display_database_summary()
    
    print("\n✓ Database initialization complete!")
    print("  You can now run: python app.py")
