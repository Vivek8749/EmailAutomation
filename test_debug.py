"""Test the full pipeline: read sheet -> render template -> send email."""
import os, time
os.environ.setdefault("FLASK_DEBUG", "true")

from dotenv import load_dotenv
load_dotenv()

from config import Config
from email_sender import test_smtp_connection, send_email
from sheet_reader import get_pending_clients
from template_engine import render_email, render_subject

# Step 1: Test SMTP
print("[1/4] Testing SMTP connection...")
smtp_result = test_smtp_connection()
if not smtp_result['success']:
    print(f"  SMTP FAILED: {smtp_result['error']}")
    exit(1)
print(f"  SMTP OK - connected to {Config.SMTP_HOST}:{Config.SMTP_PORT}")

# Small delay to avoid rate limits
time.sleep(2)

# Step 2: Get pending clients
print("[2/4] Reading pending clients from Google Sheet...")
try:
    pending = get_pending_clients()
    print(f"  Found {len(pending)} pending row(s)")
except Exception as e:
    print(f"  Sheet read FAILED: {e}")
    exit(1)

if not pending:
    print("  No pending rows! Set Status column to 'pending' in your sheet.")
    exit(0)

# Step 3: Render template for first client
client = pending[0]
print(f"[3/4] Rendering template for: {client.get('Name')} ({client.get('Email')})")
template_name = Config.DEFAULT_TEMPLATE
subject_template = Config.DEFAULT_EMAIL_SUBJECT

try:
    html_body = render_email(template_name, client)
    subject = render_subject(subject_template, client)
    print(f"  Template: {template_name}")
    print(f"  Subject: {subject}")
    print(f"  HTML length: {len(html_body)} chars")
except Exception as e:
    print(f"  Template render FAILED: {e}")
    exit(1)

# Step 4: Send the email
recipient = client.get("Email", "")
print(f"[4/4] Sending email to {recipient}...")
result = send_email(recipient, subject, html_body)

if result["success"]:
    print(f"  SUCCESS! Email sent to {recipient}")
else:
    print(f"  FAILED: {result['error']}")
