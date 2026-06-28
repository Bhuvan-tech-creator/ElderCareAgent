"""
llm.py
------
Thin wrapper around the Groq API (OpenAI-compatible).
All four agents share this single reasoning backend (gpt-oss-120b),
but each supplies its own system persona.

IMPORTANT: openai/gpt-oss-120b is a REASONING model. We must tell Groq to
put the final answer into message.content (reasoning_format="parsed") and
keep reasoning effort low, otherwise message.content can come back empty
and the app silently falls back to demo text.
"""

import json
import traceback
from .config import config
from .ratelimit import api_limiter

_client = None
_client_failed = False


def _build_client():
    """Construct a Groq client robustly across groq/httpx versions."""
    from groq import Groq

    last_err = None
    try:
        return Groq(api_key=config.GROQ_API_KEY)
    except Exception as e:  # noqa: BLE001
        last_err = e
        print(f"[CareCircle] Groq plain init failed, trying custom httpx client: {e}")

    try:
        import httpx
        http_client = httpx.Client(timeout=30.0)
        return Groq(api_key=config.GROQ_API_KEY, http_client=http_client)
    except Exception as e:  # noqa: BLE001
        last_err = e
        print(f"[CareCircle] Groq custom httpx init failed: {e}")

    raise last_err


def _get_client():
    global _client, _client_failed
    if _client is not None:
        return _client
    if _client_failed:
        return None
    if not config.GROQ_API_KEY:
        return None
    try:
        _client = _build_client()
        print("[CareCircle] Groq client initialized successfully.")
    except Exception:  # noqa: BLE001
        print("[CareCircle] Groq client init failed permanently, using demo mode:")
        traceback.print_exc()
        _client_failed = True
        _client = None
    return _client


def _is_reasoning_model() -> bool:
    """gpt-oss-* models are reasoning models that need special handling."""
    m = (config.GROQ_MODEL or "").lower()
    return "gpt-oss" in m or "qwen" in m or "reasoning" in m


def _extract_content(resp) -> str:
    """
    Pull the final answer text out of a Groq response, accounting for
    reasoning models where content may be empty and the answer may sit
    in a 'reasoning' attribute instead.
    """
    try:
        msg = resp.choices[0].message
    except Exception:
        return ""

    content = getattr(msg, "content", None)
    if content and content.strip():
        return content.strip()

    # Some reasoning models put the answer in 'reasoning' if content is empty.
    reasoning = getattr(msg, "reasoning", None)
    if reasoning and reasoning.strip():
        return reasoning.strip()

    # Last resort: dict-style access.
    try:
        d = msg.model_dump()
        for key in ("content", "reasoning"):
            v = d.get(key)
            if v and str(v).strip():
                return str(v).strip()
    except Exception:
        pass

    return ""


def chat(system: str, user: str, *, temperature: float = 0.4, json_mode: bool = False) -> str:
    """Send a single-turn prompt to the model and return the text."""
    client = _get_client()
    if client is None:
        return _demo_response(system, user, json_mode)

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
        # Cap output so reasoning models don't run away with tokens.
        "max_completion_tokens": 1024,
    }

    # CRITICAL for gpt-oss-120b: force the final answer into message.content
    # and keep reasoning light so we actually get usable output.
    if _is_reasoning_model():
        kwargs["reasoning_effort"] = "low"
        kwargs["reasoning_format"] = "parsed"

    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
        text = _extract_content(resp)
        if not text:
            # The call succeeded but produced empty content — log it so we know.
            print("[CareCircle] Groq returned empty content. Full message dump:")
            try:
                print(resp.choices[0].message.model_dump())
            except Exception:
                print(resp)
            return _demo_response(system, user, json_mode, error="empty_content")
        return text
    except Exception as e:  # noqa: BLE001
        # Print FULL details (incl. HTTP body) so the real cause is visible.
        print(f"[CareCircle] Groq request FAILED: {type(e).__name__}: {e}")
        body = getattr(e, "body", None) or getattr(e, "response", None)
        if body is not None:
            print(f"[CareCircle] Error body: {body}")
        traceback.print_exc()

        # If the failure was caused by reasoning params or response_format,
        # retry once WITHOUT those extras before giving up to demo mode.
        return _retry_minimal(client, system, user, temperature, json_mode, original_error=str(e))


def _retry_minimal(client, system, user, temperature, json_mode, *, original_error):
    """Fallback retry with the most compatible, minimal parameters."""
    try:
        resp = client.chat.completions.create(
            model=config.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user
                 + ("\n\nReturn ONLY a valid JSON object." if json_mode else "")},
            ],
            temperature=temperature,
        )
        text = _extract_content(resp)
        if text:
            print("[CareCircle] Minimal retry succeeded.")
            return text
        print("[CareCircle] Minimal retry returned empty content.")
    except Exception as e:  # noqa: BLE001
        print(f"[CareCircle] Minimal retry also failed: {e}")
        body = getattr(e, "body", None)
        if body is not None:
            print(f"[CareCircle] Retry error body: {body}")

    return _demo_response(system, user, json_mode, error=original_error)


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
        print(f"[CareCircle] chat_json could not parse JSON. Raw was:\n{raw[:500]}")
        return {"_raw": raw}


def get_client_status() -> dict:
    """Expose whether the live LLM is active (used by /api/health for debugging)."""
    has_key = bool(config.GROQ_API_KEY)
    client = _get_client()
    return {
        "groq_key_present": has_key,
        "groq_client_active": client is not None,
        "groq_client_failed": _client_failed,
        "model": config.GROQ_MODEL,
        "reasoning_model": _is_reasoning_model(),
    }


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