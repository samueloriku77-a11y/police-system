-- ============================================================================
-- Document Image Authenticity Verification System (DIAVS)
-- MySQL Database Schema
-- Version: 1.0
-- Created: February 23, 2026
-- ============================================================================

-- Drop existing database if it exists (for fresh installation)
DROP DATABASE IF EXISTS document_forgery_db;

-- Create the database
CREATE DATABASE document_forgery_db
CHARACTER SET utf8mb4
COLLATE utf8mb4_unicode_ci;

-- Use the database
USE document_forgery_db;

-- ============================================================================
-- TABLE: users
-- Purpose: Store user accounts, roles, and authentication data
-- ============================================================================
CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_email (email),
    INDEX idx_is_admin (is_admin)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: reference_documents
-- Purpose: Store original reference documents for comparison
-- ============================================================================
CREATE TABLE reference_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    file_path VARCHAR(512) NOT NULL,
    embedding_data LONGBLOB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_name (name),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: verification_results
-- Purpose: Store results of document analysis
-- ============================================================================
CREATE TABLE verification_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    filename VARCHAR(255) NOT NULL,
    similarity FLOAT NOT NULL,
    status VARCHAR(50) NOT NULL COMMENT 'AUTHENTIC, UNCERTAIN, or FORGED',
    closest_match VARCHAR(255),
    flagged BOOLEAN DEFAULT FALSE,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_timestamp (timestamp),
    INDEX idx_status (status),
    INDEX idx_flagged (flagged),
    INDEX idx_similarity (similarity)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: audit_logs
-- Purpose: Track all system actions for compliance and auditing
-- ============================================================================
CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    action VARCHAR(255) NOT NULL,
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- TABLE: feature_vectors
-- Purpose: Cache extracted feature embeddings for performance
-- ============================================================================
CREATE TABLE feature_vectors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT,
    embedding_data LONGBLOB NOT NULL,
    extraction_method VARCHAR(50) DEFAULT 'MobileNetV2',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_document_id (document_id),
    INDEX idx_extraction_method (extraction_method)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- INSERT INITIAL DATA
-- ============================================================================

-- Create default admin user
-- Email: admin@example.com
-- Password: admin123 (SHA-256 hash)
INSERT INTO users (username, email, password_hash, is_admin) VALUES (
    'admin',
    'admin@example.com',
    '240be518fabd2724ddb6f04eeb1da5967448d7e1c33ddef2d73331bde2a6189',
    TRUE
);

-- ============================================================================
-- CREATE VIEWS FOR REPORTING
-- ============================================================================

-- View: Recent Analysis Results
CREATE VIEW view_recent_analysis AS
SELECT 
    vr.id,
    vr.timestamp,
    u.username,
    u.email,
    vr.filename,
    vr.status,
    vr.similarity,
    vr.closest_match,
    vr.flagged,
    CASE 
        WHEN vr.similarity >= 0.85 THEN 'AUTHENTIC'
        WHEN vr.similarity >= 0.70 THEN 'UNCERTAIN'
        ELSE 'FORGED'
    END as classification
FROM verification_results vr
JOIN users u ON vr.user_id = u.id
ORDER BY vr.timestamp DESC;

-- View: Flagged Cases Summary
CREATE VIEW view_flagged_cases AS
SELECT 
    vr.id,
    vr.timestamp,
    u.username,
    vr.filename,
    vr.status,
    vr.similarity,
    vr.closest_match,
    COUNT(*) OVER () as total_flagged
FROM verification_results vr
JOIN users u ON vr.user_id = u.id
WHERE vr.flagged = TRUE
ORDER BY vr.timestamp DESC;

-- View: User Activity Summary
CREATE VIEW view_user_activity AS
SELECT 
    u.id,
    u.username,
    u.email,
    u.is_admin,
    COUNT(vr.id) as total_analyses,
    COUNT(CASE WHEN vr.flagged = TRUE THEN 1 END) as flagged_cases,
    MAX(vr.timestamp) as last_analysis,
    u.created_at as user_created_at
FROM users u
LEFT JOIN verification_results vr ON u.id = vr.user_id
GROUP BY u.id;

-- View: Analysis Statistics
CREATE VIEW view_analysis_statistics AS
SELECT 
    CURDATE() as analysis_date,
    COUNT(*) as total_analyses,
    COUNT(CASE WHEN status = 'AUTHENTIC' THEN 1 END) as authentic_count,
    COUNT(CASE WHEN status = 'UNCERTAIN' THEN 1 END) as uncertain_count,
    COUNT(CASE WHEN status = 'FORGED' THEN 1 END) as forged_count,
    AVG(similarity) as avg_similarity,
    COUNT(CASE WHEN flagged = TRUE THEN 1 END) as flagged_count
FROM verification_results
WHERE DATE(timestamp) = CURDATE();

-- ============================================================================
-- CREATE INDEXES FOR PERFORMANCE
-- ============================================================================

-- Composite indexes for common queries
CREATE INDEX idx_user_timestamp ON verification_results(user_id, timestamp DESC);
CREATE INDEX idx_status_similarity ON verification_results(status, similarity DESC);
CREATE INDEX idx_flagged_timestamp ON verification_results(flagged, timestamp DESC);

-- ============================================================================
-- VERIFY INSTALLATION
-- ============================================================================

-- Display all tables
SELECT 'document_forgery_db Setup Complete!' as status;
SELECT COUNT(*) as table_count FROM information_schema.tables 
WHERE table_schema = 'document_forgery_db';

-- Display admin user
SELECT id, username, email, is_admin, created_at FROM users LIMIT 1;

-- ============================================================================
-- END OF SCHEMA DEFINITION
-- ============================================================================
