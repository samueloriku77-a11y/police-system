-- Zero-Trust Document Integrity System - Database Schema for XAMPP
-- Import this file into phpMyAdmin

CREATE DATABASE IF NOT EXISTS `document_forgery_db`;
USE `document_forgery_db`;

-- Drop tables if they already exist to prevent import errors
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS `fraud_alerts`;
DROP TABLE IF EXISTS `forensic_reports`;
DROP TABLE IF EXISTS `protected_zones`;
DROP TABLE IF EXISTS `reference_templates`;
DROP TABLE IF EXISTS `document_types`;
DROP TABLE IF EXISTS `document_edit_logs`;
DROP TABLE IF EXISTS `organization_reference_documents`;
DROP TABLE IF EXISTS `document_tracker_logs`;
DROP TABLE IF EXISTS `audit_logs`;
DROP TABLE IF EXISTS `verification_results`;
DROP TABLE IF EXISTS `reference_documents`;
DROP TABLE IF EXISTS `police_users`;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE `police_users` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `username` varchar(80) NOT NULL,
  `email` varchar(120) NOT NULL,
  `password_hash` varchar(256) NOT NULL,
  `is_admin` tinyint(1) DEFAULT 0,
  `organization_name` varchar(120) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  UNIQUE KEY `email` (`email`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `reference_documents` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(255) NOT NULL,
  `file_path` varchar(512) NOT NULL,
  `embedding_data` longblob,
  `document_type` varchar(50) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_reference_documents_document_type` (`document_type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `verification_results` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `filename` varchar(255) NOT NULL,
  `similarity` float NOT NULL,
  `status` varchar(50) NOT NULL,
  `document_type` varchar(50) DEFAULT NULL,
  `flagged` tinyint(1) DEFAULT 0,
  `matched_reference_id` int(11) DEFAULT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `matched_reference_id` (`matched_reference_id`),
  CONSTRAINT `fk_verification_user` FOREIGN KEY (`user_id`) REFERENCES `police_users` (`id`),
  CONSTRAINT `fk_verification_ref` FOREIGN KEY (`matched_reference_id`) REFERENCES `reference_documents` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `audit_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) DEFAULT NULL,
  `action` varchar(255) NOT NULL,
  `details` text,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `fk_audit_user` FOREIGN KEY (`user_id`) REFERENCES `police_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `document_tracker_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `filename` varchar(255) NOT NULL,
  `status` varchar(50) NOT NULL,
  `similarity_score` float DEFAULT NULL,
  `forgery_confidence` float DEFAULT NULL,
  `proof_b64` mediumtext,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  CONSTRAINT `fk_tracker_user` FOREIGN KEY (`user_id`) REFERENCES `police_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `organization_reference_documents` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_name` varchar(120) NOT NULL,
  `document_name` varchar(255) NOT NULL,
  `file_path` varchar(512) NOT NULL,
  `embedding_data` longblob,
  `should_not_edit` tinyint(1) DEFAULT 1,
  `description` text,
  `uploaded_by_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_org_ref_name` (`organization_name`),
  KEY `uploaded_by_id` (`uploaded_by_id`),
  CONSTRAINT `fk_org_ref_user` FOREIGN KEY (`uploaded_by_id`) REFERENCES `police_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `document_edit_logs` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `organization_name` varchar(120) NOT NULL,
  `ref_document_id` int(11) DEFAULT NULL,
  `original_filename` varchar(255) NOT NULL,
  `uploaded_filename` varchar(255) NOT NULL,
  `uploader_id` int(11) NOT NULL,
  `uploader_office` varchar(255) DEFAULT NULL,
  `similarity_score` float NOT NULL,
  `changed_regions_count` int(11) DEFAULT 0,
  `changed_regions_percentage` float DEFAULT NULL,
  `diff_heatmap_b64` mediumtext,
  `change_details` json DEFAULT NULL,
  `email_sent_to_admin` tinyint(1) DEFAULT 0,
  `admin_notified_id` int(11) DEFAULT NULL,
  `timestamp` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `ix_edit_org_name` (`organization_name`),
  KEY `uploader_id` (`uploader_id`),
  KEY `admin_notified_id` (`admin_notified_id`),
  CONSTRAINT `fk_edit_ref` FOREIGN KEY (`ref_document_id`) REFERENCES `organization_reference_documents` (`id`),
  CONSTRAINT `fk_edit_uploader` FOREIGN KEY (`uploader_id`) REFERENCES `police_users` (`id`),
  CONSTRAINT `fk_edit_admin` FOREIGN KEY (`admin_notified_id`) REFERENCES `police_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `document_types` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `name` varchar(50) NOT NULL,
  `description` text,
  `config_json` json DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_doc_types_name` (`name`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `reference_templates` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `document_type_id` int(11) NOT NULL,
  `template_name` varchar(100) NOT NULL,
  `file_path` varchar(255) NOT NULL,
  `feature_embedding` longblob,
  `version` varchar(20) DEFAULT '1.0',
  `created_by_id` int(11) DEFAULT NULL,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `document_type_id` (`document_type_id`),
  KEY `created_by_id` (`created_by_id`),
  CONSTRAINT `fk_ref_temp_type` FOREIGN KEY (`document_type_id`) REFERENCES `document_types` (`id`),
  CONSTRAINT `fk_ref_temp_user` FOREIGN KEY (`created_by_id`) REFERENCES `police_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `protected_zones` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `document_type_id` int(11) NOT NULL,
  `zone_name` varchar(100) NOT NULL,
  `coordinates` json NOT NULL,
  `similarity_threshold` float DEFAULT 0.95,
  `priority` varchar(20) DEFAULT 'high',
  `description` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `document_type_id` (`document_type_id`),
  CONSTRAINT `fk_zone_type` FOREIGN KEY (`document_type_id`) REFERENCES `document_types` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `forensic_reports` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `user_id` int(11) NOT NULL,
  `document_type_id` int(11) NOT NULL,
  `received_doc_path` varchar(255) NOT NULL,
  `overall_similarity` float NOT NULL,
  `ela_score` float NOT NULL,
  `structural_alignment_score` float NOT NULL,
  `siamese_confidence` float NOT NULL,
  `zone_violations_count` int(11) DEFAULT 0,
  `anomaly_regions_json` json DEFAULT NULL,
  `heatmap_data` mediumtext,
  `zone_heatmap_data` mediumtext,
  `ela_heatmap_data` mediumtext,
  `report_text` mediumtext,
  `alert_severity` varchar(20) DEFAULT 'CLEAN',
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `document_type_id` (`document_type_id`),
  CONSTRAINT `fk_report_user` FOREIGN KEY (`user_id`) REFERENCES `police_users` (`id`),
  CONSTRAINT `fk_report_type` FOREIGN KEY (`document_type_id`) REFERENCES `document_types` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE `fraud_alerts` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `forensic_report_id` int(11) NOT NULL,
  `alert_type` varchar(50) NOT NULL,
  `severity_level` varchar(20) NOT NULL,
  `violated_zones_json` json DEFAULT NULL,
  `description` text NOT NULL,
  `is_acknowledged` tinyint(1) DEFAULT 0,
  `acknowledged_by_id` int(11) DEFAULT NULL,
  `acknowledged_at` datetime DEFAULT NULL,
  `notes` text,
  `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_fraud_alert_report` (`forensic_report_id`),
  KEY `acknowledged_by_id` (`acknowledged_by_id`),
  CONSTRAINT `fk_alert_report` FOREIGN KEY (`forensic_report_id`) REFERENCES `forensic_reports` (`id`),
  CONSTRAINT `fk_alert_user` FOREIGN KEY (`acknowledged_by_id`) REFERENCES `police_users` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insert a default Sudo Admin user (Password is 'admin')
INSERT INTO `police_users` (`username`, `email`, `password_hash`, `is_admin`, `organization_name`) 
VALUES ('admin', 'admin@example.com', SHA2('admin', 256), 1, 'Headquarters');
