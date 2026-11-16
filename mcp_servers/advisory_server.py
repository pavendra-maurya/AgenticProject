from mcp.server.fastmcp import FastMCP

mcp = FastMCP("advisories")

ADVISORIES = [
    {"id": "SAMPLE-ADV-001", "product": "vpn-client", "affected": "5.2",
     "severity": "medium",
     "summary": "Stale credential cache after password change. Fixed in 5.3."},
]


@mcp.tool()
def search_advisories(product: str, version: str = "") -> list[dict]:
    """Search vendor advisories for a product and optional version."""
    hits = [a for a in ADVISORIES if a["product"] == product
            and (not version or a["affected"] == version)]
    return hits or [{"info": "no advisories found"}]

if __name__ == "__main__":
    from mcp_http import run
    run(mcp, 9003)   # itsm_server.py = 9001, directory_server.py = 9002, advisory_server.py = 9003