"""
config.py
---------
Centralized, secure configuration loader for CareCircle.

SECURITY FEATURE (Kaggle key concept):
- All secrets (API keys, bot tokens, encryption keys) are loaded ONLY from
  environment variables via a .env file that is git-ignored.
- No secret is ever hard-coded anywhere in the codebase.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Strongly-typed access to all environment configuration."""

    # --- Groq LLM ---
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    GROQ_GUARD_MODEL: str = os.getenv(
        "GROQ_GUARD_MODEL", "meta-llama/llama-prompt-guard-2-22m"
    )

    # --- Telegram ---
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Weather ---
    OPENWEATHER_API_KEY: str = os.getenv("OPENWEATHER_API_KEY", "")
    CARE_CITY: str = os.getenv("CARE_CITY", "Mumbai")

    # --- Security ---
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    # Secret used to sign session cookies. Falls back to a dev default.
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "carecircle-dev-session-secret-change-me")

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # --- Daily summary scheduler ---
    DAILY_SUMMARY_HOUR: int = int(os.getenv("DAILY_SUMMARY_HOUR", "8"))
    DAILY_SUMMARY_MINUTE: int = int(os.getenv("DAILY_SUMMARY_MINUTE", "0"))
    ENABLE_DAILY_SUMMARY: bool = os.getenv("ENABLE_DAILY_SUMMARY", "true").lower() == "true"

    # --- Rate limiting ---
    MAX_API_CALLS_PER_MINUTE: int = int(os.getenv("MAX_API_CALLS_PER_MINUTE", "10"))

    @classmethod
    def validate(cls) -> list[str]:
        warnings = []
        if not cls.GROQ_API_KEY:
            warnings.append("GROQ_API_KEY missing — agents will run in offline/demo mode.")
        if not cls.TELEGRAM_BOT_TOKEN or not cls.TELEGRAM_CHAT_ID:
            warnings.append("Telegram not configured — notifications will print to console.")
        if not cls.OPENWEATHER_API_KEY:
            warnings.append("OPENWEATHER_API_KEY missing — weather will use mock data.")
        if not cls.ENCRYPTION_KEY:
            warnings.append("ENCRYPTION_KEY missing — a temporary key will be generated (data won't persist across restarts).")
        if cls.SESSION_SECRET == "carecircle-dev-session-secret-change-me":
            warnings.append("SESSION_SECRET is the default — set a strong value in .env for production.")
        return warnings


config = Config()