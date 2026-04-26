"""
Database Migration Script - Add missing columns to verification_results table
Run this to update existing database schema
"""

import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

# Database configuration
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME = os.getenv('DB_NAME', 'forgery_detector_db')

def migrate_database():
    """Add missing columns to verification_results table"""
    
    try:
        # Connect to database
        connection = pymysql.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        
        cursor = connection.cursor()
        
        print("🔄 Starting database migration...")
        
        # Check if columns exist and add them if they don't
        check_query = """
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'verification_results' AND COLUMN_NAME = 'document_type'
        """
        
        cursor.execute(check_query)
        result = cursor.fetchone()
        
        if not result:
            print("  Adding 'document_type' column...")
            alter_query_1 = """
            ALTER TABLE verification_results 
            ADD COLUMN document_type VARCHAR(50) NULL DEFAULT 'Document' AFTER status
            """
            cursor.execute(alter_query_1)
            connection.commit()
            print("    ✓ document_type column added")
        else:
            print("  ✓ document_type column already exists")
        
        # Check for matched_reference_id column
        check_query_2 = """
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'verification_results' AND COLUMN_NAME = 'matched_reference_id'
        """
        
        cursor.execute(check_query_2)
        result_2 = cursor.fetchone()
        
        if not result_2:
            print("  Adding 'matched_reference_id' column...")
            alter_query_2 = """
            ALTER TABLE verification_results 
            ADD COLUMN matched_reference_id INT NULL AFTER flagged,
            ADD FOREIGN KEY (matched_reference_id) REFERENCES reference_documents(id) ON DELETE SET NULL
            """
            cursor.execute(alter_query_2)
            connection.commit()
            print("    ✓ matched_reference_id column added with foreign key")
        else:
            print("  ✓ matched_reference_id column already exists")
        
        # Check document_type column in reference_documents
        check_query_3 = """
        SELECT COLUMN_NAME 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'reference_documents' AND COLUMN_NAME = 'document_type'
        """
        
        cursor.execute(check_query_3)
        result_3 = cursor.fetchone()
        
        if not result_3:
            print("  Adding 'document_type' column to reference_documents...")
            alter_query_3 = """
            ALTER TABLE reference_documents 
            ADD COLUMN document_type VARCHAR(50) NULL DEFAULT NULL AFTER embedding_data,
            ADD INDEX idx_document_type (document_type)
            """
            cursor.execute(alter_query_3)
            connection.commit()
            print("    ✓ document_type column added to reference_documents")
        else:
            print("  ✓ document_type column already exists in reference_documents")
        
        cursor.close()
        connection.close()
        
        print("\n✅ Migration completed successfully!")
        print("   The database schema is now up-to-date.")
        return True
        
    except pymysql.Error as err:
        if err.args[0] == 1054:
            print(f"❌ Column error: {err.args[1]}")
        elif err.args[0] == 1091:
            print(f"⚠️  Column already exists: {err.args[1]}")
        else:
            print(f"❌ MySQL Error: {err}")
        return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    print("=" * 60)
    print("Database Migration Tool")
    print("=" * 60)
    success = migrate_database()
    print("=" * 60)
    exit(0 if success else 1)
