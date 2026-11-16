import json, re, sqlite3, time, uuid

_PATTERNS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),
    re.compile(r"\b(?:sk|key|token|pwd)[-_=:][A-Za-z0-9_\-]{8,}\b", re.I),
]


def redact(text: str) -> str:
    for p in _PATTERNS:
        text = p.sub("[REDACTED]", text)
    return text


class Tracker:
    def __init__(self, path: str = ":memory:"):
        self.db = sqlite3.connect(path)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(task_id TEXT PRIMARY KEY, request_id TEXT,
          tenant_id TEXT, agent TEXT, status TEXT, detail TEXT,
          created_at REAL, updated_at REAL);
        CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT,
          ts REAL, request_id TEXT, task_id TEXT, type TEXT, payload TEXT);""")

    def new_request(self) -> str:
        return "r-" + uuid.uuid4().hex[:8]

    def create_task(self, request_id, agent, tenant_id="default") -> str:
        tid, now = "t-" + uuid.uuid4().hex[:8], time.time()
        self.db.execute("INSERT INTO tasks VALUES(?,?,?,?,?,?,?,?)",
                        (tid, request_id, tenant_id, agent, "queued", "", now, now))
        self.event(request_id, tid, "task.created", {"agent": agent})
        return tid

    def update(self, request_id, task_id, status, detail=""):
        self.db.execute("UPDATE tasks SET status=?, detail=?, updated_at=? WHERE task_id=?",
                        (status, redact(detail)[:500], time.time(), task_id))
        self.event(request_id, task_id, f"task.{status}", {"detail": detail[:200]})

    def event(self, request_id, task_id, type_, payload):
        self.db.execute("INSERT INTO events(ts,request_id,task_id,type,payload) VALUES(?,?,?,?,?)",
                        (time.time(), request_id, task_id, type_, redact(json.dumps(payload))))
        self.db.commit()

    def tasks(self, request_id, tenant_id="default"):
        rows = self.db.execute("SELECT task_id,agent,status FROM tasks "
                               "WHERE request_id=? AND tenant_id=?",
                               (request_id, tenant_id)).fetchall()
        return [dict(zip(("task_id", "agent", "status"), r)) for r in rows]