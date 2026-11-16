from mcp.server.fastmcp import FastMCP

mcp = FastMCP("directory")

USERS = {
    "u-100": {"name": "Test User A", "department": "Sales", "account_locked": True,
              "mfa_enrolled": True, "groups": ["vpn-users"]},
    "u-101": {"name": "Test User B", "department": "Finance", "account_locked": False,
              "mfa_enrolled": True, "groups": []},
}


@mcp.tool()
def get_user(user_id: str) -> dict:
    """Look up a user's account state and group memberships."""
    return USERS.get(user_id, {"error": "user not found"})


@mcp.tool()
def check_entitlement(user_id: str, group: str) -> dict:
    """Check whether a user belongs to a group."""
    u = USERS.get(user_id)
    return {"user_id": user_id, "group": group, "entitled": bool(u and group in u["groups"])}


if __name__ == "__main__":
    from mcp_http import run
    run(mcp, 9002)   # itsm_server.py = 9001, directory_server.py = 9002, advisory_server.py = 9003