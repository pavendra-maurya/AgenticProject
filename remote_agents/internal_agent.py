from common.agent import Agent
from config import INTERNAL_TOKEN, mcp_server
from remote_agents.a2a_server import bearer_auth, build_app

CARD = {
    "name": "internal-identity",
    "description": "Internal identity agent: account state and entitlement checks.",
    "version": "1.0.0",
    "scope": "internal",
    "authentication": {"scheme": "bearer", "header": "Authorization"},
    "capabilities": {"streaming": False},
}

SYSTEM = ("You are the internal identity agent. Use directory tools to check user "
          "account state and entitlements. Report facts only; never invent data.")


def make_app(llm=None):
    agent = Agent("internal-identity", SYSTEM, [mcp_server("directory_server.py")], llm=llm)
    return build_app(CARD, agent, bearer_auth(INTERNAL_TOKEN))


app = make_app()