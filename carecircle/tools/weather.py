"""
weather.py — Live weather tool used by Night Watch / GUARDIAN.
Falls back to mock data if no OPENWEATHER_API_KEY is set.
"""

import requests
from ..config import config


def get_weather(city: str | None = None) -> dict:
    city = city or config.CARE_CITY
    if not config.OPENWEATHER_API_KEY:
        return _mock(city)
    try:
        r = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"q": city, "appid": config.OPENWEATHER_API_KEY, "units": "metric"},
            timeout=8,
        )
        d = r.json()
        temp = d["main"]["temp"]
        cond = d["weather"][0]["main"]
        risk = _assess_risk(temp, cond)
        return {"city": city, "temp_c": temp, "condition": cond, "risk": risk}
    except Exception:
        return _mock(city)


def _assess_risk(temp: float, condition: str) -> str:
    risks = []
    if temp <= 5:
        risks.append("Very cold night — hypothermia risk; ensure heating/blankets.")
    if condition.lower() in ("thunderstorm", "tornado"):
        risks.append("Severe storm warning — keep elder indoors.")
    if condition.lower() in ("smoke", "haze", "dust"):
        risks.append("Poor air quality — limit outdoor activity.")
    return " ".join(risks) if risks else "No significant environmental risk."


def _mock(city: str) -> dict:
    return {"city": city, "temp_c": 22, "condition": "Clear",
            "risk": "No significant environmental risk. (mock data)"}