"""
db.py
-----
SQLite-backed user database for CareCircle.

SECURITY (Kaggle key concept):
- Each user has a UNIQUE username and a password stored ONLY as a salted
  bcrypt hash (never plaintext) using the bcrypt library directly.
- Each user's full medical profile is stored as an ENCRYPTED JSON blob
  (Fernet, via the Vault) so even the database file never contains plaintext
  health data at rest.
- A signed session cookie (itsdangerous) authenticates requests.

This file owns all persistence: user accounts + their encrypted profiles.
"""

import os
import json
import sqlite3
import threading
import bcrypt
from .security import vault

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_DB_PATH = os.path.join(_DATA_DIR, "carecircle.db")

# SQLite from multiple threads needs care; we guard writes with a lock.
_lock = threading.Lock()

# bcrypt has a hard 72-byte limit on the password input. We truncate safely.
_BCRYPT_MAX_BYTES = 72


def _hash_password(password: str) -> str:
    """Salt + hash a password with bcrypt. Returns a UTF-8 string for storage."""
    pw_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, password_hash: str) -> bool:
    """Constant-time verification of a password against its stored hash."""
    try:
        pw_bytes = password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
        return bcrypt.checkpw(pw_bytes, password_hash.encode("utf-8"))
    except Exception:
        return False


def _ensure_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def _connect() -> sqlite3.Connection:
    _ensure_dir()
    conn = sqlite3.connect(_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the users table if it does not yet exist."""
    with _lock, _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                profile_enc   TEXT NOT NULL,   -- encrypted JSON of the full care record
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Default care record — used as the template for a brand-new user. The login /
# registration form shows each of these values as the placeholder example.
# ---------------------------------------------------------------------------
def default_record(elder_name: str = "Grandma Devi") -> dict:
    return {
        "elder": {
            "name": elder_name,
            "language": "English",
            "culture": {"tradition": "Hindu", "fasting_days": ["Tuesday"], "tone": "familiar"},
        },
        "profile": {
            "age": 74,
            "gender": "Female",
            "weight_kg": 62,
            "height_cm": 158,
            "blood_type": "B+",
            "allergies": ["Penicillin", "Peanuts"],
            "injuries": ["Hip fracture (2021, healed)", "Mild arthritis in knees"],
            "conditions": ["Type 2 Diabetes", "Hypertension"],
            "history_notes": "Cataract surgery in 2019. No history of heart attack or stroke.",
            "primary_doctor": "Dr. Mehta (Cardiology)",
            "emergency_note": "Keeps glucose tablets in bedside drawer.",
        },
        "medications": [
            {"name": "Metformin", "dose": "500mg", "time": "08:00"},
            {"name": "Amlodipine", "dose": "5mg", "time": "20:00"},
        ],
        "taken_today": ["Metformin"],
        "contacts": [
            {"name": "Anita (daughter)", "priority": 1, "phone": "+91-90000-00001"},
            {"name": "Raj (son)", "priority": 2, "phone": "+91-90000-00002"},
        ],
        "signals": {"adherence_pct": 50, "activity_score": 68, "sleep_score": 72, "consistency_score": 80},
        "night_watch": {"bathroom_visits": 2, "returned_to_bed": True},
        "notes": "Mild morning cough reported yesterday.",
    }


# --- Account operations -----------------------------------------------------

def create_user(username: str, password: str, record: dict) -> tuple[bool, str]:
    """Register a new user. Returns (ok, message)."""
    username = (username or "").strip().lower()
    if not username or not password:
        return False, "Username and password are required."
    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    password_hash = _hash_password(password)
    profile_enc = vault.encrypt(json.dumps(record))
    try:
        with _lock, _connect() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, profile_enc) VALUES (?, ?, ?)",
                (username, password_hash, profile_enc),
            )
            conn.commit()
        return True, "Account created."
    except sqlite3.IntegrityError:
        return False, "That username is already taken."


def verify_user(username: str, password: str) -> bool:
    """Return True if the username/password combination is valid."""
    username = (username or "").strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return False
    return _verify_password(password, row["password_hash"])


def user_exists(username: str) -> bool:
    username = (username or "").strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        ).fetchone()
    return row is not None


# --- Per-user encrypted care record ----------------------------------------

def get_record(username: str) -> dict:
    """Load and decrypt a user's full care record."""
    username = (username or "").strip().lower()
    with _connect() as conn:
        row = conn.execute(
            "SELECT profile_enc FROM users WHERE username = ?", (username,)
        ).fetchone()
    if not row:
        return default_record()
    try:
        data = json.loads(vault.decrypt(row["profile_enc"]))
        # Backfill any missing top-level keys for forward compatibility.
        for key, val in default_record().items():
            data.setdefault(key, val)
        return data
    except Exception:
        return default_record()


def save_record(username: str, record: dict) -> None:
    """Encrypt and persist a user's full care record."""
    username = (username or "").strip().lower()
    profile_enc = vault.encrypt(json.dumps(record))
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE users SET profile_enc = ? WHERE username = ?",
            (profile_enc, username),
        )
        conn.commit()


def update_profile(username: str, profile: dict) -> dict:
    """Merge profile fields into the user's record and persist."""
    record = get_record(username)
    record.setdefault("profile", {}).update(profile)
    # Allow updating the elder's display name from the profile form.
    if "name" in profile:
        record.setdefault("elder", {})["name"] = profile["name"]
    save_record(username, record)
    return record["profile"]