from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hashlib

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'police_users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    organization_name = db.Column(db.String(120), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    verification_results = db.relationship('VerificationResult', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def set_password(self, password):
        self.password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    def check_password(self, password):
        return self.password_hash == hashlib.sha256(password.encode()).hexdigest()
    
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat()
        }


class VerificationResult(db.Model):
    __tablename__ = 'verification_results'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('police_users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    similarity = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # Authentic, Suspicious, Forged
    document_type = db.Column(db.String(50), nullable=True)  # ID, Certificate, PDF, Document, etc.
    flagged = db.Column(db.Boolean, default=False)
    matched_reference_id = db.Column(db.Integer, db.ForeignKey('reference_documents.id'), nullable=True)  # Which reference was matched
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship
    matched_reference = db.relationship('ReferenceDocument', backref='verification_results')
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'similarity': self.similarity,
            'status': self.status,
            'document_type': self.document_type,
            'flagged': self.flagged,
            'matched_reference_id': self.matched_reference_id,
            'timestamp': self.timestamp.isoformat()
        }


class ReferenceDocument(db.Model):
    __tablename__ = 'reference_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    embedding_data = db.Column(db.LargeBinary, nullable=True)
    document_type = db.Column(db.String(50), nullable=True, index=True)  # ID, Certificate, PDF, Driver License, Passport, etc.
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'file_path': self.file_path,
            'document_type': self.document_type,
            'created_at': self.created_at.isoformat()
        }


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('police_users.id'), nullable=True)
    action = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'details': self.details,
            'timestamp': self.timestamp.isoformat()
        }

class DocumentTrackerLog(db.Model):
    __tablename__ = 'document_tracker_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('police_users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False) # EDITED/FORGED or AUTHENTIC
    similarity_score = db.Column(db.Float, nullable=True)
    forgery_confidence = db.Column(db.Float, nullable=True)
    proof_b64 = db.Column(db.Text(length=16777215), nullable=True) # MEDIUMTEXT up to 16MB
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'filename': self.filename,
            'status': self.status,
            'similarity_score': self.similarity_score,
            'forgery_confidence': self.forgery_confidence,
            'timestamp': self.timestamp.isoformat()
        }


class OrganizationReferenceDocument(db.Model):
    """Stores reference documents uploaded by organization admins - documents that should not be edited"""
    __tablename__ = 'organization_reference_documents'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(120), nullable=False, index=True)
    document_name = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    embedding_data = db.Column(db.LargeBinary, nullable=True)
    should_not_edit = db.Column(db.Boolean, default=True)  # True means any edits should be flagged
    description = db.Column(db.Text, nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey('police_users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_name': self.organization_name,
            'document_name': self.document_name,
            'should_not_edit': self.should_not_edit,
            'description': self.description,
            'created_at': self.created_at.isoformat()
        }


class DocumentEditLog(db.Model):
    """Logs when a reference document is edited, who edited it, and what changed"""
    __tablename__ = 'document_edit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    organization_name = db.Column(db.String(120), nullable=False, index=True)
    ref_document_id = db.Column(db.Integer, db.ForeignKey('organization_reference_documents.id'), nullable=True)
    original_filename = db.Column(db.String(255), nullable=False)
    uploaded_filename = db.Column(db.String(255), nullable=False)
    uploader_id = db.Column(db.Integer, db.ForeignKey('police_users.id'), nullable=False)
    uploader_office = db.Column(db.String(255), nullable=True)  # Office/branch name
    similarity_score = db.Column(db.Float, nullable=False)  # How similar the documents are (0-1)
    changed_regions_count = db.Column(db.Integer, default=0)  # Number of changed regions
    changed_regions_percentage = db.Column(db.Float, nullable=True)  # Percentage of document changed
    diff_heatmap_b64 = db.Column(db.Text(length=16777215), nullable=True)  # Base64 heatmap showing changes
    change_details = db.Column(db.JSON, nullable=True)  # JSON with detailed change info
    email_sent_to_admin = db.Column(db.Boolean, default=False)
    admin_notified_id = db.Column(db.Integer, db.ForeignKey('police_users.id'), nullable=True)  # Which admin was notified
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'organization_name': self.organization_name,
            'original_filename': self.original_filename,
            'uploaded_filename': self.uploaded_filename,
            'uploader_office': self.uploader_office,
            'similarity_score': self.similarity_score,
            'changed_regions_count': self.changed_regions_count,
            'changed_regions_percentage': self.changed_regions_percentage,
            'email_sent_to_admin': self.email_sent_to_admin,
            'timestamp': self.timestamp.isoformat()
        }
