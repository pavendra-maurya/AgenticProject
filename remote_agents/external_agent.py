from common.agent import Agent
from config import EXTERNAL_API_KEY, mcp_server
from remote_agents.a2a_server import api_key_auth, build_app

CARD = {
    "name": "external-advisory",
    "description": "External vendor advisory agent: known issues by product and version.",
    "version": "1.0.0",
    "scope": "external",
    "authentication": {"scheme": "api_key", "header": "X-API-Key"},
    "capabilities": {"streaming": False},
}
SYSTEM = ("You are an external vendor advisory agent. Use advisory tools to find known "
          "issues for a product and version. Report only what the tools return.")


def make_app(llm=None):
    agent = Agent("external-advisory", SYSTEM, [mcp_server("advisory_server.py")], llm=llm)
    return build_app(CARD, agent, api_key_auth(EXTERNAL_API_KEY))


app = make_app()