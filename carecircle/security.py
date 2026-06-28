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

import traceback
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
    low = (text or "").lower()
    return any(p in low for p in _INJECTION_PATTERNS)


def _build_guard_client():
    """
    Build a Groq client for the guard using the same robust strategy as llm.py
    so an httpx/proxies version mismatch never silently breaks the guard.
    """
    from groq import Groq
    try:
        return Groq(api_key=config.GROQ_API_KEY)
    except Exception:
        import httpx
        http_client = httpx.Client(timeout=30.0)
        return Groq(api_key=config.GROQ_API_KEY, http_client=http_client)


def guard_input(text: str) -> dict:
    """
    Screen untrusted input using Llama Prompt Guard 2 via Groq.
    Returns {"safe": bool, "reason": str, "score": float}.
    Falls back to the heuristic check if the model is unavailable.
    """
    text = text or ""

    # Empty input is trivially safe (nothing to screen).
    if not text.strip():
        return {"safe": True, "reason": "Empty input.", "score": 0.0}

    # Always run the cheap heuristic first.
    if heuristic_is_malicious(text):
        return {"safe": False, "reason": "Heuristic detected injection pattern.", "score": 0.95}

    if not config.GROQ_API_KEY:
        return {"safe": True, "reason": "Guard offline; heuristic passed.", "score": 0.0}

    try:
        client = _build_guard_client()
        # Prompt Guard 2 returns a jailbreak probability (or a label) as text.
        resp = client.chat.completions.create(
            model=config.GROQ_GUARD_MODEL,
            messages=[{"role": "user", "content": text[:512]}],
            temperature=0,
        )
        raw = (resp.choices[0].message.content or "").strip()

        # Try to parse a float probability first.
        score = None
        try:
            score = float(raw)
        except ValueError:
            # Some deployments return a label such as "LABEL_1"/"LABEL_0"
            # or "jailbreak"/"benign". Map those sensibly.
            low = raw.lower()
            if "1" in low or "jailbreak" in low or "unsafe" in low:
                score = 0.9
            else:
                score = 0.0

        safe = score < 0.5
        return {
            "safe": safe,
            "reason": "Prompt Guard 2 score" if safe else "Prompt Guard 2 flagged jailbreak.",
            "score": score,
        }
    except Exception as e:  # noqa: BLE001
        # Fail safe: if guard errors, fall back to heuristic result (already passed),
        # but print the traceback so the cause is visible.
        print(f"[CareCircle] Prompt guard error, heuristic fallback used: {e}")
        traceback.print_exc()
        return {"safe": True, "reason": f"Guard error, heuristic passed ({e}).", "score": 0.0}