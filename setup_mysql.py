"""
MySQL Database Setup Script
Run this script to create the database and initialize tables for the Document Forgery Detection System
"""

import pymysql
from pymysql import Error
import os
import sys

def create_database_and_tables():
    """Create MySQL database and tables"""
    
    # Get configuration from environment or use defaults
    db_user = os.getenv('DB_USER', 'samuel')
    db_password = os.getenv('DB_PASSWORD', 'Ii[gJ64@a_Sk5X/(')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '3306'))
    db_name = os.getenv('DB_NAME', 'document_forgery_db')
    
    print(f"\n{'='*60}")
    print("MySQL Database Setup - Document Forgery Detection System")
    print(f"{'='*60}")
    print(f"Host: {db_host}")
    print(f"Port: {db_port}")
    print(f"Database: {db_name}")
    print(f"User: {db_user}")
    print(f"{'='*60}\n")
    
    try:
        # Connect to MySQL server (without database)
        print("📡 Connecting to MySQL server...")
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password
        )
        cursor = connection.cursor()
        print("✅ Connected successfully!\n")
        
        # Create database if it doesn't exist
        print(f"📦 Creating database '{db_name}'...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"✅ Database created/verified\n")
        
        # Switch to the new database
        cursor.execute(f"USE {db_name}")
        
        # Create tables
        tables = {
            'users': """
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(80) UNIQUE NOT NULL,
                    email VARCHAR(120) UNIQUE NOT NULL,
                    password_hash VARCHAR(256) NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_username (username),
                    INDEX idx_email (email)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'verification_results': """
                CREATE TABLE IF NOT EXISTS verification_results (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT NOT NULL,
                    filename VARCHAR(255) NOT NULL,
                    similarity FLOAT NOT NULL,
                    status VARCHAR(50) NOT NULL,
                    closest_match VARCHAR(255),
                    flagged BOOLEAN DEFAULT FALSE,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    INDEX idx_user_id (user_id),
                    INDEX idx_timestamp (timestamp),
                    INDEX idx_status (status)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'reference_documents': """
                CREATE TABLE IF NOT EXISTS reference_documents (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    file_path VARCHAR(512) NOT NULL,
                    embedding_data LONGBLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_name (name)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """,
            'audit_logs': """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    action VARCHAR(255) NOT NULL,
                    details TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
                    INDEX idx_user_id (user_id),
                    INDEX idx_action (action),
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        }
        
        print("📋 Creating database tables...\n")
        for table_name, create_sql in tables.items():
            print(f"  Creating table '{table_name}'... ", end='', flush=True)
            cursor.execute(create_sql)
            print("✅")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"\n{'='*60}")
        print("✅ DATABASE SETUP COMPLETED SUCCESSFULLY!")
        print(f"{'='*60}\n")
        print("📝 Configuration steps:")
        print("  1. Copy .env.example to .env")
        print("  2. Update .env with your MySQL credentials")
        print("  3. Run: python app.py\n")
        
        return True
        
    except Error as err:
        print(f"\n❌ ERROR: {err}")
        print("\n📋 Troubleshooting:")
        print("  • Make sure MySQL is running")
        print("  • Verify database credentials in .env")
        print("  • Ensure user has CREATE DATABASE privilege")
        return False

if __name__ == '__main__':
    success = create_database_and_tables()
    sys.exit(0 if success else 1)
