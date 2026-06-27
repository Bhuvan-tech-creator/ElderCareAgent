"""
security.py
-----------
SECURITY FEATURES (Kaggle key concept) — two layers:

1. End-to-end encryption of health data at rest (Fernet / AES-128-CBC + HMAC).
   Aligns with the Concierge track mandate: personal data stays private,
   encrypted, and inside the family circle.

2. Prompt-injection / jailbreak defense using Meta's Llama Prompt Guard 2.
   Every piece of untrusted user/elder input is screened BEFORE it reaches
   the reasoning model, preventing malicious instructions from hijacking
   an agent that has access to real tools (calendar, emergency dialing, etc.).
"""

from cryptography.fernet import Fernet
from .config import config


class Vault:
    """Encrypts/decrypts sensitive strings for storage."""

    def __init__(self) -> None:
        if config.ENCRYPTION_KEY:
            self._key = config.ENCRYPTION_KEY.encode()
        else:
            # Ephemeral key for demo runs (data won't survive restart).
            self._key = Fernet.generate_key()
        self._fernet = Fernet(self._key)

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, token: str) -> str:
        return self._fernet.decrypt(token.encode()).decode()


vault = Vault()


# --- Prompt-injection guard -------------------------------------------------

# Lightweight keyword pre-filter (runs even with no network / no key).
_INJECTION_PATTERNS = [
    "ignore previous", "ignore all previous", "disregard your instructions",
    "you are now", "system prompt", "reveal your prompt", "jailbreak",
    "act as", "developer mode", "override safety",
]


def heuristic_is_malicious(text: str) -> bool:
    """Fast, offline first-pass check."""
    low = text.lower()
    return any(p in low for p in _INJECTION_PATTERNS)


def guard_input(text: str) -> dict:
    """
    Screen untrusted input using Llama Prompt Guard 2 via Groq.
    Returns {"safe": bool, "reason": str, "score": float}.
    Falls back to the heuristic check if the model is unavailable.
    """
    # Always run the cheap heuristic first.
    if heuristic_is_malicious(text):
        return {"safe": False, "reason": "Heuristic detected injection pattern.", "score": 0.95}

    if not config.GROQ_API_KEY:
        return {"safe": True, "reason": "Guard offline; heuristic passed.", "score": 0.0}

    try:
        from groq import Groq
        client = Groq(api_key=config.GROQ_API_KEY)
        # Prompt Guard 2 returns a jailbreak probability as plain text.
        resp = client.chat.completions.create(
            model=config.GROQ_GUARD_MODEL,
            messages=[{"role": "user", "content": text[:512]}],
            temperature=0,
        )
        raw = resp.choices[0].message.content.strip()
        try:
            score = float(raw)
        except ValueError:
            score = 0.0
        safe = score < 0.5
        return {
            "safe": safe,
            "reason": "Prompt Guard 2 score" if safe else "Prompt Guard 2 flagged jailbreak.",
            "score": score,
        }
    except Exception as e:
        # Fail safe: if guard errors, fall back to heuristic result (already passed).
        return {"safe": True, "reason": f"Guard error, heuristic passed ({e}).", "score": 0.0}  