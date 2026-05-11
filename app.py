from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, make_response

from flask_session import Session
import cv2
import numpy as np
import json
import pickle
import os
from werkzeug.utils import secure_filename
import hashlib
import datetime
from dotenv import load_dotenv
from db import (
    db, User, VerificationResult, AuditLog, ReferenceDocument, DocumentTrackerLog,
    OrganizationReferenceDocument, DocumentEditLog,
    DocumentType, ReferenceTemplate, ProtectedZone, ForensicReport, FraudAlert
)
from email_service import email_service
from zero_trust_engine import DirectoryWatcher, ForgeryAnalyzer, generate_difference_heatmap
import base64
import io
from urllib.parse import quote
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None


# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-12345'
if os.getenv("VERCEL"):
    app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
    app.config['ORIGINALS_FOLDER'] = '/tmp/originals'
    app.config['REPORTS_FOLDER'] = '/tmp/reports'
    app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'
else:
    app.config['UPLOAD_FOLDER'] = 'uploads'
    app.config['ORIGINALS_FOLDER'] = 'originals'
    app.config['REPORTS_FOLDER'] = 'reports'

app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB
app.config['SESSION_TYPE'] = 'filesystem'

# MySQL Configuration - Use environment variables for security
DB_USER = os.getenv('DB_USER', 'root')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'root')
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = os.getenv('DB_PORT', '3306')
DB_NAME = os.getenv('DB_NAME', 'document_forgery_db')

# MySQL Connection String - URL-encode password for special characters
db_password_encoded = quote(DB_PASSWORD, safe='')
app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{DB_USER}:{db_password_encoded}@{DB_HOST}:{DB_PORT}/{DB_NAME}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 280,
    'pool_pre_ping': True,
    'connect_args': {
        'auth_plugin_map': {
            'caching_sha2_password': 'mysql_native_password'
        }
    }
}

Session(app)
db.init_app(app)

# Create necessary directories
for folder in [app.config['UPLOAD_FOLDER'], app.config['ORIGINALS_FOLDER'], app.config['REPORTS_FOLDER']]:
    os.makedirs(folder, exist_ok=True)

from tracker import tracker_bp
app.register_blueprint(tracker_bp)


@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/dashboard')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    recent_history = VerificationResult.query.filter_by(user_id=session.get('user_id')).order_by(VerificationResult.timestamp.desc()).limit(10).all()
        
    return render_template('index.html', username=session.get('username'), recent_history=recent_history)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['is_admin'] = user.is_admin
            # Add audit log
            log = AuditLog(user_id=user.id, action='LOGIN', details='User logged in')
            db.session.add(log)
            db.session.commit()
            return redirect(url_for('index'))

        else:
            flash('Invalid email or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        account_type = request.form.get('account_type', 'office')
        org_name = request.form.get('organization_name', '')
        
        if password != confirm_password:
            flash('Passwords do not match', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'danger')
            return render_template('register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Username already taken', 'danger')
            return render_template('register.html')
        
        is_admin = (account_type == 'organization')
        
        user = User(
            username=username, 
            email=email, 
            is_admin=is_admin,
            organization_name=org_name
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        # Add audit log
        log = AuditLog(user_id=user.id, action='REGISTER', details='User registered')
        db.session.add(log)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    user_id = session.get('user_id')
    if user_id:
        # Add audit log
        log = AuditLog(user_id=user_id, action='LOGOUT', details='User logged out')
        db.session.add(log)
        db.session.commit()
    session.clear()
    flash('You have been logged out', 'info')
    return redirect(url_for('login'))

@app.route('/admin')
def admin():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    user_id = session.get('user_id')
    # Get user's verification results
    all_results = VerificationResult.query.filter_by(user_id=user_id).all()
    flagged_results = VerificationResult.query.filter_by(user_id=user_id, flagged=True).all()
    
    # Get reference documents
    reference_docs = ReferenceDocument.query.all()
    
    return render_template('admin.html', history=all_results, flagged=flagged_results, references=reference_docs)


@app.route('/admin/upload-org-reference', methods=['POST'])
def upload_organization_reference():
    """Admin endpoint to upload organization-specific reference documents (documents that should not be edited)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    if not user.organization_name:
        return jsonify({'error': 'User must be part of an organization'}), 400
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Validate file format
        allowed_extensions = {'jpg', 'jpeg', 'png', 'bmp', 'pdf'}
        file_ext = file.filename.rsplit('.', 1)[1].lower()
        
        if file_ext not in allowed_extensions:
            return jsonify({'error': f'File type not allowed. Allowed: {", ".join(allowed_extensions)}'}), 400
        
        # Generate unique filename with org prefix
        filename = secure_filename(file.filename)
        filename_with_org = f"{user.organization_name}_{datetime.datetime.utcnow().timestamp()}_{filename}"
        filepath = os.path.join(app.config['ORIGINALS_FOLDER'], filename_with_org)
        file.save(filepath)
        
        # Handle PDF conversion if needed
        if file_ext.lower() == 'pdf':
            if convert_from_path is not None:
                try:
                    pages = convert_from_path(filepath, first_page=1, last_page=1)
                    if pages:
                        temp_png = filepath.replace('.pdf', '.png')
                        pages[0].save(temp_png, 'PNG')
                        os.remove(filepath)
                        filepath = temp_png
                        filename = filename.replace('.pdf', '.png')
                except Exception as e:
                    print(f"PDF conversion warning: {e}")
        
        # Extract embedding
        embedding = feature_extractor.extract_features(filepath, preprocess=True)
        embedding_bytes = pickle.dumps(embedding)
        
        # Get description if provided
        description = request.form.get('description', '')
        should_not_edit = request.form.get('should_not_edit', 'true').lower() == 'true'
        
        # Save to organization-specific reference documents
        org_ref_doc = OrganizationReferenceDocument(
            organization_name=user.organization_name,
            document_name=filename,
            file_path=filepath,
            embedding_data=embedding_bytes,
            should_not_edit=should_not_edit,
            description=description,
            uploaded_by_id=user.id
        )
        db.session.add(org_ref_doc)
        
        # Log action
        log = AuditLog(
            user_id=session.get('user_id'),
            action='UPLOAD_ORG_REFERENCE',
            details=f'Organization {user.organization_name} uploaded reference document: {filename}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Organization reference document "{filename}" uploaded successfully',
            'filename': filename,
            'doc_id': org_ref_doc.id,
            'should_not_edit': should_not_edit
        })
    
    except Exception as e:
        print(f"Organization reference upload error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/admin/list-org-references')
def list_org_references():
    """List all reference documents for the org"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    if not user.organization_name:
        return jsonify({'error': 'User must be part of an organization'}), 400
    
    org_docs = OrganizationReferenceDocument.query.filter_by(
        organization_name=user.organization_name
    ).all()
    
    return jsonify({
        'success': True,
        'documents': [doc.to_dict() for doc in org_docs]
    })


@app.route('/admin/delete-org-reference/<int:doc_id>', methods=['POST'])
def delete_org_reference(doc_id):
    """Delete an organization reference document"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    org_doc = db.session.get(OrganizationReferenceDocument, doc_id)
    if not org_doc:
        return jsonify({'error': 'Document not found'}), 404
    
    if org_doc.organization_name != user.organization_name:
        return jsonify({'error': 'Unauthorized - document belongs to different organization'}), 403
    
    try:
        # Remove file
        if os.path.exists(org_doc.file_path):
            os.remove(org_doc.file_path)
        
        # Remove from database
        db.session.delete(org_doc)
        
        # Log action
        log = AuditLog(
            user_id=user.id,
            action='DELETE_ORG_REFERENCE',
            details=f'Deleted organization reference document: {org_doc.document_name}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Reference document deleted successfully'
        })
    except Exception as e:
        print(f"Delete reference error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/history')
def history():
    """User's personal analysis history - only own uploads"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    results = VerificationResult.query.filter_by(user_id=session.get('user_id')).order_by(VerificationResult.timestamp.desc()).all()
    username = session.get('username', 'User')
    return render_template('history.html', results=results, username=username)


@app.route('/admin/org-references')
def org_references():
    """Admin page for managing organization protected documents"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('org_references.html')


@app.route('/admin/edit-history')
def edit_history_page():
    """Admin page for viewing document edit history"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        flash('Access denied. Admin privileges required.', 'danger')
        return redirect(url_for('index'))
    
    return render_template('edit_history.html')


@app.route('/api/edit-history')
def edit_history_api():
    """Get edit detection history for organization"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    if not user.organization_name:
        return jsonify({'error': 'User must be part of an organization'}), 400
    
    logs = DocumentEditLog.query.filter_by(
        organization_name=user.organization_name
    ).order_by(DocumentEditLog.timestamp.desc()).all()
    
    return jsonify({
        'success': True,
        'edits': [log.to_dict() for log in logs]
    })


@app.route('/admin/edit-details/<int:edit_log_id>')
def edit_details(edit_log_id):
    """Get detailed information about a specific edit"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    edit_log = db.session.get(DocumentEditLog, edit_log_id)
    if not edit_log:
        return jsonify({'error': 'Edit log not found'}), 404
    
    if edit_log.organization_name != user.organization_name:
        return jsonify({'error': 'Unauthorized'}), 403
    
    uploader = db.session.get(User, edit_log.uploader_id)
    
    return jsonify({
        'success': True,
        'edit_log': edit_log.to_dict(),
        'uploader': {
            'username': uploader.username,
            'email': uploader.email
        },
        'heatmap_b64': edit_log.diff_heatmap_b64
    })


# ============================================================================
# CONTEXT-AWARE DOCUMENT POLICE ROUTES
# ============================================================================

@app.route('/api/alerts', methods=['GET'])
def get_alerts():
    """Get all fraud alerts (admin only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    alerts = FraudAlert.query.order_by(FraudAlert.created_at.desc()).limit(100).all()
    return jsonify({
        'success': True,
        'alerts': [alert.to_dict() for alert in alerts]
    })


@app.route('/api/alerts/<int:alert_id>/acknowledge', methods=['POST'])
def acknowledge_alert(alert_id):
    """Mark alert as acknowledged"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    alert = db.session.get(FraudAlert, alert_id)
    if not alert:
        return jsonify({'error': 'Alert not found'}), 404
    
    alert.is_acknowledged = True
    alert.acknowledged_by_id = user.id
    alert.acknowledged_at = datetime.datetime.utcnow()
    alert.notes = request.get_json().get('notes', '')
    
    db.session.commit()
    
    # Audit log
    log = AuditLog(
        user_id=user.id,
        action='ACKNOWLEDGE_ALERT',
        details=f'Acknowledged fraud alert {alert_id}'
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'success': True,
        'alert': alert.to_dict()
    })


@app.route('/api/critical-alerts', methods=['GET'])
def get_critical_alerts():
    """Get only CRITICAL alerts (admin only)"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    critical_alerts = FraudAlert.query.filter_by(
        severity_level='CRITICAL',
        is_acknowledged=False
    ).order_by(FraudAlert.created_at.desc()).all()
    
    return jsonify({
        'success': True,
        'critical_alerts': [alert.to_dict() for alert in critical_alerts],
        'count': len(critical_alerts)
    })


@app.route('/api/categories', methods=['GET'])
def get_categories():
    watcher = DirectoryWatcher()
    categories = watcher.sync_to_db()
    return jsonify({"categories": categories})

@app.route('/api/zero-trust-upload', methods=['POST'])
def zero_trust_upload():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
        
    if 'document' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['document']
    category = request.form.get('category') # e.g., 'Contracts'
    
    if not category:
        return jsonify({'error': 'Category required'}), 400
    
    # 1. Save Suspect
    suspect_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
    file.save(suspect_path)
    
    # 2. Get Master from folder
    master_path = os.path.join("master_references", category, "master_template.pdf")
    if not os.path.exists(master_path):
        cat_dir = os.path.join("master_references", category)
        if os.path.exists(cat_dir):
            files = [f for f in os.listdir(cat_dir) if os.path.isfile(os.path.join(cat_dir, f))]
            if files:
                master_path = os.path.join(cat_dir, files[0])
    
    # 3. Analyze
    analyzer = ForgeryAnalyzer()
    alignment_score = analyzer.check_structural_alignment(suspect_path, master_path)
    
    if alignment_score < 0.98:
        # Generate Heatmap and Log Fraud
        heatmap_dict = generate_difference_heatmap(master_path, suspect_path)
        heatmap_path = heatmap_dict.get('heatmap_b64', '')
        
        log_entry = DocumentEditLog(
            organization_name="System",
            original_filename="master_template",
            uploaded_filename=file.filename,
            uploader_id=session.get('user_id'),
            uploader_office="System",
            similarity_score=float(alignment_score),
            diff_heatmap_b64=heatmap_path
        )
        db.session.add(log_entry)
        db.session.commit()
        
        # Send Alert to Sudo
        admin = User.query.filter_by(is_admin=True).first()
        admin_email = admin.email if admin else "admin@example.com"
        
        user = db.session.get(User, session.get('user_id'))
        office_name = user.username if user else "Unknown User"
        timestamp = datetime.datetime.utcnow().isoformat()
        
        email_service.send_forgery_alert(
            office_name=office_name,
            filename=file.filename,
            timestamp=timestamp,
            similarity_score=float(alignment_score) * 100,
            forged_regions=heatmap_dict.get('changed_regions', 0),
            recipient_email=admin_email,
            changed_regions_b64=heatmap_path
        )
        
        return jsonify({"status": "REJECTED", "reason": "Structural Integrity Failed", "score": float(alignment_score)}), 403
    
    return jsonify({"status": "VERIFIED", "score": float(alignment_score)})

if __name__ == '__main__':
    with app.app_context():
        # Create database tables
        db.create_all()
        
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
            print("Admin user created: admin@example.com / admin123")
        
    app.run(debug=True)
