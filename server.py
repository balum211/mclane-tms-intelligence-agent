"""FastAPI server for the TMS Intelligence agent (same pattern as the sdd-adk-antigravity starter).

    uv run uvicorn server:app --host 0.0.0.0 --port 8080      # ADK dev UI + /run_sse API

ADK discovers every agent package under agents_dir; tms_agent exposes root_agent.
"""

import os

import uvicorn
from google.adk.cli.fast_api import get_fast_api_app

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))

app = get_fast_api_app(agents_dir=AGENTS_DIR, web=True)

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
