import hmac
import logging

from pydantic import BaseModel
from fastapi import Depends, FastAPI, Header, HTTPException, Request



class TaskIn(BaseModel):
    task_id: str
    request_id: str
    tenant_id: str = "default"
    input: str
    context: str = ""


def _eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def bearer_auth(token: str):
    async def dep(authorization: str = Header(default="")):
        if not _eq(authorization, f"Bearer {token}"):
            raise HTTPException(401, "unauthorized")
    return dep


def api_key_auth(key: str):
    async def dep(x_api_key: str = Header(default="")):
        if not _eq(x_api_key, key):
            raise HTTPException(401, "unauthorized")
    return dep


def build_app(card: dict, agent, auth) -> FastAPI:
    app = FastAPI(title=card["name"])
    cache: dict = {}

    @app.get("/.well-known/agent.json")
    async def get_card(request: Request):
        skills = cache.get("skills")
        if skills is None:
            try:
                skills = cache["skills"] = await agent.describe_tools()
            except Exception:
                logging.exception("could not list tools for agent card")
                skills = []
        return {**card, "url": str(request.base_url).rstrip("/"), "skills": skills}

    @app.post("/tasks", dependencies=[Depends(auth)])
    async def run_task(t: TaskIn):
        try:
            out = await agent.run(t.input, t.context)
        except Exception as e:
            logging.exception("agent run failed")
            raise HTTPException(500, f"agent error: {type(e).__name__}")
        return {"task_id": t.task_id, "status": "done", "output": out}

    return app