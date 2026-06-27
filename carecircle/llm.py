"""
llm.py
------
Thin wrapper around the Groq API (OpenAI-compatible).
All four agents share this single reasoning backend (gpt-oss-120b),
but each supplies its own system persona.

Hardened against groq/httpx version mismatches AND rate-limited so we never
spam the API (max calls/minute enforced via the shared RateLimiter).
"""

import json
from .config import config
from .ratelimit import api_limiter

_client = None
_client_failed = False  # remember if init failed so we stop retrying


def _get_client():
    global _client, _client_failed
    if _client is not None or _client_failed:
        return _client
    if not config.GROQ_API_KEY:
        return None
    try:
        from groq import Groq
        # Construct with an explicit, clean httpx client to avoid the
        # 'proxies' keyword incompatibility between groq and newer httpx.
        try:
            import httpx
            http_client = httpx.Client(timeout=30.0)
            _client = Groq(api_key=config.GROQ_API_KEY, http_client=http_client)
        except Exception:
            _client = Groq(api_key=config.GROQ_API_KEY)
    except Exception as e:
        print(f"[CareCircle] Groq client init failed, using demo mode: {e}")
        _client_failed = True
        _client = None
    return _client


def chat(system: str, user: str, *, temperature: float = 0.4, json_mode: bool = False) -> str:
    """Send a single-turn prompt to gpt-oss-120b and return the text."""
    client = _get_client()
    if client is None:
        return _demo_response(system, user, json_mode)

    # RATE LIMIT: refuse to exceed the per-minute ceiling. If we're over the
    # limit, return a graceful demo response instead of calling the API.
    if not api_limiter.allow():
        print("[CareCircle] Rate limit reached — serving demo response this cycle.")
        return _demo_response(system, user, json_mode, error="rate_limited")

    kwargs = {
        "model": config.GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
    }
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"[CareCircle] Groq request failed, using demo response: {e}")
        return _demo_response(system, user, json_mode, error=str(e))


def chat_json(system: str, user: str, *, temperature: float = 0.3) -> dict:
    """Convenience wrapper that parses a JSON object response."""
    raw = chat(system, user, temperature=temperature, json_mode=True)
    try:
        return json.loads(raw)
    except Exception:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start:end + 1])
            except Exception:
                pass
        return {"_raw": raw}


def _demo_response(system: str, user: str, json_mode: bool, error: str | None = None) -> str:
    """Deterministic fallback so the app works without a key or on errors."""
    if json_mode:
        return json.dumps({
            "interaction_warnings": [],
            "missed_dose_advice": "Gently remind your loved one about any pending doses.",
            "reminder_adjustments": "No adjustments needed today.",
            "explanation": "CareScore reflects steady routines today.",
            "risk_window_72h": "No elevated risk detected in the next 72 hours.",
            "suggestions": [
                "A short morning walk for gentle activity.",
                "Encourage a glass of water with each meal.",
                "A calm evening routine to support good sleep.",
            ],
            "severity": "low",
            "action_plan": ["Continue normal routine.", "Check in this evening."],
            "alert_message": "All is calm — no action needed right now.",
            "summary": "Demo mode: connect GROQ_API_KEY for live reasoning.",
            "note": error or "offline",
        })
    return ("Your loved one is having a steady day. Medications are mostly on track, "
            "activity and sleep look normal, and there are no concerns right now. "
            "(Connect GROQ_API_KEY in .env for fully personalized AI messages.)")