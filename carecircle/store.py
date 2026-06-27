"""
store.py — Encrypted-at-rest local data store.

SECURITY: All health/profile data is serialized to JSON, encrypted with the
Vault (Fernet), and written to data/store.enc. Nothing is stored in plaintext.

Now includes a full elder PROFILE (age, gender, weight, allergies, injuries,
medical history) surfaced by the new History tab.
"""

import json
import os
from .security import vault

_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
_PATH = os.path.join(_DATA_DIR, "store.enc")

_DEFAULT = {
    "elder": {
        "name": "Grandma Devi",
        "language": "English",
        "culture": {"tradition": "Hindu", "fasting_days": ["Tuesday"], "tone": "familiar"},
    },
    # Full medical profile shown on the History tab.
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


def _ensure_dir() -> None:
    os.makedirs(_DATA_DIR, exist_ok=True)


def load() -> dict:
    _ensure_dir()
    if not os.path.exists(_PATH):
        save(_DEFAULT)
        return json.loads(json.dumps(_DEFAULT))
    try:
        with open(_PATH, "r") as f:
            enc = f.read()
        data = json.loads(vault.decrypt(enc))
        # Backfill any missing keys (e.g. if upgrading from an older store).
        for key, val in _DEFAULT.items():
            data.setdefault(key, val)
        return data
    except Exception:
        return json.loads(json.dumps(_DEFAULT))


def save(data: dict) -> None:
    _ensure_dir()
    enc = vault.encrypt(json.dumps(data))
    with open(_PATH, "w") as f:
        f.write(enc)


def update_profile(profile: dict) -> dict:
    """Merge new profile fields and persist (used by the History tab editor)."""
    data = load()
    data.setdefault("profile", {}).update(profile)
    save(data)
    return data["profile"]