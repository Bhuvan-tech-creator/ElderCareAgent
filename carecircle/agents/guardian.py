"""
guardian.py — GUARDIAN: Emergency Escalation Agent.

Decides if a situation warrants escalation, builds a priority contact
chain, and (in Night Watch) cross-references weather for environmental risk.
"""

from .base import BaseAgent, AgentResult


class GuardianAgent(BaseAgent):
    name = "GUARDIAN"
    domain = "emergency"
    persona = (
        "You are GUARDIAN, the calm emergency coordinator of CareCircle. You assess "
        "whether a situation needs escalation. You produce a clear, prioritized action "
        "plan and a short alert message. You are decisive but never cause panic. "
        "If a CareScore is in 'Concern' band, vitals/behaviour are abnormal, concerning "
        "symptoms are reported, or a risky extra/OTC medication was taken, you recommend "
        "contacting family in priority order and, if critical, emergency services."
    )

    def run(self, payload: dict) -> AgentResult:
        care_score = payload.get("care_score", 100)
        band = payload.get("band", "Good")
        night_watch = payload.get("night_watch", {})
        contacts = payload.get("contacts", [])
        weather_risk = payload.get("weather_risk", "")
        symptoms = payload.get("symptoms", [])
        extra_meds = payload.get("extra_meds", [])

        # Deterministic escalation trigger (now includes symptoms).
        escalate = (
            band == "Concern"
            or night_watch.get("bathroom_visits", 0) >= 4
            or len(symptoms) >= 2
        )

        user = (
            f"CareScore band: {band} ({care_score}). "
            f"Night watch data: {night_watch}. Weather risk: {weather_risk}. "
            f"Reported symptoms: {symptoms}. Extra/OTC meds: {extra_meds}. "
            f"Priority contacts: {contacts}. Escalate flag: {escalate}.\n"
            "Return ONLY a JSON object with keys: severity (low|medium|high), "
            "action_plan (list), alert_message (string under 60 words)."
        )
        plan = self.think_json(user)

        return AgentResult(
            agent=self.name,
            output={
                "escalate": escalate,
                "severity": plan.get("severity", "low"),
                "action_plan": plan.get("action_plan", []),
                "alert_message": plan.get("alert_message", ""),
            },
        )