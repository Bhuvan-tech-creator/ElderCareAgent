"""
run.py — single entry point for the CareCircle web app.
Usage:  python run.py
"""

import uvicorn
from carecircle.config import config

if __name__ == "__main__":
    print("=" * 60)
    print(" CareCircle — ambient multi-agent elder care")
    print("=" * 60)
    for w in config.validate():
        print("  ⚠️ ", w)
    print(f"\n  Open http://localhost:{config.PORT}\n")
    uvicorn.run("carecircle.web.server:app", host=config.HOST, port=config.PORT, reload=False)