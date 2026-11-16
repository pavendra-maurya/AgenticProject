import json
import os
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from dotenv import load_dotenv
load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "openai").lower()  # "openai" | "gemini"

_PROVIDERS = {
    "openai": {"key_env": "OPENAI_API_KEY", "base_url": None,
               "model": os.getenv("LLM_MODEL") or "gpt-4o-mini"},
    "gemini": {"key_env": "GEMINI_API_KEY",
               "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
               "model": os.getenv("LLM_MODEL") or "gemini-2.0-flash"},
    "groq": {"key_env": "GROQ_API_KEY",
             "base_url": "https://api.groq.com/openai/v1",
             "model": os.getenv("LLM_MODEL") or "llama-3.3-70b-versatile"},
}


@dataclass
class ToolCall:
    id: str
    name: str
    args: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_message: dict | None = None


class LLM:
    def __init__(self, max_tokens: int = 2048):
        if PROVIDER not in _PROVIDERS:
            raise ValueError(f"LLM_PROVIDER must be one of {list(_PROVIDERS)}")
        self.cfg = _PROVIDERS[PROVIDER]
        self.max_tokens = max_tokens
        self._client = None

    async def create(self, system: str, messages: list[dict],
                     tools: list[dict] | None = None) -> LLMResponse:
        if self._client is None:
            self._client = AsyncOpenAI(api_key=os.environ[self.cfg["key_env"]],
                                       base_url=self.cfg["base_url"])
        kwargs = {
            "model": self.cfg["model"],
            "max_tokens": self.max_tokens,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        if tools:
            kwargs["tools"] = [
                {"type": "function",
                 "function": {"name": t["name"], "description": t["description"],
                              "parameters": t["input_schema"]}}
                for t in tools
            ]
        msg = (await self._client.chat.completions.create(**kwargs)).choices[0].message
        calls = [ToolCall(c.id, c.function.name, json.loads(c.function.arguments or "{}"))
                 for c in (msg.tool_calls or [])]
        raw = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            raw["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in msg.tool_calls
            ]
        return LLMResponse(text=msg.content or "", tool_calls=calls, raw_message=raw)