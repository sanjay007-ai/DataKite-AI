import os
import sqlite3
from pathlib import Path
from flask import session
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = Path(__file__).resolve().parent

# Vercel functions run from a read-only filesystem. Always use /tmp there.
# Ignore any stale DATAKITE_DB_PATH value on Vercel unless explicitly needed later.
if os.environ.get("VERCEL") == "1":
    DB_PATH = Path("/tmp/datakite_users.db")
else:
    DB_PATH = Path(os.environ.get("DATAKITE_DB_PATH", BASE_DIR / "datakite_users.db"))


def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)


def create_user(name, email, password):
    name = str(name or "").strip()[:100]
    email = str(email or "").strip().lower()[:254]
    password = str(password or "")
    if len(name) < 2:
        return None, "Please enter your name."
    if "@" not in email or len(email) < 6:
        return None, "Please enter a valid email address."
    if len(password) < 8:
        return None, "Password must be at least 8 characters."
    try:
        with _connect() as conn:
            cur = conn.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            user_id = cur.lastrowid
    except sqlite3.IntegrityError:
        return None, "An account with this email already exists."
    # Keep a server-signed, browser-scoped credential as a fallback for
    # stateless Vercel instances. SQLite /tmp is not durable across instances.
    session["account_email"] = email
    session["account_name"] = name
    session["account_password_hash"] = generate_password_hash(password)
    return {"id": user_id, "name": name, "email": email}, None


def authenticate(email, password):
    email = str(email or "").strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, name, email, password_hash FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    if row and check_password_hash(row["password_hash"], str(password or "")):
        return {"id": row["id"], "name": row["name"], "email": row["email"]}

    # Serverless fallback: use the signed Flask session created during
    # registration on this browser. This avoids false login failures when a
    # later request lands on a fresh Vercel instance with a new /tmp database.
    cached_email = str(session.get("account_email") or "").strip().lower()
    cached_hash = session.get("account_password_hash")
    if cached_email == email and cached_hash:
        try:
            if check_password_hash(cached_hash, str(password or "")):
                return {
                    "id": session.get("user_id", 1),
                    "name": session.get("account_name", "DataKite User"),
                    "email": cached_email,
                }
        except Exception:
            pass
    return None


def sign_in(user):
    account_email = session.get("account_email")
    account_name = session.get("account_name")
    account_password_hash = session.get("account_password_hash")
    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    session["user_email"] = user["email"]
    if account_email and account_password_hash:
        session["account_email"] = account_email
        session["account_name"] = account_name or user["name"]
        session["account_password_hash"] = account_password_hash
    session.permanent = True


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return {
        "id": user_id,
        "name": session.get("user_name", ""),
        "email": session.get("user_email", ""),
    }


def sign_out():
    session.clear()
