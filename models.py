"""
Database models for email send logging.
Uses SQLite for lightweight, zero-config persistence.
"""

import sqlite3
import os
from datetime import datetime, timezone
from config import Config


DB_PATH = Config.DATABASE_PATH


def _get_connection():
    """Get a SQLite connection with row factory enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """Create the database tables if they don't exist."""
    conn = _get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS email_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            recipient TEXT NOT NULL,
            recipient_name TEXT DEFAULT '',
            subject TEXT NOT NULL,
            status TEXT NOT NULL CHECK(status IN ('sent', 'failed')),
            error_message TEXT DEFAULT '',
            template_used TEXT DEFAULT '',
            sent_at TEXT NOT NULL,
            trigger_source TEXT DEFAULT 'webhook'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS run_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            started_at TEXT NOT NULL,
            completed_at TEXT,
            total_emails INTEGER DEFAULT 0,
            sent_count INTEGER DEFAULT 0,
            failed_count INTEGER DEFAULT 0,
            trigger_source TEXT DEFAULT 'webhook',
            status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'failed'))
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_logs_sent_at 
        ON email_logs(sent_at DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_email_logs_status 
        ON email_logs(status)
    """)
    conn.commit()
    conn.close()


def log_email(recipient, recipient_name, subject, status, error_message="",
              template_used="", trigger_source="webhook"):
    """Log a single email send attempt.
    
    Args:
        recipient: Email address of the recipient
        recipient_name: Name of the recipient
        subject: Email subject line
        status: 'sent' or 'failed'
        error_message: Error details if failed
        template_used: Name of the template file used
        trigger_source: How the send was triggered ('webhook', 'manual', 'test')
    """
    conn = _get_connection()
    conn.execute("""
        INSERT INTO email_logs 
        (recipient, recipient_name, subject, status, error_message, template_used, sent_at, trigger_source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        recipient, recipient_name, subject, status, error_message,
        template_used, datetime.now(timezone.utc).isoformat(), trigger_source
    ))
    conn.commit()
    conn.close()


def create_run_log(trigger_source="webhook"):
    """Create a new run log entry and return its ID.
    
    Args:
        trigger_source: How the run was triggered
        
    Returns:
        int: The run log ID
    """
    conn = _get_connection()
    cursor = conn.execute("""
        INSERT INTO run_logs (started_at, trigger_source)
        VALUES (?, ?)
    """, (datetime.now(timezone.utc).isoformat(), trigger_source))
    run_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return run_id


def complete_run_log(run_id, total_emails, sent_count, failed_count, status="completed"):
    """Update a run log entry with completion details.
    
    Args:
        run_id: The run log ID to update
        total_emails: Total number of emails processed
        sent_count: Number of emails successfully sent
        failed_count: Number of emails that failed
        status: Final status ('completed' or 'failed')
    """
    conn = _get_connection()
    conn.execute("""
        UPDATE run_logs 
        SET completed_at = ?, total_emails = ?, sent_count = ?, failed_count = ?, status = ?
        WHERE id = ?
    """, (
        datetime.now(timezone.utc).isoformat(),
        total_emails, sent_count, failed_count, status, run_id
    ))
    conn.commit()
    conn.close()


def get_logs(page=1, per_page=25, status_filter=None, search=None):
    """Get paginated email logs with optional filtering.
    
    Args:
        page: Page number (1-indexed)
        per_page: Number of records per page
        status_filter: Filter by status ('sent' or 'failed')
        search: Search term for recipient email or name
        
    Returns:
        tuple: (logs: list[dict], total_count: int, total_pages: int)
    """
    conn = _get_connection()
    
    where_clauses = []
    params = []
    
    if status_filter and status_filter in ("sent", "failed"):
        where_clauses.append("status = ?")
        params.append(status_filter)
    
    if search:
        where_clauses.append("(recipient LIKE ? OR recipient_name LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    # Get total count
    count_row = conn.execute(
        f"SELECT COUNT(*) as count FROM email_logs {where_sql}", params
    ).fetchone()
    total_count = count_row["count"]
    total_pages = max(1, (total_count + per_page - 1) // per_page)
    
    # Get paginated results
    offset = (page - 1) * per_page
    rows = conn.execute(
        f"SELECT * FROM email_logs {where_sql} ORDER BY sent_at DESC LIMIT ? OFFSET ?",
        params + [per_page, offset]
    ).fetchall()
    
    logs = [dict(row) for row in rows]
    conn.close()
    
    return logs, total_count, total_pages


def get_stats():
    """Get aggregate email statistics.
    
    Returns:
        dict: Statistics including total_sent, total_failed, total_emails,
              last_run_at, today_sent, today_failed
    """
    conn = _get_connection()
    
    # Overall counts
    stats_row = conn.execute("""
        SELECT 
            COUNT(*) as total_emails,
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as total_sent,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as total_failed
        FROM email_logs
    """).fetchone()
    
    # Today's counts (UTC)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    today_row = conn.execute("""
        SELECT 
            SUM(CASE WHEN status = 'sent' THEN 1 ELSE 0 END) as today_sent,
            SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as today_failed
        FROM email_logs
        WHERE sent_at LIKE ?
    """, (f"{today}%",)).fetchone()
    
    # Last run info
    last_run = conn.execute("""
        SELECT * FROM run_logs ORDER BY started_at DESC LIMIT 1
    """).fetchone()
    
    # Recent runs
    recent_runs = conn.execute("""
        SELECT * FROM run_logs ORDER BY started_at DESC LIMIT 10
    """).fetchall()
    
    conn.close()
    
    return {
        "total_emails": stats_row["total_emails"] or 0,
        "total_sent": stats_row["total_sent"] or 0,
        "total_failed": stats_row["total_failed"] or 0,
        "today_sent": today_row["today_sent"] or 0 if today_row else 0,
        "today_failed": today_row["today_failed"] or 0 if today_row else 0,
        "last_run": dict(last_run) if last_run else None,
        "recent_runs": [dict(r) for r in recent_runs],
    }


def get_recent_activity(limit=10):
    """Get the most recent email log entries.
    
    Args:
        limit: Number of recent entries to return
        
    Returns:
        list[dict]: Recent email log entries
    """
    conn = _get_connection()
    rows = conn.execute(
        "SELECT * FROM email_logs ORDER BY sent_at DESC LIMIT ?", (limit,)
    ).fetchall()
    activity = [dict(row) for row in rows]
    conn.close()
    return activity


# Initialize database on import
init_db()
