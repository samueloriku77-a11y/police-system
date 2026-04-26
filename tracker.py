from flask import Blueprint, render_template, request, jsonify, session, flash, redirect, url_for
from db import db, User, DocumentTrackerLog
from email_service import email_service
import os
import logging

logger = logging.getLogger(__name__)

tracker_bp = Blueprint('tracker', __name__, url_prefix='/tracker')

@tracker_bp.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    user = db.session.get(User, session['user_id'])
    if not user or not user.is_admin:
        flash('Access denied. Admin/Police privileges required to access the central Evidence Tracker.', 'danger')
        return redirect(url_for('index'))
        
    logs = db.session.query(DocumentTrackerLog).join(User).filter(User.organization_name == user.organization_name).order_by(DocumentTrackerLog.timestamp.desc()).all()
    
    enriched_logs = []
    for log in logs:
        u = db.session.get(User, log.user_id)
        log_dict = log.to_dict()
        log_dict['username'] = u.username if u else 'Unknown Office'
        log_dict['proof_b64'] = log.proof_b64
        enriched_logs.append(log_dict)
        
    return render_template('tracker_dashboard.html', logs=enriched_logs)

def send_alert_email(office_name, filename, timestamp, similarity_score, forged_regions, uploader_email=None, full_results=None, changed_regions_b64=None):
    """Sends an email alert via configured SMTP when forgery/editing is detected."""
    recipient_email = uploader_email or os.getenv("ADMIN_EMAIL", "admin@organization.com")
    
    success = email_service.send_forgery_alert(
        office_name=office_name,
        filename=filename,
        timestamp=timestamp,
        similarity_score=similarity_score,
        forged_regions=forged_regions,
        recipient_email=recipient_email,
        full_results=full_results,
        changed_regions_b64=changed_regions_b64
    )
    
    if success:
        logger.info(f"Forgery alert email sent to {recipient_email}")
    else:
        logger.error(f"Failed to send forgery alert email to {recipient_email}")


def send_edit_detection_email(organization_name, uploader_user, uploader_office, original_filename, 
                              uploaded_filename, similarity_score, changed_regions, change_percentage, 
                              heatmap_b64, recipient_email, forged_text_regions=None, text_visualization_b64=None):
    """
    Sends an email alert when a document edit is detected with forged text region coordinates.
    
    Args:
        organization_name: Organization name
        uploader_user: User object who uploaded the document
        uploader_office: Office/branch name
        original_filename: Name of original reference document
        uploaded_filename: Name of uploaded edited document
        similarity_score: Similarity between documents (0-1)
        changed_regions: Number of changed regions
        change_percentage: Percentage of document changed
        heatmap_b64: Base64 encoded heatmap image
        recipient_email: Admin email to send to
        forged_text_regions: List of dicts with x, y, width, height, forgery_score for forged text
        text_visualization_b64: Base64 encoded image showing forged text with coordinates
        
    Returns:
        bool: True if email sent successfully
    """
    success = email_service.send_edit_detection_email(
        organization_name=organization_name,
        uploader_username=uploader_user.username,
        uploader_office=uploader_office,
        original_filename=original_filename,
        uploaded_filename=uploaded_filename,
        similarity_score=similarity_score,
        changed_regions=changed_regions,
        change_percentage=change_percentage,
        heatmap_b64=heatmap_b64,
        recipient_email=recipient_email,
        forged_text_regions=forged_text_regions,
        text_visualization_b64=text_visualization_b64
    )
    
    if success:
        logger.info(f"Edit detection email sent to {recipient_email} for {organization_name}")
    else:
        logger.error(f"Failed to send edit detection email to {recipient_email}")
    
    return success
