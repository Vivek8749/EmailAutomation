"""
Email sender module.
Handles sending emails via Gmail SMTP with TLS.
"""

import os
import smtplib
import logging
import mimetypes
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from email.utils import formataddr
from config import Config

logger = logging.getLogger(__name__)


def send_email(to, subject, html_body, cc=None, bcc=None):
    """Send a single HTML email via Gmail SMTP.
    
    Args:
        to: Recipient email address
        subject: Email subject line
        html_body: Rendered HTML content of the email
        cc: Optional CC address or list of addresses
        bcc: Optional BCC address or list of addresses
        
    Returns:
        dict: Result with 'success' (bool) and 'error' (str, if failed)
    """
    sender_email = Config.GMAIL_ADDRESS
    sender_password = Config.GMAIL_APP_PASSWORD
    from_name = Config.EMAIL_FROM_NAME or sender_email
    
    if not sender_email or not sender_password:
        return {
            "success": False,
            "error": "Gmail credentials not configured (GMAIL_ADDRESS / GMAIL_APP_PASSWORD)"
        }
    
    # Build the email message
    msg = MIMEMultipart("alternative")
    msg["From"] = formataddr((from_name, sender_email))
    msg["To"] = to
    msg["Subject"] = subject
    
    if cc:
        cc_list = cc if isinstance(cc, list) else [cc]
        msg["Cc"] = ", ".join(cc_list)
    else:
        cc_list = []
    
    if bcc:
        bcc_list = bcc if isinstance(bcc, list) else [bcc]
    else:
        bcc_list = []
    
    # Attach HTML content
    msg.attach(MIMEText(html_body, "html"))
    
    # Attach files from attachments directory
    attachments_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EMailAutomation", "attachments")
    if os.path.exists(attachments_dir):
        for filename in os.listdir(attachments_dir):
            file_path = os.path.join(attachments_dir, filename)
            if os.path.isfile(file_path) and not filename.startswith('.'):
                try:
                    with open(file_path, "rb") as attachment:
                        ctype, encoding = mimetypes.guess_type(file_path)
                        if ctype is None or encoding is not None:
                            ctype = "application/octet-stream"
                        maintype, subtype = ctype.split("/", 1)
                        
                        part = MIMEBase(maintype, subtype)
                        part.set_payload(attachment.read())
                        encoders.encode_base64(part)
                        part.add_header(
                            "Content-Disposition",
                            f"attachment; filename={filename}",
                        )
                        msg.attach(part)
                        logger.info(f"Attached file: {filename}")
                except Exception as e:
                    logger.error(f"Failed to attach {filename}: {e}")
    
    # Build full recipient list
    all_recipients = [to] + cc_list + bcc_list
    
    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, all_recipients, msg.as_string())
        
        logger.info(f"Email sent successfully to {to}")
        return {"success": True, "error": ""}
        
    except smtplib.SMTPAuthenticationError as e:
        error_msg = f"SMTP authentication failed. Check your App Password. Details: {e}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
        
    except smtplib.SMTPRecipientsRefused as e:
        error_msg = f"Recipient refused: {to}. Details: {e}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
        
    except smtplib.SMTPException as e:
        error_msg = f"SMTP error sending to {to}: {e}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
        
    except Exception as e:
        error_msg = f"Unexpected error sending to {to}: {e}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}


def test_smtp_connection():
    """Test the SMTP connection without sending an email.
    
    Returns:
        dict: Result with 'success' (bool) and 'error' (str, if failed)
    """
    sender_email = Config.GMAIL_ADDRESS
    sender_password = Config.GMAIL_APP_PASSWORD
    
    if not sender_email or not sender_password:
        return {
            "success": False,
            "error": "Gmail credentials not configured"
        }
    
    try:
        with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(sender_email, sender_password)
        
        logger.info("SMTP connection test successful")
        return {"success": True, "error": ""}
        
    except Exception as e:
        error_msg = f"SMTP connection test failed: {e}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}
