import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "fixit_tirana.db"


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def init_db():
    with get_connection() as db:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                location TEXT NOT NULL,
                photo TEXT,
                status TEXT NOT NULL DEFAULT 'E re',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                ai_analysis TEXT,
                ai_priority TEXT
            );

            CREATE TABLE IF NOT EXISTS recommendations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_id INTEGER,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY(report_id) REFERENCES reports(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS chat_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );
        """)


def create_report(category, description, location, photo):
    with get_connection() as db:
        cursor = db.execute(
            "INSERT INTO reports (category, description, location, photo) VALUES (?, ?, ?, ?)",
            (category, description, location, photo),
        )
        return cursor.lastrowid


def list_reports(status=None, search=None):
    sql = "SELECT * FROM reports WHERE 1=1"
    params = []
    if status and status != "Të gjitha":
        sql += " AND status = ?"
        params.append(status)
    if search:
        sql += " AND (description LIKE ? OR location LIKE ? OR category LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term])
    sql += " ORDER BY id DESC"
    with get_connection() as db:
        return [dict(row) for row in db.execute(sql, params).fetchall()]


def get_report(report_id):
    with get_connection() as db:
        row = db.execute("SELECT * FROM reports WHERE id = ?", (report_id,)).fetchone()
        return dict(row) if row else None


def update_report_status(report_id, status):
    with get_connection() as db:
        cursor = db.execute("UPDATE reports SET status = ? WHERE id = ?", (status, report_id))
        return cursor.rowcount > 0


def save_ai_analysis(report_id, analysis, priority):
    with get_connection() as db:
        db.execute(
            "UPDATE reports SET ai_analysis = ?, ai_priority = ? WHERE id = ?",
            (analysis, priority, report_id),
        )


def save_recommendation(report_id, content):
    with get_connection() as db:
        db.execute(
            "INSERT INTO recommendations (report_id, content) VALUES (?, ?)",
            (report_id, content),
        )


def list_recommendations():
    with get_connection() as db:
        return [dict(row) for row in db.execute(
            """SELECT recommendations.*, reports.category, reports.location
               FROM recommendations LEFT JOIN reports ON reports.id = recommendations.report_id
               ORDER BY recommendations.id DESC"""
        ).fetchall()]


def add_chat_message(session_id, role, content):
    with get_connection() as db:
        db.execute(
            "INSERT INTO chat_messages (session_id, role, content) VALUES (?, ?, ?)",
            (session_id, role, content),
        )


def get_chat_history(session_id, limit=12):
    with get_connection() as db:
        rows = db.execute(
            "SELECT role, content FROM chat_messages WHERE session_id = ? ORDER BY id DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def clear_chat_history(session_id):
    with get_connection() as db:
        db.execute("DELETE FROM chat_messages WHERE session_id = ?", (session_id,))
