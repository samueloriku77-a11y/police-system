from flask import Flask, request, jsonify, render_template, redirect, url_for, flash, session, make_response

from flask_session import Session
# import cv2  <-- Mocked for demo
import numpy as np
import json
import pickle
import os
from werkzeug.utils import secure_filename

# DUMMY CV2 MOCK FOR UI DEMO
class MockCv2:
    IMREAD_UNCHANGED = 0
    COLOR_BGR2GRAY = 6
    RETR_EXTERNAL = 0
    CHAIN_APPROX_SIMPLE = 1
    def imread(self, *args, **kwargs): return np.zeros((100,100,3))
    def resize(self, img, size, **kwargs): return img
    def cvtColor(self, img, code): return img
    def imencode(self, ext, img, **kwargs): return True, b''
    def waitKey(self, *args): return 0
    def destroyAllWindows(self): pass
    def findContours(self, *args): return [], None
    def boundingRect(self, *args): return 0,0,10,10
    def rectangle(self, *args): pass
    def putText(self, *args): pass

cv2 = MockCv2()

import hashlib
import datetime
from dotenv import load_dotenv
from db import db, User, VerificationResult, AuditLog, ReferenceDocument, DocumentTrackerLog, OrganizationReferenceDocument, DocumentEditLog
from preprocessing import ImagePreprocessor
from feature_extraction import FeatureExtractor, ForgeryDetector
from similarity import SimilarityCalculator
from email_service import email_service
from advanced_forgery_detector import AdvancedForgeryDetector
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

# Initialize modules
from config import MODEL_PATH, MODEL_METADATA_PATH
preprocessor = ImagePreprocessor()
feature_extractor = FeatureExtractor(model_path=MODEL_PATH, metadata_path=MODEL_METADATA_PATH)
similarity_calculator = SimilarityCalculator()
advanced_detector = AdvancedForgeryDetector()  # Multi-stage detector (alignment + embedding + pixel analysis)

from tracker import tracker_bp
app.register_blueprint(tracker_bp)

# Load reference embeddings from database
def generate_difference_heatmap(ref_img_path, upload_img_path):
    """
    Generate a heatmap showing differences between two document images.
    
    Args:
        ref_img_path: Path to reference image
        upload_img_path: Path to uploaded image
        
    Returns:
        dict with 'changed_regions', 'change_percentage', 'heatmap_b64'
    """
    result = {
        'changed_regions': 0,
        'change_percentage': 0.0,
        'heatmap_b64': None
    }
    
    try:
        ref_img = cv2.imread(ref_img_path)
        upload_img = cv2.imread(upload_img_path)
        
        if ref_img is None or upload_img is None:
            return result
        
        # Resize to match
        h, w = ref_img.shape[:2]
        upload_img = cv2.resize(upload_img, (w, h))
        
        # Calculate difference
        diff = cv2.absdiff(ref_img, upload_img)
        gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
        
        # Find changed regions
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result['changed_regions'] = len(contours)
        
        # Calculate percentage of changed pixels
        total_pixels = gray.size
        changed_pixels = np.count_nonzero(thresh)
        result['change_percentage'] = (changed_pixels / total_pixels) * 100
        
        # Create heatmap with highlighted changes
        changed_img = ref_img.copy()
        cv2.drawContours(changed_img, contours, -1, (0, 0, 255), 4)
        
        # Encode as base64
        _, buf = cv2.imencode('.png', changed_img)
        result['heatmap_b64'] = base64.b64encode(buf).decode()
        
        print(f"📊 Heatmap: {result['changed_regions']} regions, {result['change_percentage']:.2f}% changed")
    except Exception as e:
        print(f"⚠️ Heatmap generation error: {e}")
    
    return result


def load_reference_embeddings():
    """Load all reference documents and their embeddings from database"""
    reference_embeddings = {}
    docs = ReferenceDocument.query.all()
    for doc in docs:
        if doc.embedding_data:
            try:
                embedding = pickle.loads(doc.embedding_data)
                reference_embeddings[doc.name] = embedding
            except Exception as e:
                print(f"Error loading embedding for {doc.name}: {e}")
    return reference_embeddings

def detect_document_edits(uploaded_filepath, organization_name, uploader_user):
    """
    Detect if an uploaded document is an edited version of an organization reference document.
    Uses multi-stage analysis: alignment → embedding distance → pixel-level diffing
    
    Args:
        uploaded_filepath: Path to the uploaded document
        organization_name: Organization name
        uploader_user: User object who uploaded the document
        
    Returns:
        dict with keys: 'is_edited', 'ref_doc', 'similarity_score', 'changed_regions', 'heatmap_b64', 'change_percentage'
    """
    result = {
        'is_edited': False,
        'ref_doc': None,
        'similarity_score': 0.0,
        'changed_regions': 0,
        'heatmap_b64': None,
        'change_percentage': 0.0,
        'embedding_distance': None,
        'alignment_success': False,
        'detected_edits': [],
        'forged_text_regions': [],
        'text_visualization_b64': None
    }
    
    if not organization_name:
        return result
    
    try:
        # Get all reference documents for this organization
        ref_docs = OrganizationReferenceDocument.query.filter_by(
            organization_name=organization_name,
            should_not_edit=True
        ).all()
        
        if not ref_docs:
            print(f"📋 No reference documents found for organization: {organization_name}")
            return result
        
        # Load uploaded image
        uploaded_img = cv2.imread(uploaded_filepath)
        if uploaded_img is None:
            print(f"⚠️ Could not load uploaded image: {uploaded_filepath}")
            return result
        
        # Compare with all reference documents using MULTI-STAGE ANALYSIS
        max_similarity = -1.0
        closest_ref_doc = None
        best_results = None
        
        for ref_doc in ref_docs:
            try:
                # Load reference image
                ref_img = cv2.imread(ref_doc.file_path)
                if ref_img is None:
                    continue
                
                print(f"\n  Analyzing: {ref_doc.document_name}")
                
                # ============================================================================
                # STAGE 1: IMAGE ALIGNMENT (Handle rotation, zoom, skew)
                # ============================================================================
                aligned_img, homography = advanced_detector.align_to_blueprint(uploaded_img, ref_img)
                alignment_success = homography is not None
                
                if alignment_success:
                    print(f"    ✓ Alignment successful (homography matrix computed)")
                
                # ============================================================================
                # STAGE 2: EMBEDDING-BASED COMPARISON (Euclidean distance via EfficientNet)
                # ============================================================================
                embedding_dist, vec_suspect, vec_ref = advanced_detector.compare_to_blueprint(
                    aligned_img, 
                    ref_img
                )
                
                if embedding_dist is not None:
                    # Normalize to similarity score (lower distance = higher similarity)
                    # Distance typically 0-2.0, invert to 0-1 scale
                    similarity = max(0.0, 1.0 - (embedding_dist / 3.0))
                    print(f"    📊 Embedding distance: {embedding_dist:.4f} → similarity: {similarity:.4f}")
                else:
                    similarity = 0.0
                
                # ============================================================================
                # STAGE 3: PIXEL-LEVEL ANALYSIS (Blueprint subtraction - exact forgery locations)
                # ============================================================================
                diff_mask, diff_visual, change_regions = advanced_detector.get_diff_mask(
                    aligned_img,
                    ref_img,
                    threshold=30
                )
                
                if diff_mask is not None and len(change_regions) > 0:
                    total_area = ref_img.shape[0] * ref_img.shape[1]
                    changed_area = sum(r['area'] for r in change_regions)
                    change_percent = (changed_area / total_area) * 100 if total_area > 0 else 0
                    print(f"    🔍 Changes detected: {len(change_regions)} regions, {change_percent:.2f}% area")
                    for i, region in enumerate(change_regions[:5]):  # Show top 5
                        print(f"      • Region {i+1}: {region['width']}×{region['height']} at ({region['x']}, {region['y']})")
                else:
                    change_percent = 0.0
                
                # ============================================================================
                # COMBINED SCORING
                # ============================================================================
                # Weight: embedding similarity (60%) + inverse of change % (40%)
                if len(change_regions) > 0:
                    # More changes detected = higher probability of edit
                    edit_score = (similarity * 0.6) + (change_percent / 100 * 0.4)
                else:
                    edit_score = similarity
                
                print(f"    📈 Final score: {edit_score:.4f}")
                
                if edit_score > max_similarity:
                    max_similarity = edit_score
                    closest_ref_doc = ref_doc
                    
                    # ANALYZE TEXT REGIONS - Find specific forged words
                    text_regions = advanced_detector.detect_text_regions(aligned_img)
                    forged_text = []
                    text_viz = None
                    if diff_mask is not None and len(text_regions) > 0:
                        forged_text = advanced_detector.analyze_text_forgeries(aligned_img, ref_img, text_regions, diff_mask)
                        if len(forged_text) > 0:
                            text_viz = advanced_detector.get_forged_words_visualization(aligned_img, forged_text)
                    
                    best_results = {
                        'similarity': similarity,
                        'embedding_distance': embedding_dist,
                        'alignment': alignment_success,
                        'diff_mask': diff_mask,
                        'diff_visual': diff_visual,
                        'change_regions': change_regions,
                        'change_percent': change_percent,
                        'aligned_img': aligned_img,
                        'text_regions': text_regions,
                        'forged_text_regions': forged_text,
                        'text_visualization': text_viz
                    }
                    
            except Exception as e:
                print(f"⚠️ Error analyzing {ref_doc.document_name}: {e}")
                continue
        
        # ============================================================================
        # DECISION: Is it edited?
        # ============================================================================
        EDIT_THRESHOLD = 0.70
        
        if closest_ref_doc and max_similarity > EDIT_THRESHOLD:
            print(f"\n✏️ EDIT DETECTED: {closest_ref_doc.document_name}")
            print(f"   Confidence: {max_similarity:.2%}")
            
            result['is_edited'] = True
            result['ref_doc'] = closest_ref_doc
            result['similarity_score'] = max_similarity
            result['embedding_distance'] = best_results['embedding_distance']
            result['alignment_success'] = best_results['alignment']
            result['detected_edits'] = best_results['change_regions']
            result['change_percentage'] = best_results['change_percent']
            
            # Generate heatmap from the diff visual
            if best_results['diff_visual'] is not None:
                _, buf = cv2.imencode('.png', best_results['diff_visual'])
                result['heatmap_b64'] = base64.b64encode(buf).decode()
            
            result['changed_regions'] = len(best_results['change_regions'])
            
            # Add forged text regions with coordinates
            result['forged_text_regions'] = best_results.get('forged_text_regions', [])
            
            # Generate text visualization heatmap
            if best_results.get('text_visualization') is not None:
                _, buf = cv2.imencode('.png', best_results['text_visualization'])
                result['text_visualization_b64'] = base64.b64encode(buf).decode()
            
            print(f"   📍 Changed regions: {result['changed_regions']}")
            print(f"   📊 Change percentage: {result['change_percentage']:.2f}%")
            print(f"   📝 Forged text regions: {len(result['forged_text_regions'])} regions with coordinates")
        else:
            print(f"\n✓ No significant edits detected (score: {max_similarity:.4f})")
        
        return result
        
    except Exception as e:
        print(f"❌ Error in detect_document_edits: {e}")
        import traceback
        traceback.print_exc()
        return result

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

@app.route('/detect', methods=['POST'])
def detect():
    """Main document verification endpoint"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Handle PDF conversion
        if filename.lower().endswith('.pdf'):
            if convert_from_path is None:
                return jsonify({'error': 'PDF support requires pdf2image + poppler-utils'}), 500
            try:
                pages = convert_from_path(filepath, first_page=1, last_page=1)
                if not pages:
                    return jsonify({'error': 'No pages found in PDF'}), 400
                temp_png = os.path.join(app.config['UPLOAD_FOLDER'], f"pdf_{filename}.png")
                pages[0].save(temp_png, 'PNG')
                filename = f"pdf_{filename}.png"
                filepath = temp_png
                print(f"PDF converted to {filename}")
            except Exception as pdf_err:
                return jsonify({'error': f'PDF conversion failed: {str(pdf_err)}'}), 500
        
        # Load reference embeddings
        reference_embeddings = load_reference_embeddings()
        # No longer required - model works without refs

        
# SKIP content similarity - pure forgery detection only
        # Get document type from filename heuristics (ID, Certificate, etc)
        doc_type = 'ID' if 'id' in filename.lower() else 'CERTIFICATE' if 'cert' in filename.lower() else 'DOCUMENT'
        print(f"📄 Filename type detection: {doc_type}")
        
        # Extract enhanced features using document recognizer (81% accuracy)
        try:
            suspect_embedding, doc_metadata = feature_extractor.extract_enhanced_features(filepath)
            print(f"✅ Document Recognition: {doc_metadata.get('document_type', 'unknown')} (confidence: {doc_metadata.get('confidence', 0):.2%})")
            doc_recognizer_accuracy = doc_metadata.get('model_accuracy', 0)
        except Exception as e:
            print(f"⚠️  Document recognition failed, using standard extraction: {e}")
            suspect_embedding = feature_extractor.extract_features(filepath, preprocess=True)
            doc_metadata = {'document_recognizer_available': False, 'model_accuracy': 0}
            doc_recognizer_accuracy = 0

        # Region-first forgery detection (gets heatmap overlays for the UI)
        forgery_detector = ForgeryDetector()
        forgery_results = forgery_detector.detect_forged_regions(filepath)
        num_regions = len(forgery_results.get('regions', []))
        metrics = forgery_results.get('metrics', {})
        pattern_check = forgery_results.get('pattern_check', False)
        
        # Load reference embeddings explicitly to dictate forgery via baseline tracking
        reference_embeddings = load_reference_embeddings()
        if reference_embeddings:
            sim_res = similarity_calculator.compare_with_references(suspect_embedding, reference_embeddings)
            best_similarity = sim_res['best_similarity']
            
            # The reference document structurally dictates the true authenticity threshold
            classification, confidence = similarity_calculator.classify_document(best_similarity)
            
            # If native anomaly maps absolutely spot forgery boundaries, force the status
            if num_regions > 0 or pattern_check:
                classification = 'FORGED'
                confidence = max(confidence, forgery_results.get('calibrated_prob', 0.8))
                
        else:
            # Fallback pure-region math if their Admin Database is totally empty
            best_similarity = 0.0
            is_forged = num_regions > 1 or pattern_check
            classification = 'FORGED' if is_forged else 'AUTHENTIC'
            
            conf_score = forgery_results.get('forged_ratio', 0.0)
            if metrics:
                conf_score += (metrics.get('ela_norm', 0) * 0.2 + metrics.get('edge_density', 0) * 0.2)
            confidence = min(0.98, max(0.02, conf_score))

        document_type = 'ID' if 'id' in filename.lower() else 'Certificate' if 'cert' in filename.lower() else 'Document'
        
        # Find closest matching reference for tracking
        closest_ref_id = None
        refs = ReferenceDocument.query.all()
        if refs:
            suspect_emb = feature_extractor.extract_features(filepath, preprocess=True)
            max_sim = -1.0
            closest_ref = None
            for doc in refs:
                if doc.embedding_data:
                    try:
                        ref_emb = pickle.loads(doc.embedding_data)
                        norm_product = np.linalg.norm(suspect_emb) * np.linalg.norm(ref_emb)
                        if norm_product > 0:
                            sim = np.dot(suspect_emb, ref_emb) / norm_product
                            if sim > max_sim:
                                max_sim = sim
                                closest_ref = doc
                    except:
                        pass
            if closest_ref:
                closest_ref_id = closest_ref.id
        
        # Save verification node log
        result = VerificationResult(
            user_id=session.get('user_id'),
            filename=filename,
            similarity=float(best_similarity),
            status=classification,
            document_type=document_type,
            flagged=(classification == 'FORGED'),
            matched_reference_id=closest_ref_id
        )
        db.session.add(result)
        db.session.flush()  # Get ID without committing yet
        
        # Cross-reference into Tracker Database seamlessly bypassing lag/autoflush constraints
        if classification == 'FORGED':
            from tracker import send_alert_email
            import datetime
            
            proof = forgery_results.get('annotated_b64') or forgery_results.get('heatmap_b64') or ''
            tracker_log = DocumentTrackerLog(
                user_id=session.get('user_id'),
                filename=filename,
                status='EDITED',
                proof_b64=proof,
                similarity_score=float(best_similarity) * 100,
                forgery_confidence=float(confidence) * 100
            )
            db.session.add(tracker_log)
            
            # Modern SQL 2.0 query to avoid Autoflush memory resets prior to committing
            u_obj = db.session.get(User, session.get('user_id'))
            office_name = u_obj.username if u_obj else "Unknown Node"
            
            uploader = db.session.get(User, session.get('user_id'))
            code_name = request.form.get('code_name', '').strip()
            if uploader and code_name and not uploader.is_admin and uploader.organization_name == code_name:
                hq_admin = db.session.query(User).filter_by(is_admin=True, organization_name=code_name).first()
                if hq_admin:
                    # CHECK FOR DOCUMENT EDITS (NEW FEATURE)
                    print(f"🔍 Checking for document edits in organization: {code_name}")
                    edit_detection = detect_document_edits(filepath, code_name, uploader)
                    
                    if edit_detection['is_edited'] and edit_detection['ref_doc']:
                        print(f"✏️ EDIT DETECTED: {edit_detection['ref_doc'].document_name}")
                        # Log the edit
                        edit_log = DocumentEditLog(
                            organization_name=code_name,
                            ref_document_id=edit_detection['ref_doc'].id,
                            original_filename=edit_detection['ref_doc'].document_name,
                            uploaded_filename=filename,
                            uploader_id=uploader.id,
                            uploader_office=office_name,
                            similarity_score=edit_detection['similarity_score'],
                            changed_regions_count=edit_detection['changed_regions'],
                            changed_regions_percentage=edit_detection['change_percentage'],
                            diff_heatmap_b64=edit_detection['heatmap_b64'],
                            email_sent_to_admin=False,
                            admin_notified_id=hq_admin.id
                        )
                        db.session.add(edit_log)
                        db.session.flush()
                        
                        # Send edit detection email to admin IMMEDIATELY with forged word locations
                        from tracker import send_edit_detection_email
                        email_sent = send_edit_detection_email(
                            organization_name=code_name,
                            uploader_user=uploader,
                            uploader_office=office_name,
                            original_filename=edit_detection['ref_doc'].document_name,
                            uploaded_filename=filename,
                            similarity_score=edit_detection['similarity_score'],
                            changed_regions=edit_detection['changed_regions'],
                            change_percentage=edit_detection['change_percentage'],
                            heatmap_b64=edit_detection['heatmap_b64'],
                            forged_text_regions=edit_detection.get('forged_text_regions', []),
                            text_visualization_b64=edit_detection.get('text_visualization_b64'),
                            recipient_email=hq_admin.email
                        )
                        
                        if email_sent:
                            edit_log.email_sent_to_admin = True
                            db.session.commit()
                        
                        # Also send user confirmation
                        email_service.send_upload_confirmation(
                            recipient_email=uploader.email,
                            filename=filename,
                            office_name=office_name,
                            timestamp=datetime.datetime.utcnow().isoformat()
                        )
                        
                        return jsonify({
                            'message': 'Document uploaded. Edit detected and admin has been notified.',
                            'status': 'uploaded',
                            'edit_detected': True,
                            'edit_similarity': float(edit_detection['similarity_score']),
                            'changed_regions': edit_detection['changed_regions']
                        })
                    
                    full_results = {
                        'status': classification,
                        'confidence': float(confidence),
                        'similarity': best_similarity,
                        'num_regions': num_regions,
                        'document_type': document_type,
                        'matched_reference': closest_ref.name if closest_ref else None
                    }
                    changed_regions_b64 = None
                    if closest_ref and os.path.exists(closest_ref.file_path):
                        try:
                            heatmap_result = generate_difference_heatmap(closest_ref.file_path, filepath)
                            changed_regions_b64 = heatmap_result['heatmap_b64']
                        except Exception as diff_err:
                            print(f"Diff heatmap error: {diff_err}")
                    
                    # Send alert email to HQ Admin
                    send_alert_email(office_name, filename, datetime.datetime.utcnow().isoformat(), float(best_similarity) * 100, num_regions, hq_admin.email, full_results=full_results, changed_regions_b64=changed_regions_b64)
                    
                    # Send upload confirmation email to organization user
                    email_service.send_upload_confirmation(
                        recipient_email=uploader.email,
                        filename=filename,
                        office_name=office_name,
                        timestamp=datetime.datetime.utcnow().isoformat()
                    )
                    
                    db.session.commit()  # Ensure logs saved
                    return jsonify({
                        'message': 'Document successfully uploaded to the server. Analysis results have been routed to your organization headquarters administrator.',
                        'status': 'uploaded'
                    })
            
            # Normal case email
            uploader_email = uploader.email if uploader else None
            send_alert_email(office_name, filename, datetime.datetime.utcnow().isoformat(), float(best_similarity) * 100, num_regions, uploader_email)

        
        # Add audit log with metrics
        metrics_str = {k: f"{v:.3f}" for k, v in metrics.items()}
        log = AuditLog(
            user_id=session.get('user_id'),
            action='DOCUMENT_ANALYZED',
            details=f'File: {filename}, Status: {classification}, Conf: {confidence:.3f}, Regions: {num_regions}, Pattern: {pattern_check}, Metrics: {metrics_str}, Type: {document_type}'
        )

        db.session.add(log)
        db.session.commit()
        
        # Clean up uploaded/temp files
        try:
            os.remove(filepath)
        except (OSError, IOError):
            pass
        if 'temp_png' in locals():
            try:
                os.remove(temp_png)
            except (OSError, IOError):
                pass
        
        similarity_heatmap_b64 = None
        return jsonify({
            'status': classification,
            'confidence': float(confidence),
            'similarity': best_similarity,
            'document_type': document_type,
            'similarity_heatmap': similarity_heatmap_b64,
            'forgery_results': forgery_results,
            'all_similarities': {},
            'document_recognition': {
                'available': doc_metadata.get('document_recognizer_available', False),
                'model_accuracy': f"{doc_recognizer_accuracy*100:.1f}%" if doc_recognizer_accuracy else "N/A",
                'detected_type': doc_metadata.get('document_type', 'unknown'),
                'confidence': doc_metadata.get('confidence', 0),
                'quality': doc_metadata.get('quality_metrics', {}),
                'bbox': doc_metadata.get('bbox', {})
            }
        })


    
    except Exception as e:
        print(f"Detection error: {e}")
        return jsonify({'error': str(e)}), 500


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


@app.route('/admin/upload-original', methods=['POST'])
def upload_original():
    """Admin endpoint to upload original reference documents"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.get(session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
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
        
        # Save file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['ORIGINALS_FOLDER'], filename)
        file.save(filepath)
        
        # Extract embedding
        embedding = feature_extractor.extract_features(filepath, preprocess=True)
        embedding_bytes = pickle.dumps(embedding)
        
        # Detect document type from filename
        filename_lower = filename.lower()
        if 'id' in filename_lower or 'passport' in filename_lower or 'license' in filename_lower:
            doc_type = 'ID'
        elif 'cert' in filename_lower or 'certificate' in filename_lower:
            doc_type = 'Certificate'
        elif 'invoice' in filename_lower:
            doc_type = 'Invoice'
        elif 'contract' in filename_lower:
            doc_type = 'Contract'
        else:
            doc_type = 'Document'
        
        # Save to database
        ref_doc = ReferenceDocument.query.filter_by(name=filename).first()
        if ref_doc:
            ref_doc.file_path = filepath
            ref_doc.embedding_data = embedding_bytes
            ref_doc.document_type = doc_type
        else:
            ref_doc = ReferenceDocument(
                name=filename,
                file_path=filepath,
                embedding_data=embedding_bytes,
                document_type=doc_type
            )
            db.session.add(ref_doc)
        
        # Log action
        log = AuditLog(
            user_id=session.get('user_id'),
            action='UPLOAD_ORIGINAL',
            details=f'Uploaded reference document: {filename}'
        )
        db.session.add(log)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Reference document "{filename}" ({doc_type}) uploaded successfully',
            'filename': filename,
            'document_type': doc_type,
            'doc_id': ref_doc.id
        })
    
    except Exception as e:
        print(f"Upload error: {e}")
        return jsonify({'error': str(e)}), 500


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


@app.route('/admin/delete-original/<int:ref_id>', methods=['POST'])
def delete_original(ref_id):

    """Delete a reference document"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user or not user.is_admin:
        return jsonify({'error': 'Admin privileges required'}), 403
    
    try:
        ref_doc = db.session.get(ReferenceDocument, ref_id)
        if not ref_doc:
            return jsonify({'error': 'Reference document not found'}), 404
        
        # Delete file
        if os.path.exists(ref_doc.file_path):
            os.remove(ref_doc.file_path)
        
        # Log action
        log = AuditLog(
            user_id=session.get('user_id'),
            action='DELETE_ORIGINAL',
            details=f'Deleted reference document: {ref_doc.name}'
        )
        db.session.add(log)
        db.session.delete(ref_doc)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Reference document deleted'})
    
    except Exception as e:
        print(f"Delete error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/flag/<int:case_id>', methods=['POST'])
def flag_case(case_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    result = db.session.get(VerificationResult, case_id)
    if not result:
        return jsonify({'error': 'Case not found'}), 404
    
    result.flagged = True
    log = AuditLog(user_id=session.get('user_id'), action='FLAG_CASE', details=f'Flagged case {case_id}')
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Case flagged for review'})

@app.route('/unflag/<int:case_id>', methods=['POST'])
def unflag_case(case_id):
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    result = db.session.get(VerificationResult, case_id)
    if not result:
        return jsonify({'error': 'Case not found'}), 404
    
    result.flagged = False
    log = AuditLog(user_id=session.get('user_id'), action='UNFLAG_CASE', details=f'Unflagged case {case_id}')
    db.session.add(log)
    db.session.commit()
    
    return jsonify({'success': True, 'message': 'Case unflagged'})

@app.route('/scan/progress', methods=['GET'])
def scan_progress():
    """Real-time scanning progress with heatmap generation simulation"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    progress = request.args.get('progress', type=int, default=0)
    file_hash = request.args.get('file_hash', default='')
    
    # Simulate different stages of scanning
    if progress < 20:
        status = 'Initializing scan...'
        similarity = 0.0
    elif progress < 40:
        status = 'Preprocessing document...'
        similarity = 0.1 + (progress - 20) / 20 * 0.2
    elif progress < 60:
        status = 'Extracting features...'
        similarity = 0.3 + (progress - 40) / 20 * 0.2
    elif progress < 80:
        status = 'Model forgery detection...'
        similarity = 0.5 + (progress - 60) / 20 * 0.25
    elif progress < 95:
        status = 'Generating heatmaps...'
        similarity = 0.75 + (progress - 80) / 15 * 0.2

    else:
        status = 'Finalizing results...'
        similarity = 0.95 + (progress - 95) / 5 * 0.05
    
    return jsonify({
        'progress': progress,
        'status': status,
        'similarity': float(similarity),
        'stage': int(progress / 20)
    })


@app.route('/preprocess', methods=['POST'])
def preprocess_endpoint():
    """Preprocess image and return preprocessed version"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # Preprocess image
        processed_image = preprocessor.preprocess_document(filepath, denoise=True, enhance_contrast=True, normalize=True)
        
        # Convert to uint8 for visualization
        processed_image_8bit = (processed_image * 255).astype(np.uint8)
        
        # Save preprocessed image
        output_filename = f"preprocessed_{filename}"
        output_path = os.path.join(app.config['UPLOAD_FOLDER'], output_filename)
        cv2.imwrite(output_path, processed_image_8bit)
        
        # Convert to base64
        _, buffer = cv2.imencode('.png', processed_image_8bit)
        image_b64 = base64.b64encode(buffer).decode('utf-8')
        
        # Clean up original
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({
            'status': 'success',
            'message': 'Image preprocessed successfully',
            'image': image_b64,
            'filename': output_filename
        })
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/heatmap', methods=['POST'])
def heatmap_endpoint():
    """Generate heatmap from comparison"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    suspect_file = data.get('suspect_file')
    reference_file = data.get('reference_file')
    
    if not suspect_file or not reference_file:
        return jsonify({'error': 'Missing files'}), 400
    
    try:
        suspect_path = os.path.join(app.config['UPLOAD_FOLDER'], suspect_file)
        reference_path = os.path.join(app.config['ORIGINALS_FOLDER'], reference_file)
        
        if not os.path.exists(suspect_path) or not os.path.exists(reference_path):
            return jsonify({'error': 'Files not found'}), 404
        
        # Load and preprocess images
        suspect_image = preprocessor.preprocess_document(suspect_path)
        suspect_8bit = (suspect_image * 255).astype(np.uint8)
        
        reference_image = preprocessor.preprocess_document(reference_path)
        reference_8bit = (reference_image * 255).astype(np.uint8)
        
        # Calculate block similarity and heatmap
        block_scores, _ = similarity_calculator.calculate_block_similarity(
            reference_8bit, suspect_8bit, block_size=64
        )
        
        # Generate colored heatmap
        heatmap = similarity_calculator.generate_heatmap(
            block_scores, suspect_8bit.shape, block_size=64, colormap='hot'
        )
        
        # Convert to base64
        _, buffer = cv2.imencode('.png', heatmap)
        heatmap_b64 = base64.b64encode(buffer).decode('utf-8')
        
        return jsonify({
            'success': True,
            'heatmap': heatmap_b64,
            'message': 'Heatmap generated successfully'
        })
    
    except Exception as e:
        print(f"Heatmap error: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/report/<int:case_id>', methods=['GET'])
def report_endpoint(case_id):
    """Generate/retrieve analysis report with matched reference"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    try:
        # Use explicit query with eager loading to ensure relationship is loaded
        case = db.session.query(VerificationResult).filter_by(id=case_id).first()
        if not case:
            return jsonify({'error': 'Case not found'}), 404
        
        # Get matched reference document if available
        reference_info = None
        if case.matched_reference_id:
            ref_doc = db.session.get(ReferenceDocument, case.matched_reference_id)
            if ref_doc:
                reference_info = {
                    'id': ref_doc.id,
                    'name': ref_doc.name,
                    'document_type': ref_doc.document_type or 'Unknown',
                    'created_at': ref_doc.created_at.isoformat()
                }
        
        # Create comprehensive report
        report_data = {
            'case_id': case.id,
            'filename': case.filename,
            'document_type': case.document_type or 'Unknown',
            'similarity_score': float(case.similarity),
            'classification': case.status,
            'reference_match': reference_info,
            'matched_reference_id': case.matched_reference_id,
            'timestamp': case.timestamp.isoformat(),
            'flagged': case.flagged,
            'analysis_details': {
                'classification_meaning': {
                    'AUTHENTIC': 'Document matches reference with high confidence (≥85%)',
                    'UNCERTAIN': 'Document has moderate match (70-85%)', 
                    'FORGED': 'Document does not match references (<70%)'
                },
                'detection_pipeline': [
                    'Stage 1: Image alignment (ORB keypoint matching)',
                    'Stage 2: Embedding extraction (EfficientNet-B0)',
                    'Stage 3: Euclidean distance comparison',
                    'Stage 4: Pixel-level blueprint subtraction'
                ],
                'methodology': 'Multi-stage forgery detection with image alignment, embedding distance, and pixel diffing',
                'confidence': float(case.similarity),
                'document_type_detected': case.document_type
            }
        }
        
        return jsonify(report_data)
    
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/scan')
def scan_page():
    """Scan page for document analysis with live heatmap generation"""
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('scan.html')


@app.route('/test-heatmap')
def test_heatmap():
    """Test endpoint: generates a heatmap from two reference images"""
    try:
        # Get first two reference documents
        refs = ReferenceDocument.query.all()
        if len(refs) < 2:
            return "Need at least 2 reference documents. Upload more in admin panel.", 400
        
        ref1 = refs[0]
        ref2 = refs[1]
        
        # Build proper file paths
        ref1_path = os.path.join(app.config['ORIGINALS_FOLDER'], ref1.name)
        ref2_path = os.path.join(app.config['ORIGINALS_FOLDER'], ref2.name)
        
        print(f"📁 Testing with: {ref1_path} and {ref2_path}")
        
        if not os.path.exists(ref1_path):
            return f"Reference 1 not found: {ref1_path}", 404
        if not os.path.exists(ref2_path):
            return f"Reference 2 not found: {ref2_path}", 404
        
        print(f"✅ Files exist, generating heatmap...")
        
        image_8bit = (preprocessor.preprocess_document(ref1_path) * 255).astype(np.uint8)
        ref_image_8bit = (preprocessor.preprocess_document(ref2_path) * 255).astype(np.uint8)
        
        print(f"✅ Images loaded: {image_8bit.shape} vs {ref_image_8bit.shape}")
        
        # Calculate block similarity
        block_scores, heatmap_array = similarity_calculator.calculate_block_similarity(
            image_8bit, ref_image_8bit, block_size=64
        )
        
        print(f"✅ Heatmap calculated: {heatmap_array.shape}")
        
        # Convert to 8-bit and colormap
        heatmap_8bit = (heatmap_array * 255).astype(np.uint8)
        heatmap_colored = cv2.applyColorMap(heatmap_8bit, cv2.COLORMAP_HOT)
        
        # Blend with original
        if len(image_8bit.shape) == 2:
            image_rgb = cv2.cvtColor(image_8bit, cv2.COLOR_GRAY2BGR)
        else:
            image_rgb = image_8bit
        
        heatmap_overlay = cv2.addWeighted(image_rgb, 0.6, heatmap_colored, 0.4, 0)
        
        print(f"✅ Overlay created: {heatmap_overlay.shape}")
        
        # Return as PNG
        _, buffer = cv2.imencode('.png', heatmap_overlay)
        response = make_response(buffer.tobytes())
        response.headers['Content-Type'] = 'image/png'
        return response
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n\n{traceback.format_exc()}"
        print(error_msg)
        return error_msg, 500



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


@app.route('/api/compare-documents', methods=['POST'])
def compare_documents_api():
    """
    API endpoint to compare two documents and get detailed analysis.
    Can be used to compare an uploaded document with a reference document.
    """
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = db.session.get(User, session.get('user_id'))
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    try:
        # Get file from request
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Get reference doc ID from form
        ref_doc_id = request.form.get('ref_doc_id')
        if not ref_doc_id:
            return jsonify({'error': 'Reference document ID required'}), 400
        
        # Get reference document
        ref_doc = db.session.get(OrganizationReferenceDocument, int(ref_doc_id))
        if not ref_doc:
            return jsonify({'error': 'Reference document not found'}), 404
        
        # Check authorization - user must be part of same organization
        if user.organization_name != ref_doc.organization_name or not user.is_admin:
            return jsonify({'error': 'Unauthorized - document belongs to different organization'}), 403
        
        # Save uploaded file
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"compare_{datetime.datetime.utcnow().timestamp()}_{filename}")
        file.save(filepath)
        
        # Handle PDF conversion
        if filename.lower().endswith('.pdf'):
            if convert_from_path is not None:
                try:
                    pages = convert_from_path(filepath, first_page=1, last_page=1)
                    if pages:
                        temp_png = filepath.replace('.pdf', '.png')
                        pages[0].save(temp_png, 'PNG')
                        os.remove(filepath)
                        filepath = temp_png
                except Exception as e:
                    print(f"PDF conversion error: {e}")
        
        # Extract features
        uploaded_embedding = feature_extractor.extract_features(filepath, preprocess=True)
        
        # Load reference embedding
        if not ref_doc.embedding_data:
            return jsonify({'error': 'Reference document embedding not available'}), 400
        
        ref_embedding = pickle.loads(ref_doc.embedding_data)
        
        # Calculate similarity with zero-vector protection
        norm_product = np.linalg.norm(uploaded_embedding) * np.linalg.norm(ref_embedding)
        if norm_product == 0:
            similarity = 0.0
        else:
            similarity = np.dot(uploaded_embedding, ref_embedding) / norm_product
        
        # Generate visual diff using centralized function
        heatmap_result = generate_difference_heatmap(ref_doc.file_path, filepath)
        
        diff_details = {
            'similarity_score': float(similarity),
            'changed_regions': heatmap_result['changed_regions'],
            'change_percentage': heatmap_result['change_percentage'],
            'heatmap_b64': heatmap_result['heatmap_b64']
        }
        
        # Clean up
        try:
            os.remove(filepath)
        except:
            pass
        
        return jsonify({
            'success': True,
            'comparison': {
                'reference_document': ref_doc.to_dict(),
                'similarity_score': diff_details['similarity_score'],
                'changed_regions': diff_details['changed_regions'],
                'change_percentage': diff_details['change_percentage'],
                'heatmap_b64': diff_details['heatmap_b64'],
                'is_edited': similarity > 0.70
            }
        })
    
    except Exception as e:
        print(f"Compare documents error: {e}")
        return jsonify({'error': str(e)}), 500


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
