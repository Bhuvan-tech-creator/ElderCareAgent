"""
vita.py — VITA: Medication Intelligence Agent.

Tracks adherence, detects missed doses, flags extra/OTC doses reported by the
caregiver, and screens for dangerous drug-drug or drug-food interactions.
"""

from .base import BaseAgent, AgentResult


class VitaAgent(BaseAgent):
    name = "VITA"
    domain = "medication"
    persona = (
        "You are VITA, a meticulous clinical pharmacist AI inside CareCircle. "
        "You track an elder's medication adherence, flag missed or doubled doses, "
        "and warn about dangerous drug-drug or drug-food interactions in plain, "
        "calm language a family member can understand. If the caregiver reports an "
        "EXTRA or over-the-counter medication (like Advil/ibuprofen, aspirin), assess "
        "whether it could interact with the elder's prescribed medications or conditions. "
        "You NEVER give a diagnosis; you flag risks and recommend contacting a doctor or "
        "pharmacist when unsure. Respect cultural fasting windows when scheduling reminders."
    )

    def run(self, payload: dict) -> AgentResult:
        meds = payload.get("medications", [])
        taken_today = payload.get("taken_today", [])
        extra_meds = payload.get("extra_meds", [])
        symptoms = payload.get("symptoms", [])
        culture = payload.get("culture", {})

        # Compute adherence locally (deterministic, auditable).
        total = len(meds)
        taken = len([m for m in meds if m.get("name") in taken_today])
        adherence = round((taken / total) * 100) if total else 100
        missed = [m["name"] for m in meds if m.get("name") not in taken_today]

        user = (
            f"Prescribed medications: {meds}\n"
            f"Taken today: {taken_today}\n"
            f"Missed: {missed}\n"
            f"Extra / OTC meds reported by caregiver: {extra_meds}\n"
            f"Reported symptoms: {symptoms}\n"
            f"Cultural context: {culture}\n"
            "Return ONLY a JSON object with keys: "
            "interaction_warnings (list of short strings about any risky interactions, "
            "including any involving the extra/OTC meds), "
            "missed_dose_advice (string), "
            "reminder_adjustments (string)."
        )
        analysis = self.think_json(user)

        return AgentResult(
            agent=self.name,
            output={
                "adherence_pct": adherence,
                "missed_doses": missed,
                "extra_meds": extra_meds,
                "interaction_warnings": analysis.get("interaction_warnings", []),
                "missed_dose_advice": analysis.get("missed_dose_advice", ""),
                "reminder_adjustments": analysis.get("reminder_adjustments", ""),
            },
        )