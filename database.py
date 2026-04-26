"""
Database Models and Configuration
Defines database schema for Document Image Authenticity Verification System
"""

from datetime import datetime
from enum import Enum
import json
import os


class UserRole(Enum):
    """User roles in the system"""
    VIEWER = 'viewer'
    ANALYST = 'analyst'
    ADMIN = 'admin'


class DocumentStatus(Enum):
    """Status of document analysis"""
    PENDING = 'pending'
    PROCESSING = 'processing'
    COMPLETED = 'completed'
    FAILED = 'failed'


class ClassificationResult(Enum):
    """Classification result for a document"""
    AUTHENTIC = 'authentic'
    FORGED = 'forged'
    UNCERTAIN = 'uncertain'


class User:
    """User model"""
    
    _id_counter = 1
    
    def __init__(self, username: str, email: str, password_hash: str, 
                 role: UserRole = UserRole.ANALYST):
        """
        Initialize user
        
        Args:
            username: Unique username
            email: User email
            password_hash: Hashed password
            role: User role (default: ANALYST)
        """
        self.user_id = User._id_counter
        User._id_counter += 1
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.is_active = True
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'user_id': self.user_id,
            'username': self.username,
            'email': self.email,
            'role': self.role.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'is_active': self.is_active
        }


class ReferenceDocument:
    """Reference document model"""
    
    _id_counter = 1
    
    def __init__(self, user_id: int, doc_name: str, doc_type: str, 
                 file_path: str, file_format: str, file_size: int,
                 embedding_data: bytes = None):
        """
        Initialize reference document
        
        Args:
            user_id: ID of user who uploaded the document
            doc_name: Name of the document
            doc_type: Type of document (e.g., 'passport', 'certificate')
            file_path: Path to the document file
            file_format: File format (e.g., 'jpg', 'png')
            file_size: File size in bytes
            embedding_data: Feature embedding (optional)
        """
        self.ref_id = ReferenceDocument._id_counter
        ReferenceDocument._id_counter += 1
        self.user_id = user_id
        self.doc_name = doc_name
        self.doc_type = doc_type
        self.file_path = file_path
        self.file_format = file_format
        self.file_size = file_size
        self.embedding_data = embedding_data
        self.embedding_type = 'mobilenet_v2'
        self.created_at = datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'ref_id': self.ref_id,
            'user_id': self.user_id,
            'doc_name': self.doc_name,
            'doc_type': self.doc_type,
            'file_path': self.file_path,
            'file_format': self.file_format,
            'file_size': self.file_size,
            'embedding_type': self.embedding_type,
            'created_at': self.created_at.isoformat()
        }


class Document:
    """Document (to be analyzed) model"""
    
    _id_counter = 1
    
    def __init__(self, user_id: int, file_path: str, file_format: str, 
                 file_size: int, status: DocumentStatus = DocumentStatus.PENDING):
        """
        Initialize document
        
        Args:
            user_id: ID of user who uploaded the document
            file_path: Path to the document file
            file_format: File format
            file_size: File size in bytes
            status: Analysis status
        """
        self.doc_id = Document._id_counter
        Document._id_counter += 1
        self.user_id = user_id
        self.file_path = file_path
        self.file_format = file_format
        self.file_size = file_size
        self.status = status
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'doc_id': self.doc_id,
            'user_id': self.user_id,
            'file_path': self.file_path,
            'file_format': self.file_format,
            'file_size': self.file_size,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


class AnalysisResult:
    """Analysis result model"""
    
    _id_counter = 1
    
    def __init__(self, doc_id: int, ref_id: int, similarity_score: float,
                 confidence_level: float, classification: ClassificationResult,
                 analysis_time: int = 0):
        """
        Initialize analysis result
        
        Args:
            doc_id: ID of analyzed document
            ref_id: ID of reference document
            similarity_score: Similarity score (0-1)
            confidence_level: Confidence level (0-1)
            classification: Classification result
            analysis_time: Time taken for analysis (ms)
        """
        self.result_id = AnalysisResult._id_counter
        AnalysisResult._id_counter += 1
        self.doc_id = doc_id
        self.ref_id = ref_id
        self.similarity_score = similarity_score
        self.confidence_level = confidence_level
        self.classification = classification
        self.analysis_time = analysis_time
        self.heatmap_path = None
        self.created_at = datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'result_id': self.result_id,
            'doc_id': self.doc_id,
            'ref_id': self.ref_id,
            'similarity_score': self.similarity_score,
            'confidence_level': self.confidence_level,
            'classification': self.classification.value,
            'analysis_time': self.analysis_time,
            'heatmap_path': self.heatmap_path,
            'created_at': self.created_at.isoformat()
        }


class FeatureVector:
    """Feature vector model"""
    
    _id_counter = 1
    
    def __init__(self, doc_id: int = None, ref_id: int = None, 
                 vector_data: bytes = None, vector_type: str = 'mobilenet_v2',
                 vector_dimension: int = 512):
        """
        Initialize feature vector
        
        Args:
            doc_id: ID of document (optional)
            ref_id: ID of reference document (optional)
            vector_data: Serialized vector data
            vector_type: Type of vector (default: mobilenet_v2)
            vector_dimension: Dimension of vector
        """
        self.vector_id = FeatureVector._id_counter
        FeatureVector._id_counter += 1
        self.doc_id = doc_id
        self.ref_id = ref_id
        self.vector_data = vector_data
        self.vector_type = vector_type
        self.vector_dimension = vector_dimension
        self.computed_at = datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'vector_id': self.vector_id,
            'doc_id': self.doc_id,
            'ref_id': self.ref_id,
            'vector_type': self.vector_type,
            'vector_dimension': self.vector_dimension,
            'computed_at': self.computed_at.isoformat()
        }


class AuditLog:
    """Audit log model for compliance tracking"""
    
    _id_counter = 1
    
    def __init__(self, user_id: int, action: str, description: str = '',
                 ip_address: str = '0.0.0.0', status: str = 'success'):
        """
        Initialize audit log entry
        
        Args:
            user_id: ID of user performing the action
            action: Action performed
            description: Detailed description
            ip_address: IP address of user
            status: Action status (success/failure)
        """
        self.log_id = AuditLog._id_counter
        AuditLog._id_counter += 1
        self.user_id = user_id
        self.action = action
        self.description = description
        self.ip_address = ip_address
        self.status = status
        self.action_time = datetime.now()
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'log_id': self.log_id,
            'user_id': self.user_id,
            'action': self.action,
            'description': self.description,
            'ip_address': self.ip_address,
            'status': self.status,
            'action_time': self.action_time.isoformat()
        }


class DatabaseManager:
    """Manages in-memory database for the system"""
    
    def __init__(self):
        """Initialize database manager"""
        self.users = {}
        self.reference_documents = {}
        self.documents = {}
        self.analysis_results = {}
        self.feature_vectors = {}
        self.audit_logs = {}
    
    # User methods
    def add_user(self, user: User) -> int:
        """Add user to database"""
        self.users[user.user_id] = user
        return user.user_id
    
    def get_user(self, user_id: int) -> User:
        """Get user by ID"""
        return self.users.get(user_id)
    
    def get_user_by_email(self, email: str) -> User:
        """Get user by email"""
        for user in self.users.values():
            if user.email == email:
                return user
        return None
    
    def get_all_users(self) -> list:
        """Get all users"""
        return list(self.users.values())
    
    # Reference document methods
    def add_reference_document(self, ref_doc: ReferenceDocument) -> int:
        """Add reference document"""
        self.reference_documents[ref_doc.ref_id] = ref_doc
        return ref_doc.ref_id
    
    def get_reference_document(self, ref_id: int) -> ReferenceDocument:
        """Get reference document by ID"""
        return self.reference_documents.get(ref_id)
    
    def get_reference_documents_by_user(self, user_id: int) -> list:
        """Get all reference documents for a user"""
        return [d for d in self.reference_documents.values() if d.user_id == user_id]
    
    def get_reference_documents_by_type(self, doc_type: str) -> list:
        """Get reference documents by type"""
        return [d for d in self.reference_documents.values() if d.doc_type == doc_type]
    
    def delete_reference_document(self, ref_id: int) -> bool:
        """Delete reference document"""
        if ref_id in self.reference_documents:
            del self.reference_documents[ref_id]
            return True
        return False
    
    # Document methods
    def add_document(self, document: Document) -> int:
        """Add document"""
        self.documents[document.doc_id] = document
        return document.doc_id
    
    def get_document(self, doc_id: int) -> Document:
        """Get document by ID"""
        return self.documents.get(doc_id)
    
    def get_documents_by_user(self, user_id: int) -> list:
        """Get all documents for a user"""
        return [d for d in self.documents.values() if d.user_id == user_id]
    
    def update_document_status(self, doc_id: int, status: DocumentStatus) -> bool:
        """Update document status"""
        if doc_id in self.documents:
            self.documents[doc_id].status = status
            self.documents[doc_id].updated_at = datetime.now()
            return True
        return False
    
    # Analysis result methods
    def add_analysis_result(self, result: AnalysisResult) -> int:
        """Add analysis result"""
        self.analysis_results[result.result_id] = result
        return result.result_id
    
    def get_analysis_result(self, result_id: int) -> AnalysisResult:
        """Get analysis result by ID"""
        return self.analysis_results.get(result_id)
    
    def get_analysis_results_by_document(self, doc_id: int) -> list:
        """Get all analysis results for a document"""
        return [r for r in self.analysis_results.values() if r.doc_id == doc_id]
    
    def get_analysis_results_by_user(self, user_id: int) -> list:
        """Get all analysis results for a user"""
        doc_ids = [d.doc_id for d in self.get_documents_by_user(user_id)]
        return [r for r in self.analysis_results.values() if r.doc_id in doc_ids]
    
    # Audit log methods
    def add_audit_log(self, log: AuditLog) -> int:
        """Add audit log entry"""
        self.audit_logs[log.log_id] = log
        return log.log_id
    
    def get_audit_logs_by_user(self, user_id: int) -> list:
        """Get audit logs for a user"""
        return [l for l in self.audit_logs.values() if l.user_id == user_id]
    
    def get_audit_logs_by_action(self, action: str) -> list:
        """Get audit logs for an action"""
        return [l for l in self.audit_logs.values() if l.action == action]
    
    def get_all_audit_logs(self) -> list:
        """Get all audit logs"""
        return sorted(self.audit_logs.values(), key=lambda x: x.action_time, reverse=True)
    
    # Feature vector methods
    def add_feature_vector(self, fv: FeatureVector) -> int:
        """Add feature vector"""
        self.feature_vectors[fv.vector_id] = fv
        return fv.vector_id
    
    def get_feature_vectors_by_document(self, doc_id: int) -> list:
        """Get feature vectors for a document"""
        return [v for v in self.feature_vectors.values() if v.doc_id == doc_id]
    
    def get_feature_vectors_by_reference(self, ref_id: int) -> list:
        """Get feature vectors for a reference document"""
        return [v for v in self.feature_vectors.values() if v.ref_id == ref_id]
    
    # Statistics methods
    def get_system_statistics(self) -> dict:
        """Get system statistics"""
        return {
            'total_users': len(self.users),
            'total_documents': len(self.documents),
            'total_reference_documents': len(self.reference_documents),
            'total_analysis': len(self.analysis_results),
            'total_audit_logs': len(self.audit_logs),
            'documents_by_status': {
                status.value: len([d for d in self.documents.values() if d.status == status])
                for status in DocumentStatus
            },
            'documents_by_classification': {
                c.value: len([r for r in self.analysis_results.values() if r.classification == c])
                for c in ClassificationResult
            }
        }
