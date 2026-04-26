"""
Professional Email Service with SMTP Integration
Supports multiple email providers: Gmail, SendGrid, Office365, Custom SMTP
"""
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import logging

logger = logging.getLogger(__name__)

class EmailService:
    """Email service handler with support for multiple SMTP providers"""
    
    # SMTP Configuration for popular providers
    PROVIDERS = {
        'gmail': {
            'smtp_server': 'smtp.gmail.com',
            'port': 587,
            'tls': True
        },
        'outlook': {
            'smtp_server': 'smtp-mail.outlook.com',
            'port': 587,
            'tls': True
        },
        'office365': {
            'smtp_server': 'smtp.office365.com',
            'port': 587,
            'tls': True
        },
        'sendgrid': {
            'smtp_server': 'smtp.sendgrid.net',
            'port': 587,
            'tls': True
        },
        'custom': {
            'smtp_server': os.getenv('SMTP_SERVER', 'localhost'),
            'port': int(os.getenv('SMTP_PORT', '587')),
            'tls': os.getenv('SMTP_TLS', 'True').lower() == 'true'
        }
    }
    
    def __init__(self):
        """Initialize email service with environment variables"""
        self.email_provider = os.getenv('EMAIL_PROVIDER', 'custom').lower()
        self.sender_email = os.getenv('SMTP_USER', 'noreply@forgerysystem.com')
        self.sender_password = os.getenv('SMTP_PASSWORD', '')
        
        # Get provider config
        if self.email_provider not in self.PROVIDERS:
            logger.warning(f"Unknown email provider: {self.email_provider}, using custom")
            self.email_provider = 'custom'
        
        self.provider_config = self.PROVIDERS[self.email_provider]
        self.smtp_server = self.provider_config['smtp_server']
        self.smtp_port = self.provider_config['port']
        self.use_tls = self.provider_config['tls']
        
    def send_email(self, to_email, subject, html_body, plain_text_body=None, attachments=None):
        """
        Send email via configured SMTP server
        
        Args:
            to_email (str): Recipient email address
            subject (str): Email subject
            html_body (str): HTML formatted email body
            plain_text_body (str): Plain text fallback
            attachments (list): List of file paths to attach
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        try:
            if not self.sender_password:
                logger.error("SMTP_PASSWORD not configured. Email not sent.")
                return False
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = self.sender_email
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Add text alternatives
            if plain_text_body:
                msg.attach(MIMEText(plain_text_body, 'plain'))
            msg.attach(MIMEText(html_body, 'html'))
            
            # Add attachments if provided
            if attachments:
                for file_path in attachments:
                    if os.path.exists(file_path):
                        self._attach_file(msg, file_path)
            
            # Send via SMTP
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=10) as server:
                if self.use_tls:
                    server.starttls()
                
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email}")
            return True
            
        except smtplib.SMTPAuthenticationError:
            logger.error(f"SMTP Authentication failed for {self.email_provider}. Check SMTP_USER and SMTP_PASSWORD.")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False
    
    def _attach_file(self, msg, file_path):
        """Attach file to email message"""
        try:
            with open(file_path, 'rb') as attachment:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(attachment.read())
            
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename= {os.path.basename(file_path)}')
            msg.attach(part)
        except Exception as e:
            logger.warning(f"Failed to attach file {file_path}: {e}")
    
    def send_forgery_alert(self, office_name, filename, timestamp, similarity_score, 
                          forged_regions, recipient_email, full_results=None, changed_regions_b64=None):
        """
        Send forgery detection alert email
        
        Args:
            office_name (str): Name of office/user uploading
            filename (str): Name of flagged document
            timestamp (str): When detection occurred
            similarity_score (float): Similarity percentage (0-100)
            forged_regions (int): Number of suspect regions
            recipient_email (str): Where to send alert
            full_results (dict): Additional analysis results
            changed_regions_b64 (str): Base64 encoded heatmap image
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"🚨 SECURITY ALERT: Document Forgery Detected - {filename}"
        
        # HTML body for rich formatting
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; border-left: 5px solid #d32f2f;">
                    <h2 style="color: #d32f2f; margin-top: 0;">🚨 SECURITY ALERT</h2>
                    
                    <p><strong>Document Forgery Detected</strong></p>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Source:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{office_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Document:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{filename}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Timestamp:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{timestamp}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Similarity Score:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #d32f2f;"><strong>{similarity_score:.2f}%</strong></td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Forged Regions:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{forged_regions} region(s) detected</td>
                        </tr>
                        {f'''<tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Classification:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{full_results.get("status", "N/A")}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Confidence:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{full_results.get("confidence", 0)*100:.1f}%</td>
                        </tr>''' if full_results else ''}
                    </table>
                    
                    <p style="margin-top: 20px; color: #555;">
                        <strong>Action Required:</strong> Please log into the system immediately and access the 
                        <strong>Tracker Dashboard</strong> to review detailed evidence and visual proof.
                    </p>
                    
                    {f'<p style="color: #d32f2f;"><strong>Heatmap Preview:</strong> Changed regions have been highlighted in the attached visual evidence.</p>' if changed_regions_b64 else ''}
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated security alert from the Document Forgery Detection System.
                        Do not reply to this email.
                    </p>
                </div>
            </body>
        </html>
        """
        
        # Plain text fallback
        plain_text_body = f"""
SECURITY ALERT: Document Forgery Detected

Source: {office_name}
Document: {filename}
Timestamp: {timestamp}
Similarity Score: {similarity_score:.2f}%
Forged Regions: {forged_regions} region(s)

{f"Full Results: Classification={full_results.get('status', 'N/A')}, Confidence={full_results.get('confidence', 0)*100:.1f}%" if full_results else ""}

Please log into the Tracker Dashboard to review detailed evidence.

---
Automated Security Alert
        """
        
        return self.send_email(recipient_email, subject, html_body, plain_text_body)
    
    def send_upload_confirmation(self, recipient_email, filename, office_name, timestamp):
        """
        Send upload confirmation email to organization user
        
        Args:
            recipient_email (str): User's email
            filename (str): Uploaded document name
            office_name (str): Office/branch name
            timestamp (str): Upload timestamp
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"Document Upload Received - {filename}"
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #f5f5f5;">
                <div style="max-width: 600px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; border-left: 5px solid #1976d2;">
                    <h2 style="color: #1976d2; margin-top: 0;">✓ Document Uploaded Successfully</h2>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Office:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{office_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Document:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{filename}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Upload Time:</strong></td>
                            <td style="padding: 8px; border-bottom: 1px solid #ddd;">{timestamp}</td>
                        </tr>
                    </table>
                    
                    <p style="margin-top: 20px; color: #555;">
                        Your document has been successfully uploaded to the server for processing. 
                        The analysis results will be routed to your organization's headquarters administrator.
                    </p>
                    
                    <p style="color: #555;">
                        Please contact your organization admin for detailed analysis reports and findings.
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        Document Forgery Detection System
                    </p>
                </div>
            </body>
        </html>
        """
        
        plain_text_body = f"""
Document Upload Confirmation

Office: {office_name}
Document: {filename}
Upload Time: {timestamp}

Your document has been successfully uploaded to the server for processing.
Analysis results will be routed to your organization's headquarters administrator.

Please contact your organization admin for detailed analysis reports.

---
Document Forgery Detection System
        """
        
        return self.send_email(recipient_email, subject, html_body, plain_text_body)
    
    def send_edit_detection_email(self, organization_name, uploader_username, uploader_office, 
                                  original_filename, uploaded_filename, similarity_score, 
                                  changed_regions, change_percentage, recipient_email, heatmap_b64=None,
                                  forged_text_regions=None, text_visualization_b64=None):
        """
        Send email alert when a document edit is detected with forged text coordinates
        
        Args:
            organization_name (str): Organization name
            uploader_username (str): Username of who uploaded the edited document
            uploader_office (str): Office/branch name
            original_filename (str): Name of the original reference document
            uploaded_filename (str): Name of the uploaded edited document
            similarity_score (float): Similarity between original and edited (0-1)
            changed_regions (int): Number of changed regions detected
            change_percentage (float): Percentage of document that changed
            recipient_email (str): Admin email to notify
            heatmap_b64 (str): Base64 encoded heatmap image (optional)
            forged_text_regions (list): List of dicts with x, y, width, height, forgery_score (optional)
            text_visualization_b64 (str): Base64 encoded image with forged text marked (optional)
            
        Returns:
            bool: True if sent successfully
        """
        subject = f"⚠️ DOCUMENT EDIT DETECTED: {original_filename}"
        
        # Build forged text regions table HTML
        forged_text_html = ""
        if forged_text_regions and len(forged_text_regions) > 0:
            forged_text_html = """
                    <div style="background-color: #ffebee; padding: 15px; border-radius: 4px; border-left: 4px solid #d32f2f; margin: 15px 0;">
                        <p style="margin: 0 0 10px 0; color: #c62828;"><strong>🔴 FORGED TEXT REGIONS DETECTED ({} locations)</strong></p>
                        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                            <thead>
                                <tr style="background-color: #ffcdd2;">
                                    <th style="padding: 8px; text-align: left; border: 1px solid #ef9a9a;">Region #</th>
                                    <th style="padding: 8px; text-align: left; border: 1px solid #ef9a9a;">Location (X, Y)</th>
                                    <th style="padding: 8px; text-align: left; border: 1px solid #ef9a9a;">Size (W × H)</th>
                                    <th style="padding: 8px; text-align: left; border: 1px solid #ef9a9a;">Confidence</th>
                                </tr>
                            </thead>
                            <tbody>
            """.format(len(forged_text_regions))
            
            for i, region in enumerate(forged_text_regions, 1):
                x, y = region.get('x', 0), region.get('y', 0)
                w, h = region.get('width', 0), region.get('height', 0)
                score = region.get('forgery_score', 0)
                
                forged_text_html += f"""
                                <tr>
                                    <td style="padding: 8px; border: 1px solid #ef9a9a;"><strong>#{i}</strong></td>
                                    <td style="padding: 8px; border: 1px solid #ef9a9a;"><code>({x}, {y})</code></td>
                                    <td style="padding: 8px; border: 1px solid #ef9a9a;"><code>{w}×{h}px</code></td>
                                    <td style="padding: 8px; border: 1px solid #ef9a9a;"><strong style="color: #d32f2f;">{score:.1f}%</strong></td>
                                </tr>
                """
            
            forged_text_html += """
                            </tbody>
                        </table>
                    </div>
            """
        
        html_body = f"""
        <html>
            <body style="font-family: Arial, sans-serif; background-color: #fff3cd;">
                <div style="max-width: 700px; margin: 20px auto; background-color: white; padding: 20px; border-radius: 8px; border-left: 5px solid #ff9800;">
                    <h2 style="color: #ff9800; margin-top: 0;">⚠️ DOCUMENT EDIT ALERT</h2>
                    
                    <p style="font-size: 14px; color: #333;"><strong>A reference document that should not be edited has been modified.</strong></p>
                    
                    <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Organization:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{organization_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Uploaded By:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong style="color: #d32f2f;">{uploader_username}</strong> ({uploader_office})</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Original Document:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{original_filename}</td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Edited Version:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;">{uploaded_filename}</td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Similarity Score:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong style="color: #ff9800;">{similarity_score*100:.1f}%</strong></td>
                        </tr>
                        <tr>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Changed Regions:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong style="color: #d32f2f;">{changed_regions} region(s)</strong></td>
                        </tr>
                        <tr style="background-color: #f9f9f9;">
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong>Percentage Changed:</strong></td>
                            <td style="padding: 10px; border: 1px solid #ddd;"><strong style="color: #d32f2f;">{change_percentage:.2f}%</strong></td>
                        </tr>
                    </table>
                    
                    {forged_text_html}
                    
                    <div style="background-color: #fff8e1; padding: 15px; border-radius: 4px; border-left: 4px solid #ff9800; margin: 15px 0;">
                        <p style="margin: 0; color: #333;"><strong>Action Required:</strong></p>
                        <ul style="margin: 10px 0 0 20px; color: #555;">
                            <li>Review the forged text locations above (pixel coordinates)</li>
                            <li>See visual evidence in attachments below</li>
                            <li>Verify who made changes and contact them if needed</li>
                            <li>Access the Tracker Dashboard for detailed forensic analysis</li>
                        </ul>
                    </div>
                    
                    {f'<div style="margin: 20px 0; padding: 15px; background-color: #f5f5f5; border-radius: 4px;"><p style="margin: 0 0 10px 0; color: #333;"><strong>📊 Visual Evidence - Changed Regions:</strong></p><img src="data:image/png;base64,{heatmap_b64}" style="max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #ddd;" alt="Heatmap showing changed regions"></div>' if heatmap_b64 else ''}
                    
                    {f'<div style="margin: 20px 0; padding: 15px; background-color: #f5f5f5; border-radius: 4px;"><p style="margin: 0 0 10px 0; color: #333;"><strong>🔴 Visual Evidence - Forged Text Marked:</strong></p><img src="data:image/png;base64,{text_visualization_b64}" style="max-width: 100%; height: auto; border-radius: 4px; border: 1px solid #ddd; background-color: white; padding: 5px;" alt="Text regions with forgeries marked"></div>' if text_visualization_b64 else ''}
                    
                    <p style="color: #666; font-size: 13px;">
                        <strong>Who:</strong> {uploader_username} from {uploader_office}<br>
                        <strong>What:</strong> Edited version of {original_filename} uploaded as {uploaded_filename}<br>
                        <strong>When:</strong> Timestamp available in system logs
                    </p>
                    
                    <hr style="border: none; border-top: 1px solid #ddd; margin: 20px 0;">
                    <p style="color: #999; font-size: 12px; margin: 0;">
                        This is an automated alert from the Document Edit Detection System.
                        Log into your admin panel to review detailed change tracking and forensic analysis.
                    </p>
                </div>
            </body>
        </html>
        """
        
        plain_text_body = f"""
DOCUMENT EDIT ALERT

Organization: {organization_name}
Uploaded By: {uploader_username} ({uploader_office})
Original Document: {original_filename}
Edited Version: {uploaded_filename}
Similarity Score: {similarity_score*100:.1f}%
Changed Regions: {changed_regions} region(s)
Percentage Changed: {change_percentage:.2f}%

FORGED TEXT LOCATIONS:
{chr(10).join([f"  Region {i+1}: ({r['x']}, {r['y']}) - {r['width']}×{r['height']}px - Confidence: {r.get('forgery_score', 0):.1f}%" for i, r in enumerate(forged_text_regions)]) if forged_text_regions else "  None detected"}

Action Required: Review the locations above and verify with the uploader.

---
Document Forgery Detection System
        """
        
        return self.send_email(recipient_email, subject, html_body, plain_text_body)


# Initialize service
email_service = EmailService()
