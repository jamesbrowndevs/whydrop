"""Task state + memory adapter. Default backend: Meterless H-MEM engine (via meterless/bridge.ts,
the agentathon-starter's vendored reference implementation). Fallback: a local JSONL store with the
same interface (WHYDROP_MEMORY=local), so the agent never depends on Node being present."""
from __future__ import annotations
import json, os, subprocess, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE_DIR = ROOT / "meterless"
STATE_DIR = Path(os.environ.get("WHYDROP_STATE", ROOT / ".whydrop-state"))

class MemoryStore:
    backend = "base"
    def remember(self, items: list[dict]) -> list[str]: ...
    def recall(self, text: str, k: int = 8) -> list[dict]: ...

class HMemStore(MemoryStore):
    backend = "meterless-hmem"
    def __init__(self):
        if not (BRIDGE_DIR / "vendor" / "hmem").exists():
            raise RuntimeError("Meterless H-MEM not vendored: run `cd meterless && npm install && npm run setup`")
        self.dir = STATE_DIR / "hmem"; self.dir.mkdir(parents=True, exist_ok=True)
    def _call(self, ops):
        p = subprocess.run(["npx", "--no-install", "tsx", "bridge.ts"], cwd=BRIDGE_DIR, input=json.dumps(ops),
                           capture_output=True, text=True, timeout=120, env={**os.environ, "WHYDROP_HMEM_DIR": str(self.dir)})
        if p.returncode != 0:
            raise RuntimeError(f"hmem bridge failed: {p.stderr[-300:]}")
        return json.loads(p.stdout)["results"]
    def remember(self, items):
        return [r["id"] for r in self._call([{"op": "add", "content": i["content"], "type": i.get("type", "general"), "source": i.get("source", "whydrop")} for i in items])]
    def recall(self, text, k=8):
        return self._call([{"op": "query", "text": text}])[0]["memories"][:k]

class LocalStore(MemoryStore):
    backend = "local-jsonl"
    def __init__(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True); self.f = STATE_DIR / "memory.jsonl"
    def remember(self, items):
        ids = []
        with self.f.open("a") as fh:
            for i in items:
                ids.append(f"loc-{time.time_ns()}"); fh.write(json.dumps({"id": ids[-1], **i}) + "\n")
        return ids
    def recall(self, text, k=8):
        if not self.f.exists(): return []
        words = set(text.lower().split()); out = []
        for l in self.f.read_text().splitlines():
            m = json.loads(l); s = len(words & set(m["content"].lower().split())) / (len(words) or 1)
            if s > 0.1: out.append({**m, "relevance": s})
        return sorted(out, key=lambda m: -m["relevance"])[:k]

def get_store() -> MemoryStore:
    if os.environ.get("WHYDROP_MEMORY", "hmem") == "local":
        return LocalStore()
    try:
        return HMemStore()
    except Exception as e:
        print(f"[memory] H-MEM unavailable ({e}); using local store"); return LocalStore()

class TaskState:
    """Investigation state: hypothesis queue, query log, findings. Persisted per run as JSON."""
    def __init__(self, question: str, run_id: str):
        self.question, self.run_id = question, run_id
        self.hypotheses: list[dict] = []; self.queries: dict[str, dict] = {}; self.findings: list[dict] = []
        self.dir = STATE_DIR / "runs" / run_id; self.dir.mkdir(parents=True, exist_ok=True)
    def save(self):
        (self.dir / "state.json").write_text(json.dumps(self.__dict__ | {"dir": str(self.dir)}, indent=1, default=str))
