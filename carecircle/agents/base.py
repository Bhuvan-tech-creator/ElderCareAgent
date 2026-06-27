"""
base.py
-------
ADK-STYLE AGENT PATTERN (Kaggle key concept: Agent / Multi-agent system).

Each CareCircle agent is a self-contained unit with:
  - a name and domain
  - a system persona (its "instruction")
  - a set of tools it can call
  - a run() method invoked by the Orchestrator

This mirrors Google's Agent Development Kit (ADK) LlmAgent design:
specialized agents coordinated by a root orchestrator agent.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
from ..security import guard_input
from ..llm import chat, chat_json


@dataclass
class AgentResult:
    agent: str
    output: dict
    blocked: bool = False
    reason: str = ""


class BaseAgent:
    name: str = "agent"
    domain: str = "general"
    persona: str = "You are a helpful care assistant."

    def __init__(self) -> None:
        self.tools: dict[str, Callable] = {}

    # --- LLM helpers shared by all agents ---
    def think(self, user: str, *, temperature: float = 0.4) -> str:
        return chat(self.persona, user, temperature=temperature)

    def think_json(self, user: str, *, temperature: float = 0.3) -> dict:
        return chat_json(self.persona, user, temperature=temperature)

    # --- Security gate applied to any untrusted input ---
    def screened(self, untrusted_text: str) -> tuple[bool, str]:
        verdict = guard_input(untrusted_text)
        return verdict["safe"], verdict["reason"]

    def run(self, payload: dict) -> AgentResult:  # pragma: no cover - overridden
        raise NotImplementedError