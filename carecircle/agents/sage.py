"""
sage.py — SAGE: Health Pattern Intelligence Agent.

Computes the CareScore (0-100 daily wellness index) and projects a
72-hour risk window from behavioral signals. This is CareCircle's
signature intelligence layer.
"""

from .base import BaseAgent, AgentResult


class SageAgent(BaseAgent):
    name = "SAGE"
    domain = "health_patterns"
    persona = (
        "You are SAGE, a careful geriatric health-pattern analyst inside CareCircle. "
        "You synthesize medication adherence, activity, sleep, behavioral "
        "consistency, and any reported symptoms into insight. You explain WHY a score "
        "moved and what to watch. You forecast a 72-hour risk window but never diagnose. "
        "Be precise and calm."
    )

    @staticmethod
    def compute_care_score(signals: dict) -> dict:
        """
        Deterministic, transparent CareScore so families can trust the number.
        Weighted blend of four pillars, each 0-100.
        """
        adherence = signals.get("adherence_pct", 100)          # from VITA
        activity = signals.get("activity_score", 70)           # steps / movement
        sleep = signals.get("sleep_score", 70)                 # sleep quality
        consistency = signals.get("consistency_score", 75)     # routine stability

        weights = {"adherence": 0.35, "activity": 0.25, "sleep": 0.25, "consistency": 0.15}
        score = (
            adherence * weights["adherence"]
            + activity * weights["activity"]
            + sleep * weights["sleep"]
            + consistency * weights["consistency"]
        )
        score = round(score)

        if score >= 80:
            band = "Good"
        elif score >= 60:
            band = "Watch"
        else:
            band = "Concern"

        return {"care_score": score, "band": band, "pillars": {
            "adherence": adherence, "activity": activity,
            "sleep": sleep, "consistency": consistency}}

    def run(self, payload: dict) -> AgentResult:
        signals = payload.get("signals", {})
        symptoms = payload.get("symptoms", [])
        scored = self.compute_care_score(signals)

        user = (
            f"CareScore: {scored['care_score']} ({scored['band']}). "
            f"Pillars: {scored['pillars']}. Recent signals: {signals}. "
            f"Reported symptoms: {symptoms}.\n"
            "Return ONLY a JSON object with keys: explanation (1 sentence on why the "
            "score is where it is, referencing the strongest pillar or any symptoms), "
            "risk_window_72h (string), "
            "suggestions (list of 3 short daily suggestions tailored to the signals)."
        )
        analysis = self.think_json(user)

        return AgentResult(
            agent=self.name,
            output={
                **scored,
                "explanation": analysis.get("explanation", ""),
                "risk_window_72h": analysis.get("risk_window_72h", ""),
                "suggestions": analysis.get("suggestions", []),
            },
        )