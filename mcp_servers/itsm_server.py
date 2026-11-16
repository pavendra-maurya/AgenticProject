from mcp.server.fastmcp import FastMCP

mcp = FastMCP("itsm")

TICKETS = {
    "INC-1001": {"summary": "Cannot connect to VPN after password change",
                 "user_id": "u-100", "device_id": "LT-204", "status": "open"},
    "INC-1002": {"summary": "Laptop very slow, high CPU",
                 "user_id": "u-101", "device_id": "LT-310", "status": "open"},
}
KB = [
    {"id": "KB-1", "title": "VPN fails after password change",
     "body": "Cached credentials are stale. Unlock the account if locked, then clear saved VPN credentials and sign in again."},
    {"id": "KB-2", "title": "Slow laptop troubleshooting",
     "body": "Check runaway processes, pending updates and free disk space. Restarting the endpoint agent service often clears high CPU."},
]
DEVICES = {
    "LT-204": {"os": "Windows 11", "vpn_client": "5.2", "last_seen": "2 min ago"},
    "LT-310": {"os": "Windows 11", "cpu_pct": 97, "disk_free_gb": 4, "agent_service": "degraded"},
}
ALLOWED_ACTIONS = {"unlock_account", "reset_password", "restart_service"}


@mcp.tool()
def get_ticket(ticket_id: str) -> dict:
    """Fetch an IT ticket by ID."""
    return TICKETS.get(ticket_id, {"error": "ticket not found"})


@mcp.tool()
def search_kb(query: str) -> list[dict]:
    """Search knowledge base articles by keywords."""
    words = set(query.lower().split())
    hits = [a for a in KB if words & set((a["title"] + " " + a["body"]).lower().split())]
    return hits or [{"info": "no matching articles"}]


@mcp.tool()
def get_device_status(device_id: str) -> dict:
    """Get health and software info for a device."""
    return DEVICES.get(device_id, {"error": "device not found"})


@mcp.tool()
def plan_action(action: str, target: str) -> dict:
    """DRY RUN. Describe a remediation action without executing it."""
    if action not in ALLOWED_ACTIONS:
        return {"error": f"action must be one of {sorted(ALLOWED_ACTIONS)}"}
    return {"dry_run": True, "action": action, "target": target, "requires_approval": True}


@mcp.tool()
def execute_action(action: str, target: str, approval_id: str) -> dict:
    """Execute an action. Requires a human approval ID. Not given to agents."""
    if not approval_id.startswith("APPROVED-") or action not in ALLOWED_ACTIONS:
        return {"error": "approval required or action not allowed"}
    return {"status": "executed (simulated)", "action": action, "target": target}


if __name__ == "__main__":
    from mcp_http import run
    run(mcp, 9001)   # itsm_server.py = 9001, directory_server.py = 9002, advisory_server.py = 9003