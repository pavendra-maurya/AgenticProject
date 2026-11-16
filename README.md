# Agentic IT Helpdesk

A multi-agent system that investigates IT tickets, proposes fixes, and runs a fix only after a human approves it.

A coordinator agent plans the work and delegates to three local agents and two remote agents (one internal, one external). All agents use tools through MCP servers running on their own ports. The LLM can be OpenAI, Gemini, or Groq.

> All data in the MCP servers is mock sample data. Replace it with calls to your real systems before real use.

## Architecture

```
main.py (CLI, human approval)
   |
Coordinator  --plans--> LLM (OpenAI / Gemini / Groq)
   |
   |-- local agents (in-process): triage, diagnostics, resolution
   |        '-- MCP over HTTP --> itsm_server        :9001
   |
   |-- internal_identity (HTTP :8001) -- MCP --> directory_server :9002
   '-- external_advisory (HTTP :8002) -- MCP --> advisory_server  :9003
```

| Link | Transport |
|---|---|
| Coordinator to remote agents | HTTP, bearer token or API key |
| Any agent to MCP servers | MCP Streamable HTTP, bearer token |
| Any agent to LLM | HTTPS to the configured provider |

## Request flow

1. `main.py` sends the request to the coordinator.
2. The coordinator reads each remote agent's card (`/.well-known/agent.json`), so the planner knows their tools.
3. The LLM produces a plan: an ordered list of agents and instructions.
4. Each step runs as a tracked task (`queued`, `running`, `done` or `failed`). Earlier results are passed forward as redacted context.
5. The resolution agent can only call `plan_action` (dry run).
6. The LLM writes a short summary.
7. For each proposed action, `main.py` asks `Execute? [y/N]`. Only `y` calls `execute_action`.

## Project structure

```
AgenticProject/
├── main.py                  CLI entry point and approval prompt
├── coordinator.py           Planning, routing, tracking, summary, RemoteAgent client
├── config.py                Settings loaded from .env, mcp_server() helper
├── common/
│   ├── llm.py               OpenAI / Gemini / Groq wrapper
│   ├── agent.py             Agent loop: MCP tools plus LLM
│   ├── mcp_conn.py          Opens MCP connections (HTTP or stdio)
│   ├── mcp_call.py          Direct MCP call for approved actions
│   └── tracking.py          SQLite task tracking and PII redaction
├── mcp_servers/
│   ├── itsm_server.py       Tickets, KB, devices, plan/execute actions (:9001)
│   ├── directory_server.py  User account state and entitlements (:9002)
│   ├── advisory_server.py   Vendor advisory lookup (:9003)
│   └── mcp_http.py          Runs a server over HTTP with token check
├── remote_agents/
│   ├── a2a_server.py        FastAPI template: /tasks and agent card
│   ├── internal_agent.py    Internal identity agent (:8001)
│   └── external_agent.py    External advisory agent (:8002)
├── tests/test_smoke.py      Redaction, tracking, approval check
├── conftest.py              Empty, lets pytest import project modules
├── requirements.txt
└── .env.example
```

## Setup

Requires Python 3.11+ (3.12 is the safest choice; newer versions may hit package incompatibilities).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`requirements.txt`:

```
openai>=1.40
mcp>=1.2,<2
fastapi>=0.110
uvicorn>=0.29
httpx>=0.27
python-dotenv>=1.0
pytest>=8
```

Pin `mcp<2`. Version 2.x renamed `FastMCP` and changed other APIs.

## Configuration (`.env`)

```
LLM_PROVIDER=groq              # openai | gemini | groq
OPENAI_API_KEY=
GEMINI_API_KEY=
GROQ_API_KEY=
LLM_MODEL=openai/gpt-oss-120b  # a model your key can use
INTERNAL_AGENT_URL=http://127.0.0.1:8001
EXTERNAL_AGENT_URL=http://127.0.0.1:8002
INTERNAL_AGENT_TOKEN=change-me
EXTERNAL_AGENT_API_KEY=change-me
MCP_TRANSPORT=http             # http | stdio
MCP_AUTH_TOKEN=change-me
```

- Fill in only the key for your chosen provider.
- Replace every `change-me` with a different random value.
- Never commit `.env`. Add `.env` and `tracking.db` to `.gitignore`.
- Set `LLM_MODEL` to a model your account can use and that supports tool calling. Default model names may not be available to your key.
- Restart the servers after changing `.env`; they read it at startup.

## Run

Open six terminals in the project folder, each with the virtual environment active. Start in this order.

MCP servers:

```bash
python mcp_servers/itsm_server.py        # :9001
python mcp_servers/directory_server.py   # :9002
python mcp_servers/advisory_server.py    # :9003
```

Remote agents:

```bash
python -m uvicorn remote_agents.internal_agent:app --port 8001
python -m uvicorn remote_agents.external_agent:app --port 8002
```

Run a request:

```bash
python main.py "Ticket INC-1001: user cannot connect to VPN"
```

You get a task list (all `done` when everything works), a summary, and an approval prompt for each proposed fix.

### stdio mode (single terminal for tools)

Set `MCP_TRANSPORT=stdio` in `.env`. Each agent run then starts its own MCP server as a child process, so you do not need the three MCP terminals. You still need the two remote agent servers.

## Checks

```bash
MCP_TRANSPORT=stdio pytest -q
curl http://127.0.0.1:8001/.well-known/agent.json
curl -i http://127.0.0.1:9001/mcp        # expect 401 without a token
```

## Components

- **Coordinator:** plans with the LLM, runs steps in order, tracks tasks, summarizes. If the plan cannot be parsed, it falls back to triage then resolution.
- **Local agents:**
  - `triage` reads the ticket and searches the KB.
  - `diagnostics` checks device status.
  - `resolution` proposes fixes by dry run only.
- **Remote agents:** `internal_identity` (account state, entitlements) and `external_advisory` (vendor advisories). Each exposes `POST /tasks` (authenticated) and a public agent card whose skills come from its real MCP tools.
- **MCP servers:** tool providers on ports 9001 to 9003.
- **Tracker:** stores requests, tasks, and events in `tracking.db` and redacts emails, card-like numbers, SSN-like numbers, and secrets.

## Safety design

- Agents only see their allowed tools. `execute_action` is hidden from every agent.
- Execution needs explicit human confirmation.
- Remote and MCP calls need tokens, and servers bind to `127.0.0.1`.
- Tracker logs and context passed between agents are redacted.
- Missing information is reported as "Data unavailable".

## Limitations

- Mock data only.
- The approval check is a simple `APPROVED-` prefix. A real system needs signed or server-stored approvals.
- Tokens are shared secrets for local development. For production use a secret manager, TLS, per-service credentials, and the MCP authorization spec (OAuth).
- Agent card routes are unauthenticated and list tool names.
- The LLM chooses the plan and tool calls, so review its proposals before approving.
- `Error in standalone SSE writer ... ClosedResourceError` lines in MCP server logs appear when a session closes. They have not caused failures in testing.

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| `No module named 'mcp.server.fastmcp'` | mcp 2.x installed. Run `pip install "mcp>=1.2,<2"`. |
| `KeyError: ... API_KEY` | `.env` not loaded or the key is missing for the chosen provider. |
| `404 model does not exist` | Set `LLM_MODEL` to a model your account can use. |
| Remote task `401 Unauthorized` | Token mismatch. Make sure all processes read the same `.env`, then restart the servers. |
| Remote task `500` | Check the uvicorn terminal for the traceback (agent or LLM error). |
| Task `failed` for a remote agent | The remote server is not running or is on a different port. |
| `AttributeError: ... _remote_info` | The method must be in `Coordinator`, not `RemoteAgent`. |
| Connection refused to 900x | Start the MCP servers first, or set `MCP_TRANSPORT=stdio`. |

## Extending

- Add a tool: define it in an MCP server with `@mcp.tool()`, and add its name to the agent's allowed tools.
- Add a local agent: create an `Agent` in `Coordinator.__init__` and describe it in the `PLANNER` prompt.
- Add a remote agent: copy `internal_agent.py`, change its card, MCP server, and port, and register it in `Coordinator.remotes`.
- Replace mock data with real ITSM, directory, and advisory integrations.