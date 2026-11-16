import hmac
import os
import uvicorn  # noqa: E402
from dotenv import load_dotenv
import logging



logging.getLogger("mcp.server.streamable_http").setLevel(logging.CRITICAL)

load_dotenv()



TOKEN = os.getenv("MCP_AUTH_TOKEN", "dev-mcp-token")


class BearerAuth:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            got = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(got, f"Bearer {TOKEN}".encode()):
                await send({"type": "http.response.start", "status": 401,
                            "headers": [(b"content-type", b"application/json")]})
                await send({"type": "http.response.body",
                            "body": b'{"error":"unauthorized"}'})
                return
        await self.app(scope, receive, send)


def run(mcp, port: int):
    if os.getenv("MCP_TRANSPORT", "stdio") == "http":
        app = BearerAuth(mcp.streamable_http_app())
        uvicorn.run(app, host="127.0.0.1", port=port)
    else:
        mcp.run()