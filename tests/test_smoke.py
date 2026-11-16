import asyncio
from common.tracking import Tracker, redact
from common.mcp_call import call_tool
from config import mcp_server


def test_redact():
    assert "[REDACTED]" in redact("mail a@b.com")


def test_tracker():
    t = Tracker()
    r = t.new_request()
    tid = t.create_task(r, "triage")
    t.update(r, tid, "done")
    assert t.tasks(r)[0]["status"] == "done"


def test_execute_needs_approval():
    out = asyncio.run(call_tool(mcp_server("itsm_server.py"), "execute_action",
                                {"action": "unlock_account", "target": "u-100",
                                 "approval_id": ""}))
    assert "approval required" in out