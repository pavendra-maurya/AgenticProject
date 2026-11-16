from contextlib import AsyncExitStack

from common.mcp_conn import open_session


async def call_tool(target, name: str, args: dict) -> str:
    async with AsyncExitStack() as stack:
        s = await open_session(stack, target)
        res = await s.call_tool(name, args)
        return "\n".join(c.text for c in res.content if hasattr(c, "text"))