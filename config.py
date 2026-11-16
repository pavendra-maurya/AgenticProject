import os, sys
from pathlib import Path
from mcp import StdioServerParameters
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
INTERNAL_URL = os.getenv("INTERNAL_AGENT_URL", "http://127.0.0.1:8001")
EXTERNAL_URL = os.getenv("EXTERNAL_AGENT_URL", "http://127.0.0.1:8002")
INTERNAL_TOKEN = os.getenv("INTERNAL_AGENT_TOKEN", "dev-internal-token")
EXTERNAL_API_KEY = os.getenv("EXTERNAL_AGENT_API_KEY", "dev-external-key")
TRACKING_DB = os.getenv("TRACKING_DB", str(ROOT / "tracking.db"))

MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio")
MCP_AUTH_TOKEN = os.getenv("MCP_AUTH_TOKEN", "dev-mcp-token")
MCP_PORTS = {"itsm_server.py": 9001, "directory_server.py": 9002, "advisory_server.py": 9003}


def mcp_server(script: str):
    if MCP_TRANSPORT == "http":
        return f"http://127.0.0.1:{MCP_PORTS[script]}/mcp"
    return StdioServerParameters(
        command=sys.executable, args=[str(ROOT / "mcp_servers" / script)]
    )
