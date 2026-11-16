from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client

from config import MCP_AUTH_TOKEN


async def open_session(stack: AsyncExitStack, target) -> ClientSession:
    """target is a URL string (HTTP) or StdioServerParameters (stdio)."""
    if isinstance(target, str):
        r, w, _ = await stack.enter_async_context(
            streamablehttp_client(target, headers={"Authorization": f"Bearer {MCP_AUTH_TOKEN}"})
        )
    else:
        r, w = await stack.enter_async_context(stdio_client(target))
    session = await stack.enter_async_context(ClientSession(r, w))
    await session.initialize()
    return session