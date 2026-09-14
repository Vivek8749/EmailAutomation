"""
EMailAutomation — Flask Application
Main entry point with API webhook routes and dashboard UI.
"""

import logging
import time
import drive_sync
from datetime import datetime, timezone
from flask import Flask, render_template, request, jsonify, redirect, url_for

from config import Config
from models import (
    init_db, log_email, create_run_log, complete_run_log,
    get_logs, get_stats, get_recent_activity,
)
from sheet_reader import get_pending_clients, update_status, test_connection as test_sheets
from email_sender import send_email, test_smtp_connection
from template_engine import (
    render_email as render_template_email,
    render_subject,
    list_templates,
    get_template_content,
    preview_template,
)

# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = Config.SECRET_KEY

# Ensure DB is initialized
init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_api_key():
    """Check the X-API-Key header against the configured trigger key.
    
    Returns:
        tuple or None: (jsonify response, status_code) if invalid, None if valid
    """
    api_key = request.headers.get("X-API-Key", "")
    if not Config.TRIGGER_API_KEY:
        return jsonify({"error": "TRIGGER_API_KEY not configured on server"}), 500
    if api_key != Config.TRIGGER_API_KEY:
        return jsonify({"error": "Invalid or missing API key"}), 401
    return None


def _run_email_job(trigger_source="webhook"):
    """Core email sending logic — reads sheet, renders templates, sends emails.
    
    Args:
        trigger_source: How this run was triggered ('webhook', 'manual', 'test')
        
    Returns:
        dict: Run summary with counts and details
    """
    run_id = create_run_log(trigger_source)
    results = {"sent": 0, "failed": 0, "total": 0, "details": []}
    
    try:
        # 0. Sync attachments from Google Drive
        drive_sync.sync_attachments()
        
        # 1. Read pending clients from Google Sheet
        pending = get_pending_clients()
        results["total"] = len(pending)
        
        if not pending:
            logger.info("No pending emails found in Google Sheet")
            complete_run_log(run_id, 0, 0, 0, "completed")
            return results
        
        logger.info(f"Processing {len(pending)} pending emails")
        
        template_name = Config.DEFAULT_TEMPLATE
        subject_template = Config.DEFAULT_EMAIL_SUBJECT
        
        # 2. Process each pending client
        for client in pending:
            recipient_email = str(client.get("Email", "")).strip()
            recipient_name = str(client.get("Name", "")).strip()
            row_number = client.get("_row_number")
            
            if not recipient_email:
                logger.warning(f"Skipping row {row_number}: no Email column value")
                continue
            
            detail = {
                "email": recipient_email,
                "name": recipient_name,
                "status": "",
                "error": "",
            }
            
            try:
                # Render the email template with client data
                html_body = render_template_email(template_name, client)
                subject = render_subject(subject_template, client)
                
                # Send the email
                result = send_email(recipient_email, subject, html_body)
                
                if result["success"]:
                    detail["status"] = "sent"
                    results["sent"] += 1
                    # Update sheet status
                    try:
                        update_status(row_number, "sent")
                    except Exception as e:
                        logger.error(f"Failed to update sheet for row {row_number}: {e}")
                else:
                    detail["status"] = "failed"
                    detail["error"] = result["error"]
                    results["failed"] += 1
                    try:
                        update_status(row_number, "failed")
                    except Exception as e:
                        logger.error(f"Failed to update sheet for row {row_number}: {e}")
                
                # Log to database
                log_email(
                    recipient=recipient_email,
                    recipient_name=recipient_name,
                    subject=subject,
                    status=detail["status"],
                    error_message=detail.get("error", ""),
                    template_used=template_name,
                    trigger_source=trigger_source,
                )
                
            except Exception as e:
                detail["status"] = "failed"
                detail["error"] = str(e)
                results["failed"] += 1
                logger.error(f"Error processing {recipient_email}: {e}")
                
                log_email(
                    recipient=recipient_email,
                    recipient_name=recipient_name,
                    subject="(render failed)",
                    status="failed",
                    error_message=str(e),
                    template_used=template_name,
                    trigger_source=trigger_source,
                )
            
            results["details"].append(detail)
            
            # Small delay between sends to avoid rate limiting
            time.sleep(1)
        
        # 3. Complete the run log
        status = "completed" if results["failed"] == 0 else "completed"
        complete_run_log(run_id, results["total"], results["sent"], results["failed"], status)
        
    except Exception as e:
        logger.error(f"Email job failed: {e}")
        complete_run_log(run_id, results["total"], results["sent"], results["failed"], "failed")
        raise
    
    return results


# ===========================================================================
# API Routes (Webhook)
# ===========================================================================

@app.route("/api/trigger", methods=["POST"])
def api_trigger():
    """Webhook endpoint for external cron service to trigger email sending.
    
    Requires X-API-Key header matching TRIGGER_API_KEY env var.
    
    Returns:
        JSON response with run summary
    """
    auth_error = _verify_api_key()
    if auth_error:
        return auth_error
    
    logger.info("Email job triggered via webhook")
    
    try:
        results = _run_email_job(trigger_source="webhook")
        return jsonify({
            "status": "completed",
            "total": results["total"],
            "sent": results["sent"],
            "failed": results["failed"],
            "details": results["details"],
        }), 200
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
        }), 500


@app.route("/api/status", methods=["GET"])
def api_status():
    """Health check and status endpoint.
    
    Returns:
        JSON response with app health and last run info
    """
    stats = get_stats()
    is_valid, config_errors = Config.validate()
    
    return jsonify({
        "status": "healthy",
        "config_valid": is_valid,
        "config_errors": config_errors,
        "stats": stats,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }), 200


@app.route("/api/send-test", methods=["POST"])
def api_send_test():
    """Send a test email to verify SMTP configuration.
    
    Expects JSON body with 'to' field (recipient email address).
    
    Returns:
        JSON response with send result
    """
    data = request.get_json() or {}
    to = data.get("to", "").strip()
    
    if not to:
        return jsonify({"error": "Missing 'to' field"}), 400
    
    # Render template with sample data
    sample_data = {
        "Name": "Test User",
        "Email": to,
        "Company": "Test Company",
        "Custom_Message": "This is a test email to verify your configuration is working!",
    }
    
    try:
        html_body = render_template_email(Config.DEFAULT_TEMPLATE, sample_data)
        subject = render_subject(Config.DEFAULT_EMAIL_SUBJECT, sample_data)
        result = send_email(to, subject, html_body)
        
        log_email(
            recipient=to,
            recipient_name="Test User",
            subject=subject,
            status="sent" if result["success"] else "failed",
            error_message=result.get("error", ""),
            template_used=Config.DEFAULT_TEMPLATE,
            trigger_source="test",
        )
        
        if result["success"]:
            return jsonify({"status": "sent", "message": f"Test email sent to {to}"}), 200
        else:
            return jsonify({"status": "failed", "error": result["error"]}), 500
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/api/test-sheets", methods=["POST"])
def api_test_sheets():
    """Test the Google Sheets connection.
    
    Returns:
        JSON response with sheet info or error
    """
    result = test_sheets()
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code


@app.route("/api/test-smtp", methods=["POST"])
def api_test_smtp():
    """Test the SMTP connection.
    
    Returns:
        JSON response with connection result
    """
    result = test_smtp_connection()
    status_code = 200 if result["success"] else 500
    return jsonify(result), status_code


@app.route("/api/preview-template", methods=["POST"])
def api_preview_template():
    """Render a template with sample data for preview.
    
    Returns:
        JSON response with rendered HTML
    """
    data = request.get_json() or {}
    template_name = data.get("template", Config.DEFAULT_TEMPLATE)
    sample_data = data.get("data", None)
    
    try:
        html = preview_template(template_name, sample_data)
        return jsonify({"html": html}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ===========================================================================
# Dashboard Routes (Web UI)
# ===========================================================================

@app.route("/")
def dashboard():
    """Main dashboard page with stats and recent activity."""
    stats = get_stats()
    recent = get_recent_activity(limit=10)
    is_valid, config_errors = Config.validate()
    
    return render_template(
        "dashboard.html",
        stats=stats,
        recent_activity=recent,
        config_valid=is_valid,
        config_errors=config_errors,
    )


@app.route("/logs")
def logs_page():
    """Email send logs page with pagination and filtering."""
    page = request.args.get("page", 1, type=int)
    status_filter = request.args.get("status", None)
    search = request.args.get("search", None)
    
    logs, total_count, total_pages = get_logs(
        page=page,
        per_page=25,
        status_filter=status_filter,
        search=search,
    )
    
    return render_template(
        "logs.html",
        logs=logs,
        page=page,
        total_count=total_count,
        total_pages=total_pages,
        status_filter=status_filter,
        search=search or "",
    )


@app.route("/settings")
def settings_page():
    """Settings page showing configuration and template info."""
    is_valid, config_errors = Config.validate()
    templates = list_templates()
    
    # Masked config for display
    masked_config = {
        "GMAIL_ADDRESS": Config.GMAIL_ADDRESS or "(not set)",
        "GMAIL_APP_PASSWORD": Config.get_masked_value(Config.GMAIL_APP_PASSWORD),
        "SMTP_HOST": Config.SMTP_HOST,
        "SMTP_PORT": Config.SMTP_PORT,
        "EMAIL_FROM_NAME": Config.EMAIL_FROM_NAME or "(not set)",
        "GOOGLE_SHEET_URL": Config.GOOGLE_SHEET_URL or "(not set)",
        "TRIGGER_API_KEY": Config.get_masked_value(Config.TRIGGER_API_KEY),
        "DEFAULT_TEMPLATE": Config.DEFAULT_TEMPLATE,
        "DEFAULT_EMAIL_SUBJECT": Config.DEFAULT_EMAIL_SUBJECT,
        "SHEET_STATUS_COLUMN": Config.SHEET_STATUS_COLUMN,
    }
    
    # Get default template content for preview
    template_content = get_template_content(Config.DEFAULT_TEMPLATE)
    
    return render_template(
        "settings.html",
        config=masked_config,
        config_valid=is_valid,
        config_errors=config_errors,
        templates=templates,
        template_content=template_content,
    )


@app.route("/trigger", methods=["POST"])
def manual_trigger():
    """Manual trigger from the dashboard UI (no API key required since it's the same server)."""
    try:
        results = _run_email_job(trigger_source="manual")
        return redirect(url_for("dashboard"))
    except Exception as e:
        logger.error(f"Manual trigger failed: {e}")
        return redirect(url_for("dashboard"))


# ===========================================================================
# Entry Point
# ===========================================================================

if __name__ == "__main__":
    is_valid, errors = Config.validate()
    if not is_valid:
        logger.warning("Configuration incomplete:")
        for err in errors:
            logger.warning(f"  - {err}")
        logger.warning("Some features may not work until configuration is complete.")
    
    app.run(debug=Config.DEBUG, host="0.0.0.0", port=5000)
