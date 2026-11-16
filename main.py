import argparse, asyncio
from common.mcp_call import call_tool
from config import mcp_server
from coordinator import Coordinator


async def run(request: str):
    result = await Coordinator().handle(request)
    print("\n=== Tasks ===")
    for t in result["tasks"]:
        print(f"{t['task_id']}  {t['agent']:<18} {t['status']}")
    print("\n=== Summary ===\n" + result["summary"])
    for p in result["proposed_actions"]:
        ans = input(f"\nProposed: {p['action']} on {p['target']}. Execute? [y/N] ")
        if ans.strip().lower() == "y":
            out = await call_tool(mcp_server("itsm_server.py"), "execute_action",
                                  {**p, "approval_id": f"APPROVED-{result['request_id']}"})
            print("Result:", out)
        else:
            print("Skipped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("request", help="e.g. 'Ticket INC-1001: user cannot connect to VPN'")
    asyncio.run(run(ap.parse_args().request))



# python3 -m venv .venv && source .venv/bin/activate
# pip install -r requirements.txt
# pytest -q
# python mcp_servers/itsm_server.py        # 9001
# python mcp_servers/directory_server.py   # 9002
# python mcp_servers/advisory_server.py    # 9003
# python -m uvicorn remote_agents.internal_agent:app --port 8001
# python -m uvicorn remote_agents.external_agent:app --port 8002
# python main.py "Ticket INC-1001: user cannot connect to VPN"