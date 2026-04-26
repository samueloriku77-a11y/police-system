"""
MySQL Connection Verification Script
Run this before starting the application to verify MySQL connection is working
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def verify_mysql_connection():
    """Test MySQL connection"""
    print("\n" + "="*60)
    print("MySQL Connection Verification")
    print("="*60 + "\n")
    
    # Get config from environment
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '3306'))
    db_name = os.getenv('DB_NAME', 'document_forgery_db')
    
    print("📋 Configuration:")
    print(f"  Host: {db_host}")
    print(f"  Port: {db_port}")
    print(f"  User: {db_user}")
    print(f"  Database: {db_name}\n")
    
    # Test 1: Check PyMySQL
    print("✓ Test 1: Checking PyMySQL...")
    try:
        import pymysql
        print("  ✅ PyMySQL is installed\n")
    except ImportError:
        print("  ❌ PyMySQL not installed")
        print("  Run: pip install PyMySQL\n")
        return False
    
    # Test 2: Direct MySQL connection using PyMySQL with auth plugin fix
    print("✓ Test 2: Testing direct MySQL connection...")
    try:
        import pymysql
        # Use PyMySQL with proper authentication plugin handling
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with connection.cursor() as cursor:
            cursor.execute("SELECT VERSION() as version")
            result = cursor.fetchone()
            print(f"  ✅ Connected to MySQL {result['version']}\n")
        connection.close()
    except Exception as e:
        print(f"  ❌ Direct connection failed: {e}\n")
        print("  Troubleshooting:")
        print("  • Verify MySQL server is running")
        print("  • Check username and password in .env")
        print("  • Verify host and port are correct")
        print("  • For MySQL 8.0+, you may need to update user auth plugin:")
        print("    ALTER USER '{db_user}'@'localhost' IDENTIFIED WITH mysql_native_password BY 'your_password';\n")
        return False

    
    # Test 3: Database exists
    print("✓ Test 3: Checking if database exists...")
    try:
        import pymysql
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        with connection.cursor() as cursor:
            cursor.execute(f"SHOW DATABASES LIKE '{db_name}'")
            result = cursor.fetchone()
            if result:
                print(f"  ✅ Database '{db_name}' exists\n")
            else:
                print(f"  ⚠️  Database '{db_name}' does not exist")
                print("  Run: python setup_mysql.py\n")
        connection.close()
    except Exception as e:
        print(f"  ❌ Database check failed: {e}\n")
        return False

    
    # Test 4: Flask-SQLAlchemy connection
    print("✓ Test 4: Testing Flask-SQLAlchemy connection...")
    try:
        from app import app, db
        with app.app_context():
            connection = db.engine.connect()
            print("  ✅ Flask-SQLAlchemy connected successfully\n")
            connection.close()
    except Exception as e:
        print(f"  ❌ Flask-SQLAlchemy connection failed: {e}\n")
        print("  Troubleshooting:")
        print("  • Run: python setup_mysql.py")
        print("  • Verify .env configuration")
        print("  • Check MySQL server status\n")
        return False
    
    # Test 5: Check tables
    print("✓ Test 5: Checking database tables...")
    try:
        from app import app, db
        with app.app_context():
            cursor = db.engine.execute("SHOW TABLES")
            tables = cursor.fetchall()
            if tables:
                print("  ✅ Tables found:")
                for table in tables:
                    print(f"     • {table[0]}")
                print()
            else:
                print("  ⚠️  No tables found - run: python setup_mysql.py\n")
    except Exception as e:
        print(f"  ℹ️  Could not check tables (may need setup): {e}\n")
    
    return True


def main():
    """Main verification function"""
    success = verify_mysql_connection()
    
    print("="*60)
    if success:
        print("✅ ALL TESTS PASSED!")
        print("="*60)
        print("\n🚀 You can now run: python app.py\n")
        return 0
    else:
        print("❌ VERIFICATION FAILED!")
        print("="*60)
        print("\n📋 Next steps:")
        print("  1. Check the errors above")
        print("  2. Install missing dependencies: pip install -r requirements.txt")
        print("  3. Initialize database: python setup_mysql.py")
        print("  4. Re-run verification: python verify_mysql.py\n")
        return 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
