# 🏡 CareCircle — Your AI Family Member

> An ambient, multi-agent AI platform that helps families care for elderly loved
> ones — quietly in the background, surfacing only when it truly matters.

**Track:** Concierge Agents · **Built with:** Google ADK pattern · MCP · Groq (gpt-oss-120b)

---

## The Problem
Families managing an elder's health carry an invisible burden — medications,
routines, appointments, and safety — across busy lives, time zones, and language
barriers. Traditional apps demand constant manual logging. CareCircle flips this:
it **watches, reasons, and acts** so families can be present without being vigilant.

## The Solution — 4 Specialized Agents
| Agent | Domain | What it does |
|-------|--------|--------------|
| **VITA** | Medication | Adherence tracking, missed-dose detection, drug-interaction warnings |
| **SAGE** | Health patterns | Computes the **CareScore (0–100)** + 72-hour risk window |
| **GUARDIAN** | Emergency | Escalation decisions, priority contact chain, Night Watch |
| **ECHO** | Communication | Warm family updates + language translation |

An **Orchestrator** coordinates them (ADK root-agent pattern):
`VITA → SAGE → GUARDIAN → ECHO → Telegram summary`.

## Signature Intelligence Layers
- **CareScore** — transparent daily wellness index families check like the weather.
- **Cultural Care Intelligence** — respects fasting windows, festivals, tone, traditions.
- **Caregiver Burnout Prevention** — redistributes load when a caregiver is strained.
- **Night Watch Mode** — silent 10pm–6am sentinel + live weather risk checks.

---

## Kaggle Key Concepts Demonstrated (3+)
1. **Multi-agent system (ADK pattern)** — `carecircle/agents/` + `orchestrator.py`
2. **MCP Server** — `carecircle/mcp/server.py` exposes weather/calendar/care-cycle tools
3. **Security features** — `carecircle/security.py`: Fernet encryption at rest **+**
   Llama Prompt Guard 2 prompt-injection defense
4. **Agent Skills / Agents CLI** — `carecircle/cli.py`
5. **Deployability** — single `python run.py`, Dockerfile-ready, env-var config

---

## Quick Start
```bash
git clone <your-repo> carecircle && cd carecircle
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # then fill in your keys
# Generate an encryption key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

python run.py                 # open http://localhost:8000