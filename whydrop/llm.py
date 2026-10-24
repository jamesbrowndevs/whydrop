"""Nemotron lanes on NVIDIA's OpenAI-compatible API, with explicit routing + fallback.
Key is read from WHYDROP_NVIDIA_KEY_FILE (default ../secrets/nvidia_api_key.txt) or NVIDIA_API_KEY."""
from __future__ import annotations
import json, os, re, threading, time
from pathlib import Path
import requests

API = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
KEY_FILE = os.environ.get("WHYDROP_NVIDIA_KEY_FILE", str(Path(__file__).resolve().parents[2] / "secrets" / "nvidia_api_key.txt"))

# Lane -> ordered model preference. First model that answers wins; the routing log records which.
LANES = {
    "planner":  ["nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-3.5-super-vl-120b-a12b", "nvidia/nemotron-3-ultra-550b-a55b"],
    "analyst":  ["nvidia/nemotron-3-super-120b-a12b", "nvidia/nemotron-3.5-super-vl-120b-a12b", "nvidia/nemotron-3-ultra-550b-a55b"],
    "sql":      ["nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "nvidia/nemotron-3.5-lightning-30b-a3b", "nvidia/nemotron-3.5-super-vl-120b-a12b"],
    "verifier": ["nvidia/nemotron-3.5-lightning-30b-a3b", "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning", "nvidia/nemotron-3.5-super-vl-120b-a12b"],
}
for lane in LANES:  # override e.g. WHYDROP_MODEL_PLANNER=nvidia/nemotron-3-ultra-550b-a55b
    if os.environ.get(f"WHYDROP_MODEL_{lane.upper()}"):
        LANES[lane] = [os.environ[f"WHYDROP_MODEL_{lane.upper()}"]] + LANES[lane]

ROUTING_LOG: list[dict] = []
_lock = threading.Lock()
_dead: set[str] = set()

def set_route_hook(fn):
    """Per-thread callback fired on every routed call (used by the UI / logs)."""
    global _ROUTE_HOOK; _ROUTE_HOOK = fn
_ROUTE_HOOK = None

def _key() -> str:
    k = os.environ.get("NVIDIA_API_KEY") or (Path(KEY_FILE).read_text().strip() if Path(KEY_FILE).exists() else "")
    if not k:
        raise RuntimeError("NVIDIA API key not found")
    return k

def chat(lane: str, system: str, user: str, max_tokens: int = 4000, temperature: float = 0.2) -> str:
    last = None
    for model in LANES[lane]:
        if model in _dead:
            continue
        for attempt in range(3):
            t0 = time.time()
            try:
                r = requests.post(f"{API}/chat/completions", timeout=240, headers={"Authorization": f"Bearer {_key()}"},
                                  json={"model": model, "temperature": temperature, "max_tokens": max_tokens,
                                        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]})
            except requests.RequestException as e:
                last = f"{model}: {type(e).__name__}"; continue
            if r.status_code == 404:
                _dead.add(model); last = f"{model}: 404 not available"; break
            if r.status_code in (429, 500, 502, 503, 504):
                last = f"{model}: HTTP {r.status_code}"; time.sleep(2 * (attempt + 1)); continue
            if r.status_code != 200:
                last = f"{model}: HTTP {r.status_code} {r.text[:120]}"; break
            j = r.json(); msg = j["choices"][0]["message"]
            text = msg.get("content") or ""
            rec = {"lane": lane, "model": model, "latency_s": round(time.time() - t0, 1),
                   "tokens": (j.get("usage") or {}).get("total_tokens"), "fallback_from": [m for m in LANES[lane][:LANES[lane].index(model)]]}
            with _lock:
                ROUTING_LOG.append(rec)
            if _ROUTE_HOOK:
                try: _ROUTE_HOOK(rec)
                except Exception: pass
            if text.strip():
                return text
            last = f"{model}: empty content"
    raise RuntimeError(f"lane {lane}: no model answered ({last})")

def extract_json(text: str):
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    m = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    cands = [m.group(1)] if m else []
    for o, c in (("{", "}"), ("[", "]")):
        i, j = text.find(o), text.rfind(c)
        if i != -1 and j > i:
            cands.append(text[i:j + 1])
    for c in cands:
        try:
            return json.loads(c)
        except ValueError:
            continue
    raise ValueError(f"no JSON in model output: {text[:200]!r}")

def chat_json(lane: str, system: str, user: str, **kw):
    try:
        return extract_json(chat(lane, system, user, **kw))
    except ValueError:
        return extract_json(chat(lane, system, user + "\n\nReturn ONLY valid JSON, no prose.", **kw))
