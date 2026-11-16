from contextlib import AsyncExitStack

from common.llm import LLM
from common.mcp_conn import open_session

MAX_OUT = 4000


class Agent:
    def __init__(self, name, system, mcp_servers: list,
                 allowed_tools: set[str] | None = None, llm: LLM | None = None,
                 max_steps: int = 8):
        self.name, self.system = name, system
        self.mcp_servers, self.allowed_tools = mcp_servers, allowed_tools
        self.llm = llm or LLM()
        self.max_steps = max_steps
        self.last_calls: list[dict] = []

    async def describe_tools(self) -> list[dict]:
        out = []
        async with AsyncExitStack() as stack:
            for target in self.mcp_servers:
                s = await open_session(stack, target)
                for t in (await s.list_tools()).tools:
                    if self.allowed_tools is None or t.name in self.allowed_tools:
                        out.append({"id": t.name, "description": t.description or ""})
        return out

    async def run(self, task: str, context: str = "") -> str:
        self.last_calls = []
        prompt = f"Context:\n{context}\n\nTask:\n{task}" if context else task
        async with AsyncExitStack() as stack:
            routes, tools = {}, []
            for target in self.mcp_servers:
                session = await open_session(stack, target)
                for t in (await session.list_tools()).tools:
                    if self.allowed_tools is None or t.name in self.allowed_tools:
                        routes[t.name] = session
                        tools.append({"name": t.name,
                                      "description": t.description or "",
                                      "input_schema": t.inputSchema})

            messages = [{"role": "user", "content": prompt}]
            for _ in range(self.max_steps):
                resp = await self.llm.create(self.system, messages, tools or None)
                messages.append(resp.raw_message)
                if not resp.tool_calls:
                    return resp.text
                for c in resp.tool_calls:
                    out, err = await self._call(routes, c.name, c.args)
                    self.last_calls.append({"tool": c.name, "args": c.args,
                                            "result": out, "error": err})
                    messages.append({"role": "tool", "tool_call_id": c.id,
                                     "content": ("ERROR: " + out) if err else out})
            return "Stopped: maximum steps reached."

    async def _call(self, routes, name, args):
        s = routes.get(name)
        if s is None:
            return f"Tool '{name}' not permitted for '{self.name}'.", True
        try:
            res = await s.call_tool(name, args)
            text = "\n".join(c.text for c in res.content if hasattr(c, "text"))
            return text[:MAX_OUT], bool(res.isError)
        except Exception as e:
            return f"Tool error: {type(e).__name__}", True