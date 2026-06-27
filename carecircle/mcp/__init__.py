"""
mcp/server.py
-------------
MCP SERVER (Kaggle key concept: Model Context Protocol).

Exposes CareCircle's real-world tools — weather, calendar, pharmacy,
emergency maps routing, and the daily care cycle — over the Model Context
Protocol so that ANY MCP-compatible agent client (Claude Desktop, Gemini,
ADK, etc.) can call them as standardized tools.

Run standalone:  python -m carecircle.mcp.server
"""

from mcp.server.fastmcp import FastMCP
from ..tools import weather as weather_tool
from ..tools import calendar as calendar_tool
from ..orchestrator import orchestrator

mcp = FastMCP("CareCircle")


@mcp.tool()
def get_weather(city: str = "") -> dict:
    """Get current weather and environmental health risk for the elder's city."""
    return weather_tool.get_weather(city or None)


@mcp.tool()
def list_appointments(limit: int = 5) -> list:
    """List the elder's upcoming appointments and medication refills."""
    return calendar_tool.list_upcoming(limit)


@mcp.tool()
def add_appointment(title: str, when: str) -> dict:
    """Add an appointment. 'when' format: 'YYYY-MM-DD HH:MM'."""
    return calendar_tool.add_event(title, when)


@mcp.tool()
def run_care_cycle(elder_note: str = "") -> dict:
    """Run the full multi-agent care cycle and return all agent outputs."""
    return orchestrator.run_care_cycle(elder_note)


@mcp.tool()
def send_daily_summary(elder_note: str = "") -> dict:
    """Run the care cycle AND dispatch the family Telegram summary."""
    return orchestrator.send_summary(elder_note)


if __name__ == "__main__":
    # Runs over stdio transport — the standard for MCP servers.
    mcp.run()