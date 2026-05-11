from app import app, db

def reset_database():
    with app.app_context():
        print("Dropping all existing tables to clear old schemas...")
        db.drop_all()
        print("Creating all tables from current db.py models...")
        db.create_all()
        
        # Re-insert default admin user since we wiped the DB
        from db import User
        import hashlib
        
        if not User.query.filter_by(username='admin').first():
            admin = User(
                username='admin',
                email='admin@example.com',
                is_admin=True,
                organization_name='Headquarters'
            )
            admin.password_hash = hashlib.sha256('admin'.encode()).hexdigest()
            db.session.add(admin)
            db.session.commit()
            print("Default admin user created.")
            
        print("Database reset successfully! All tables match current models.")

if __name__ == "__main__":
    reset_database()
