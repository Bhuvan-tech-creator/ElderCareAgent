"""
vita.py — VITA: Medication Intelligence Agent.

Tracks adherence, detects missed doses, and screens for dangerous
drug-drug interactions BEFORE a dose is taken.
"""

from .base import BaseAgent, AgentResult


class VitaAgent(BaseAgent):
    name = "VITA"
    domain = "medication"
    persona = (
        "You are VITA, a meticulous clinical pharmacist AI inside CareCircle. "
        "You track an elder's medication adherence, flag missed or doubled doses, "
        "and warn about dangerous drug-drug or drug-food interactions in plain, "
        "calm language a family member can understand. You NEVER give a diagnosis; "
        "you flag risks and recommend contacting a doctor or pharmacist when unsure. "
        "Respect cultural fasting windows when scheduling reminders."
    )

    def run(self, payload: dict) -> AgentResult:
        meds = payload.get("medications", [])
        taken_today = payload.get("taken_today", [])
        culture = payload.get("culture", {})

        # Compute adherence locally (deterministic, auditable).
        total = len(meds)
        taken = len([m for m in meds if m.get("name") in taken_today])
        adherence = round((taken / total) * 100) if total else 100
        missed = [m["name"] for m in meds if m.get("name") not in taken_today]

        user = (
            f"Medications: {meds}\n"
            f"Taken today: {taken_today}\n"
            f"Missed: {missed}\n"
            f"Cultural context: {culture}\n"
            "Return JSON with keys: interaction_warnings (list), "
            "missed_dose_advice (string), reminder_adjustments (string)."
        )
        analysis = self.think_json(user)

        return AgentResult(
            agent=self.name,
            output={
                "adherence_pct": adherence,
                "missed_doses": missed,
                "interaction_warnings": analysis.get("interaction_warnings", []),
                "missed_dose_advice": analysis.get("missed_dose_advice", ""),
                "reminder_adjustments": analysis.get("reminder_adjustments", ""),
            },
        )