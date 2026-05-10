import os
from app import app, db
from dotenv import load_dotenv

def init_database():
    """
    Initialize the database connection and create all tables.
    Useful for creating the schema in a remote database like Aiven.
    """
    # Force load environment variables if they exist
    load_dotenv()
    
    print("="*50)
    print("🚀 Initializing Database on Aiven")
    print("="*50)
    print(f"Target Host: {os.getenv('DB_HOST', 'localhost')}")
    print(f"Target DB:   {os.getenv('DB_NAME', 'document_forgery_db')}")
    
    try:
        with app.app_context():
            # This uses the connection string defined in app.py
            print("\nCreating tables (this may take a few seconds on remote DBs)...")
            db.create_all()
            print("\n✅ Database tables successfully created!")
            
    except Exception as e:
        print("\n❌ ERROR: Failed to create tables.")
        print(f"Details: {str(e)}")
        print("\nPlease ensure your .env file has the correct Aiven credentials:")
        print("DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME")

if __name__ == "__main__":
    init_database()
