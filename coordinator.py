import json
import httpx
from common.agent import Agent
from common.llm import LLM
from common.tracking import Tracker, redact
from config import (EXTERNAL_API_KEY, EXTERNAL_URL, INTERNAL_TOKEN, INTERNAL_URL,
                    TRACKING_DB, mcp_server)

PLANNER = """You are the planner for an IT helpdesk coordinator. Agents:
- triage: reads the ticket and finds KB articles
- diagnostics: checks device status
- internal_identity: internal directory (account state, entitlements)
- external_advisory: external vendor advisories for a product/version
- resolution: proposes fix actions (dry-run only)
Return ONLY a JSON array (max 6) of {"agent": name, "instruction": text} in order.
Always end with resolution."""
SUMMARY = ("You are an IT helpdesk coordinator. Summarize findings for the user in under "
           "150 words. State root cause, proposed actions, and that actions need human "
           "approval. Use only the provided results; say 'Data unavailable' for gaps. "
           "Do not add causes or steps that are not in the results.")
TRIAGE = "You triage IT tickets. Get the ticket and search the KB. Report summary, user_id, device_id, relevant KB."
DIAG = "You diagnose devices. Check device status for the given device and report findings only."
RESOLVE = ("You propose fixes. Call plan_action (dry run) for each recommended action. "
           "You cannot execute anything. Explain each proposal briefly. "
           "Use only facts present in the tool results.")


class RemoteAgent:
    def __init__(self, base_url, headers, transport=None, timeout=60):
        self.base_url, self.headers = base_url, headers
        self.transport, self.timeout = transport, timeout

    async def card(self):
        async with httpx.AsyncClient(base_url=self.base_url, transport=self.transport,
                                     timeout=self.timeout) as c:
            r = await c.get("/.well-known/agent.json")
            r.raise_for_status()
            return r.json()

    async def send(self, task_id, request_id, tenant_id, text, context=""):
        async with httpx.AsyncClient(base_url=self.base_url, headers=self.headers,
                                     transport=self.transport, timeout=self.timeout) as c:
            r = await c.post("/tasks", json={"task_id": task_id, "request_id": request_id,
                                             "tenant_id": tenant_id, "input": text,
                                             "context": context})
            r.raise_for_status()
            return r.json()["output"]


def parse_plan(text, valid):
    try:
        data = json.loads(text[text.index("["): text.rindex("]") + 1])
        plan = [{"agent": d["agent"], "instruction": d["instruction"]}
                for d in data if d.get("agent") in valid]
        return plan[:6] or None
    except Exception:
        return None


class Coordinator:
    def __init__(self, llm=None, tracker=None, remotes=None):
        self.llm = llm or LLM()
        self.tracker = tracker or Tracker(TRACKING_DB)
        itsm = mcp_server("itsm_server.py")
        self.local = {
            "triage": Agent("triage", TRIAGE, [itsm], {"get_ticket", "search_kb"}, self.llm),
            "diagnostics": Agent("diagnostics", DIAG, [itsm],
                                 {"get_device_status", "get_ticket"}, self.llm),
            "resolution": Agent("resolution", RESOLVE, [itsm],
                                {"search_kb", "plan_action"}, self.llm),
        }
        self.remotes = remotes or {
            "internal_identity": RemoteAgent(INTERNAL_URL, {"Authorization": f"Bearer {INTERNAL_TOKEN}"}),
            "external_advisory": RemoteAgent(EXTERNAL_URL, {"X-API-Key": EXTERNAL_API_KEY}),
        }
        self.valid = set(self.local) | set(self.remotes)

    async def _ask(self, system, text):
        r = await self.llm.create(system, [{"role": "user", "content": text}])
        return r.text

    async def _remote_info(self) -> str:
        lines = []
        for name, ra in self.remotes.items():
            try:
                c = await ra.card()
                tools = ", ".join(s["id"] for s in c.get("skills", []))
                lines.append(f"- {name}: {c.get('description', '')} Tools: {tools}")
            except Exception:
                lines.append(f"- {name}: (card unavailable)")
        return "\n".join(lines)

    @staticmethod
    def _proposals(calls):
        out = []
        for c in calls:
            if c["tool"] == "plan_action" and not c["error"]:
                try:
                    d = json.loads(c["result"])
                    if d.get("dry_run"):
                        out.append({"action": d["action"], "target": d["target"]})
                except Exception:
                    pass
        return out

    async def handle(self, request: str, tenant_id: str = "default") -> dict:
        rid = self.tracker.new_request()
        self.tracker.event(rid, None, "request.received", {"text": request})

        planner = PLANNER + "\n\nRemote agent details (from agent cards):\n" + await self._remote_info()
        plan = parse_plan(await self._ask(planner, request), self.valid) or [
            {"agent": "triage", "instruction": request},
            {"agent": "resolution", "instruction": request}]
        results, proposals = [], []
        for step in plan:
            name, instr = step["agent"], step["instruction"]
            tid = self.tracker.create_task(rid, name, tenant_id)
            ctx = redact("\n\n".join(f"[{r['agent']}] {r['output'][:1500]}" for r in results))
            self.tracker.update(rid, tid, "running")
            try:
                if name in self.local:
                    agent = self.local[name]
                    out = await agent.run(f"{instr}\n\nOriginal request: {request}", ctx)
                    if name == "resolution":
                        proposals += self._proposals(agent.last_calls)
                else:
                    out = await self.remotes[name].send(tid, rid, tenant_id, instr, ctx)
                self.tracker.update(rid, tid, "done", out)
            except Exception as e:
                out = f"FAILED: {type(e).__name__}"
                self.tracker.update(rid, tid, "failed", out)
            results.append({"agent": name, "output": out})
        summary = await self._ask(SUMMARY, redact(json.dumps(results)))
        return {"request_id": rid, "summary": summary, "proposed_actions": proposals,
                "tasks": self.tracker.tasks(rid, tenant_id)}