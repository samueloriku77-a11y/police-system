# Email Service Configuration Guide

The Document Forgery Detection System now supports professional SMTP email delivery using well-known email providers. This guide explains how to set up each provider.

## Quick Setup

1. Choose your email provider (Gmail, Outlook, Office365, SendGrid, or custom)
2. Obtain your API key or credentials
3. Update your `.env` file with the credentials
4. Test the configuration

## Supported Providers

### 1. Gmail (Recommended for Testing)

**Setup Steps:**
1. Go to [Google Account Security Settings](https://myaccount.google.com/security)
2. Enable 2-Step Verification (if not already enabled)
3. Create an [App Password](https://support.google.com/accounts/answer/185833)
   - Select app: "Mail"
   - Select device: "Windows Computer" (or your device)
   - Copy the 16-character password
4. Update `.env`:
```env
EMAIL_PROVIDER=gmail
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=xxxx xxxx xxxx xxxx
ADMIN_EMAIL=admin@organization.com
```

**Port:** 587 (automatic)
**Protocol:** TLS

### 2. Microsoft Outlook / Office365

**Setup Steps:**
1. Sign in to your Outlook account
2. Ensure your email is on Outlook.com or Office 365
3. Update `.env`:
```env
EMAIL_PROVIDER=outlook
SMTP_USER=your-email@outlook.com
SMTP_PASSWORD=your-password
ADMIN_EMAIL=admin@organization.com
```

Or for Office365:
```env
EMAIL_PROVIDER=office365
SMTP_USER=your-email@company.com
SMTP_PASSWORD=your-password
ADMIN_EMAIL=admin@organization.com
```

**Port:** 587 (automatic)
**Protocol:** TLS

### 3. SendGrid (Best for Production)

**Setup Steps:**
1. Create a [SendGrid account](https://sendgrid.com/)
2. Get your API Key:
   - Navigate to Settings → API Keys
   - Create a new API Key or copy existing one
3. Update `.env`:
```env
EMAIL_PROVIDER=sendgrid
SMTP_USER=apikey
SMTP_PASSWORD=SG.your-actual-api-key-here
ADMIN_EMAIL=admin@organization.com
```

**Port:** 587 (automatic)
**Protocol:** TLS
**Note:** The username is literally "apikey" - this tells SendGrid to authenticate using the API key

### 4. Custom SMTP Server

For corporate or self-hosted email servers:

```env
EMAIL_PROVIDER=custom
SMTP_SERVER=mail.company.com
SMTP_PORT=587
SMTP_TLS=True
SMTP_USER=your-username
SMTP_PASSWORD=your-password
ADMIN_EMAIL=admin@organization.com
```

### 5. Mailgun (Alternative for Production)

```env
EMAIL_PROVIDER=custom
SMTP_SERVER=smtp.mailgun.org
SMTP_PORT=587
SMTP_TLS=True
SMTP_USER=postmaster@yourdomain.mailgun.org
SMTP_PASSWORD=your-mailgun-password
```

## Email Types

The system sends two types of emails:

### 1. Forgery Alert Email
- **Sent to:** Organization HQ Admin and regular users when forgery detected
- **Content:** Security alert with:
  - Similarity score
  - Forged regions detected
  - Analysis confidence level
  - Instructions to check Tracker Dashboard
  - Optional: Changed regions heatmap preview

### 2. Upload Confirmation Email
- **Sent to:** Organization users when document uploaded
- **Content:** Confirmation that upload was received and routed to HQ admin

## Environment Variable Reference

```env
# Email Provider Selection
EMAIL_PROVIDER=gmail           # One of: gmail, outlook, office365, sendgrid, custom

# SMTP Credentials
SMTP_USER=user@example.com     # Email address or API key
SMTP_PASSWORD=your-password    # App password or API key

# Custom SMTP Only
SMTP_SERVER=smtp.example.com   # Server hostname
SMTP_PORT=587                  # Port (usually 587 for TLS)
SMTP_TLS=True                  # Use TLS encryption

# Default Admin Email
ADMIN_EMAIL=admin@org.com      # Fallback email for alerts
```

## Testing the Configuration

### Method 1: Manual Test
```python
from email_service import email_service

# Send test forgery alert
email_service.send_forgery_alert(
    office_name="Test Office",
    filename="test_document.pdf",
    timestamp="2024-01-01T12:00:00",
    similarity_score=85.5,
    forged_regions=3,
    recipient_email="test@example.com",
    full_results={
        'status': 'FORGED',
        'confidence': 0.92,
        'similarity': 0.855,
        'num_regions': 3
    }
)
```

### Method 2: Via Application
1. Log in as a non-admin organization user
2. Upload a document
3. Check your email for the upload confirmation message

### Troubleshooting

| Error | Solution |
|-------|----------|
| `SMTPAuthenticationError` | Check SMTP_USER and SMTP_PASSWORD credentials |
| `Connection timeout` | Verify SMTP_SERVER and SMTP_PORT are correct |
| `TLS error` | Ensure SMTP_TLS=True for port 587 |
| `Email not received` | Check spam folder, verify recipient email is correct |
| `Module not found` | Ensure email_service.py is in the same directory as app.py |

## Security Best Practices

1. **Never commit credentials to version control**
   - Use `.env` file (listed in `.gitignore`)
   - Use `.env.example` for documentation

2. **Use App Passwords instead of account passwords**
   - Gmail: Generate App Password specific to the application
   - Microsoft: Use Application Password

3. **Rotate API Keys regularly**
   - SendGrid, Mailgun: Generate new keys periodically
   - Document rotation dates

4. **Use TLS/SSL encryption**
   - All providers use port 587 with TLS
   - Ensure SMTP_TLS=True in custom configurations

5. **Limit email addresses in code**
   - Admin email should be in `.env`, not hardcoded
   - Sensitive emails come from database, not config

## Email Customization

To modify email templates, edit the HTML and plain text templates in `email_service.py`:

1. **Forgery Alert Email Template:**
   - Location: `send_forgery_alert()` method
   - Modify HTML body and plain_text_body variables

2. **Upload Confirmation Template:**
   - Location: `send_upload_confirmation()` method
   - Modify HTML body and plain_text_body variables

### Template Variables Available:
- `{office_name}` - Name of uploading office/user
- `{filename}` - Name of document
- `{timestamp}` - When action occurred
- `{similarity_score}` - Forgery score percentage
- `{forged_regions}` - Number of altered regions
- `{full_results}` - Complete analysis data

## Support for API Keys

### How API Keys Work:
- **SendGrid API Key:** Acts as password, no username needed (use 'apikey')
- **Mailgun API Key:** Can be used as password with mailgun as username
- **Custom services:** Supports any SMTP username/password combination

### Where to Find API Keys:
- **SendGrid:** Settings → API Keys
- **Mailgun:** Domain Settings → SMTP Credentials
- **Gmail App Password:** Account → Security → App Passwords
- **Microsoft:** Account → Security → Additional Access

## Production Recommendations

1. **Use SendGrid or similar service:**
   - Better deliverability
   - Track email bounces
   - Scalable for high volume
   - Better monitoring

2. **Monitor email delivery:**
   - Enable logging in email_service.py
   - Track failed emails in database
   - Set up alerts for delivery failures

3. **Queue email processing:**
   - Use background tasks for large batches
   - Implement retry logic for failed emails
   - Consider Celery for async processing

4. **Email templates:**
   - Test on multiple clients
   - Include plain text alternative
   - Add footer with unsubscribe link (if needed)

## Log Messages

The email service logs the following:

```
INFO: Email sent successfully to recipient@example.com
ERROR: SMTP Authentication failed for gmail
ERROR: Email to admin@org.com could not be delivered
```

Check logs to troubleshoot delivery issues.
