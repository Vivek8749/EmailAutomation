# 📧 EMailAutomation

Automated email sending system that reads client data from Google Sheets, renders personalized HTML templates, and sends emails via Gmail SMTP. Designed for deployment on **Render** with an external cron service for scheduling.

## Features

- 🔄 **Webhook-triggered** email runs (POST `/api/trigger`)
- 📊 **Google Sheets** integration — reads clients, updates send status
- 🎨 **Jinja2 HTML templates** — any sheet column becomes a template variable
- 📧 **Gmail SMTP** — sends via App Password with TLS
- 📋 **Dashboard UI** — dark-themed monitoring with stats, logs, and settings
- 🧪 **Test tools** — send test emails, test connections from the dashboard
- 🗄️ **SQLite logging** — tracks every email sent and every run

---

## Quick Start (Local Development)

### 1. Prerequisites

- Python 3.9+
- A Gmail account with 2FA enabled
- A Google Cloud project with Sheets API enabled

### 2. Clone & Install

```bash
cd EMailAutomation
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

### 3. Set Up Gmail App Password

1. Go to [Google Account Security](https://myaccount.google.com/security)
2. Ensure **2-Step Verification** is enabled
3. Go to **App Passwords** (search for it in account settings)
4. Create a new app password for "Mail"
5. Copy the 16-character password

### 4. Set Up Google Sheets API

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Google Sheets API** and **Google Drive API**
4. Go to **Credentials** → **Create Credentials** → **Service Account**
5. Download the JSON key file → save as `service_account.json` in project root
6. Open your Google Sheet → click **Share** → paste the `client_email` from the JSON file

### 5. Set Up Your Google Sheet

Create a spreadsheet with these columns (the header names matter):

| Name | Email | Company | Custom_Message | Status |
|------|-------|---------|----------------|--------|
| John Doe | john@example.com | Acme Corp | Welcome aboard! | pending |
| Jane Smith | jane@example.com | Beta Inc | Let's connect! | pending |

- The `Status` column must contain `pending` for rows that need to be sent
- After sending, the system updates it to `sent` or `failed`
- You can add any extra columns — they all become template variables

### 6. Configure Environment

```bash
copy .env.example .env
# Edit .env with your values
```

Required values:
- `GMAIL_ADDRESS` — your Gmail address
- `GMAIL_APP_PASSWORD` — the 16-char app password
- `GOOGLE_SHEET_URL` — full URL of your Google Sheet
- `GOOGLE_SERVICE_ACCOUNT_FILE` — path to service account JSON (or use `GOOGLE_SERVICE_ACCOUNT_JSON` for inline)
- `TRIGGER_API_KEY` — any secret string for webhook authentication

### 7. Run Locally

```bash
python app.py
```

Open http://localhost:5000 to see the dashboard.

---

## API Endpoints

### Trigger Email Run
```bash
curl -X POST http://localhost:5000/api/trigger \
  -H "X-API-Key: your-api-key"
```

### Health Check
```bash
curl http://localhost:5000/api/status
```

### Send Test Email
```bash
curl -X POST http://localhost:5000/api/send-test \
  -H "Content-Type: application/json" \
  -d '{"to": "test@example.com"}'
```

---

## Deployment to Render

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-username/EMailAutomation.git
git push -u origin main
```

### 2. Deploy on Render

1. Go to [Render Dashboard](https://dashboard.render.com/)
2. Click **New** → **Web Service**
3. Connect your GitHub repo
4. Render will auto-detect `render.yaml`
5. Add environment variables in the Render dashboard:
   - `GMAIL_ADDRESS`
   - `GMAIL_APP_PASSWORD`
   - `GOOGLE_SHEET_URL`
   - `GOOGLE_SERVICE_ACCOUNT_JSON` — paste the **entire JSON content** of your service account file
   - `TRIGGER_API_KEY` — (auto-generated, but note it down)

### 3. Set Up External Cron

Since Render's free tier sleeps after inactivity, use an external cron service:

**Option A: [cron-job.org](https://cron-job.org/)**
1. Create a free account
2. Create a new cron job:
   - **URL**: `https://your-app.onrender.com/api/trigger`
   - **Method**: POST
   - **Headers**: `X-API-Key: your-trigger-api-key`
   - **Schedule**: Set your desired time (e.g., daily at 9:00 AM)

**Option B: [UptimeRobot](https://uptimerobot.com/)**
1. Create a monitor for `https://your-app.onrender.com/api/status`
2. This keeps the app awake between cron runs

---

## Email Templates

Templates live in `templates/email_templates/` and use Jinja2 syntax.

### Using Sheet Columns as Variables

Every column header in your Google Sheet becomes a template variable:

```html
<h1>Hello, {{ Name }}!</h1>
<p>We're reaching out to {{ Company }}.</p>
<p>{{ Custom_Message }}</p>
```

### Creating Custom Templates

1. Add a new `.html` file to `templates/email_templates/`
2. Use inline CSS (for email client compatibility)
3. Use `{{ ColumnName }}` for any sheet column
4. Set `DEFAULT_TEMPLATE` in `.env` to use your new template

---

## Project Structure

```
EMailAutomation/
├── app.py                  # Flask app — routes & job orchestration
├── config.py               # Environment variable configuration
├── email_sender.py         # Gmail SMTP sender
├── sheet_reader.py         # Google Sheets integration
├── template_engine.py      # Jinja2 template rendering
├── models.py               # SQLite email log models
├── requirements.txt        # Python dependencies
├── gunicorn.conf.py        # Gunicorn config for Render
├── render.yaml             # Render deployment Blueprint
├── .env.example            # Environment variable template
├── .gitignore              # Git ignore rules
├── templates/
│   ├── base.html           # Dashboard layout
│   ├── dashboard.html      # Stats & activity page
│   ├── logs.html           # Email logs page
│   ├── settings.html       # Config & test page
│   └── email_templates/
│       └── default.html    # Default email template
└── static/
    └── css/
        └── style.css       # Dashboard dark theme
```

---

## License

MIT
