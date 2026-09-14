"""Parse the .eml file and extract the HTML body content."""
import email
import os
import quopri
import base64

eml_path = os.path.join(os.path.dirname(__file__), "Join Us for the Campus Recruitment Drive \u2013 FY\u201927 Batch, NIT Jamshedpur.eml")

with open(eml_path, "rb") as f:
    msg = email.message_from_bytes(f.read())

print(f"Subject: {msg['Subject']}")
print(f"From: {msg['From']}")
print(f"To: {msg['To']}")
print()

# Walk through MIME parts to find the HTML body
for part in msg.walk():
    content_type = part.get_content_type()
    if content_type == "text/html":
        encoding = part.get("Content-Transfer-Encoding", "")
        payload = part.get_payload(decode=True)
        if payload:
            charset = part.get_content_charset() or "utf-8"
            html_content = payload.decode(charset, errors="replace")
            
            output_path = os.path.join(os.path.dirname(__file__), "extracted_email.html")
            with open(output_path, "w", encoding="utf-8") as out:
                out.write(html_content)
            
            print(f"HTML body extracted! Length: {len(html_content)} chars")
            print(f"Saved to: {output_path}")
            break
else:
    print("No text/html part found in the email.")
