"""
store.py — Per-user encrypted care record access.

Historically this module held a single global record. It now delegates to the
SQLite database (db.py) so EACH logged-in user gets their own personalized,
encrypted profile. The orchestrator/agents call load()/save() with a username.

SECURITY: All health/profile data remains encrypted at rest (Fernet) inside
the database; nothing is stored in plaintext.
"""

from . import db


def load(username: str) -> dict:
    """Load a specific user's care record (decrypted)."""
    return db.get_record(username)


def save(username: str, data: dict) -> None:
    """Persist a specific user's care record (encrypted)."""
    db.save_record(username, data)


def update_profile(username: str, profile: dict) -> dict:
    """Merge + persist profile fields for a user. Returns the new profile."""
    return db.update_profile(username, profile)