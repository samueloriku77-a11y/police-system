"""
Pure Python MySQL Database Loader
No MySQL CLI required - uses PyMySQL directly
"""

import os
import sys
from dotenv import load_dotenv
import pymysql

# Load environment variables
load_dotenv()

def load_sql_file_python():
    """Load SQL schema using pure Python (PyMySQL)"""
    
    # Get configuration
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = int(os.getenv('DB_PORT', '3306'))
    
    sql_file = 'database_schema.sql'
    
    print("\n" + "="*70)
    print("MySQL Database Initialization (Python)")
    print("="*70)
    print(f"\n📋 Configuration:")
    print(f"  Host: {db_host}")
    print(f"  Port: {db_port}")
    print(f"  User: {db_user}")
    print(f"  SQL File: {sql_file}\n")
    
    # Check if SQL file exists
    if not os.path.exists(sql_file):
        print(f"❌ ERROR: {sql_file} not found!")
        print(f"   Make sure {sql_file} exists in the current directory\n")
        return False
    
    try:
        import pymysql
    except ImportError:
        print("❌ ERROR: PyMySQL not installed")
        print("   Run: pip install PyMySQL\n")
        return False
    
    try:
        # Read SQL file
        print("📖 Reading SQL file...")
        with open(sql_file, 'r') as f:
            sql_content = f.read()
        print("✅ SQL file loaded\n")
        
        # Connect to MySQL
        print("📡 Connecting to MySQL server...")
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            charset='utf8mb4'
        )
        cursor = connection.cursor()
        print("✅ Connected successfully\n")
        
        # Execute SQL statements
        print("⏳ Executing SQL schema...\n")
        
        # Split SQL file by statements and execute
        statements = sql_content.split(';')
        executed = 0
        
        for statement in statements:
            statement = statement.strip()
            
            # Skip empty statements and comments
            if not statement or statement.startswith('--'):
                continue
            
            # Skip comment-only lines
            if statement.startswith('/*') or statement.endswith('*/'):
                continue
            
            try:
                cursor.execute(statement)
                executed += 1
                print(f"  ✓ Statement {executed} executed")
            except Exception as e:
                print(f"  ⚠️  Warning: {str(e)[:100]}")
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"\n✅ Successfully executed {executed} SQL statements\n")
        
        # Verify installation
        print("📊 Verifying installation...")
        connection = pymysql.connect(
            host=db_host,
            port=db_port,
            user=db_user,
            password=db_password,
            database='document_forgery_db',
            charset='utf8mb4'
        )
        cursor = connection.cursor()
        
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        print(f"\n✅ Database tables created ({len(tables)} tables):")
        for table in tables:
            print(f"   • {table[0]}")
        
        # Check admin user
        cursor.execute("SELECT username, email FROM users LIMIT 1")
        admin = cursor.fetchone()
        if admin:
            print(f"\n✅ Admin user created:")
            print(f"   Username: {admin[0]}")
            print(f"   Email: {admin[1]}")
        
        cursor.close()
        connection.close()
        
        print("\n" + "="*70)
        print("✅ DATABASE INITIALIZATION COMPLETE!")
        print("="*70)
        print("\n🚀 Ready to start the application!")
        print("   python app.py\n")
        print("📝 Login credentials:")
        print("   Email: admin@example.com")
        print("   Password: admin123\n")
        
        return True
        
    except pymysql.Error as err:
        print(f"❌ Database ERROR: {err}\n")
        print("Troubleshooting:")
        print("  • Make sure MySQL is running")
        print("  • Verify username and password in .env file")
        print("  • Check host and port configuration")
        print()
        return False
        
    except Exception as e:
        print(f"❌ ERROR: {e}\n")
        print("Troubleshooting:")
        print("  1. Make sure MySQL Server is running")
        print("  2. Verify credentials in .env file")
        print("  3. Ensure database_schema.sql exists in current directory")
        print("  4. Run: pip install PyMySQL\n")
        return False


def main():
    """Main function"""
    success = load_sql_file_python()
    return 0 if success else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
