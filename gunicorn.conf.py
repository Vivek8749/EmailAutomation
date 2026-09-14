"""Gunicorn configuration for Render deployment."""

import os

# Bind to the port Render provides, or default to 5000
bind = f"0.0.0.0:{os.getenv('PORT', '5000')}"

# Single worker is fine for free tier; keeps memory low
workers = 1

# Longer timeout since email jobs can take a while
timeout = 300

# Access logging
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Graceful shutdown
graceful_timeout = 30
