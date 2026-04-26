"""
MySQL Database Initialization Script
Loads the database_schema.sql file into MySQL
"""

import os
import sys
import subprocess
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def run_sql_file():
    """Load SQL schema file into MySQL"""
    
    db_user = os.getenv('DB_USER', 'root')
    db_password = os.getenv('DB_PASSWORD', 'root')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '3306')
    
    sql_file = 'database_schema.sql'
    
    print("\n" + "="*70)
    print("MySQL Database Initialization")
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
    
    # Build MySQL command
    if db_password:
        cmd = [
            'mysql',
            f'--host={db_host}',
            f'--port={db_port}',
            f'--user={db_user}',
            f'--password={db_password}',
            '<',
            sql_file
        ]
    else:
        cmd = [
            'mysql',
            f'--host={db_host}',
            f'--port={db_port}',
            f'--user={db_user}',
            '<',
            sql_file
        ]
    
    try:
        print("⏳ Loading database schema...\n")
        
        # Execute SQL file
        if db_password:
            process = subprocess.Popen(
                f'mysql --host={db_host} --port={db_port} --user={db_user} --password={db_password} < {sql_file}',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        else:
            process = subprocess.Popen(
                f'mysql --host={db_host} --port={db_port} --user={db_user} < {sql_file}',
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            print(f"❌ ERROR: Failed to load database schema")
            print(f"   {stderr}\n")
            return False
        
        print("✅ Database schema loaded successfully!\n")
        print(stdout)
        
        # Verify installation
        print("\n📊 Verifying installation...")
        verify_cmd = f'mysql --host={db_host} --port={db_port} --user={db_user} --password={db_password} -e "USE document_forgery_db; SHOW TABLES;" 2>/dev/null' if db_password else f'mysql --host={db_host} --port={db_port} --user={db_user} -e "USE document_forgery_db; SHOW TABLES;" 2>/dev/null'
        
        verify_process = subprocess.Popen(verify_cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        verify_output, verify_error = verify_process.communicate()
        
        if verify_output:
            print("✅ Tables created:")
            print(verify_output)
        
        print("\n" + "="*70)
        print("✅ DATABASE INITIALIZATION COMPLETE!")
        print("="*70)
        print("\n🚀 You can now start the application:")
        print("   python app.py\n")
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}\n")
        print("Troubleshooting:")
        print("  1. Make sure MySQL is running")
        print("  2. Verify credentials in .env file")
        print("  3. Ensure database_schema.sql exists\n")
        return False


def main():
    """Main function"""
    success = run_sql_file()
    return 0 if success else 1


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
