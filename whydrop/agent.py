"""WhyDrop agent loop: plan -> SQL -> run on Zetaris -> analyse -> verify -> ranked, cited explanation."""
from __future__ import annotations
import json, re, time, uuid
from concurrent.futures import ThreadPoolExecutor
from . import llm
from .zetaris import zetaris_sql, schema_text, ZetarisError
from .memory import get_store, TaskState

MAX_ROWS_TO_MODEL = 60

PLANNER_SYS = """You are the planning lane of WhyDrop, an analyst agent for a small online seller.
Given a business 'why' question and the data catalogue, propose 5-7 distinct, testable hypotheses that could explain it.
Cover different mechanisms (traffic, conversion, pricing, refunds/quality, channel/marketing, product mix, seasonality, geography).
Always check the event logs (pricing_changes, release_log) and refunds/support_tickets for changes that coincide with the period, and paid-channel efficiency (spend vs clicks vs sessions vs landing_404s vs orders).
Include hypotheses that may turn out FALSE - they will be tested and rejected with evidence.
Return JSON: {"hypotheses":[{"id":"H1","statement":"...","mechanism":"...","test_plan":"which tables/metrics to compare, e.g. Aug vs Sep"}]}"""

SQL_SYS = """You are the SQL lane of WhyDrop. Write Spark SQL for the Zetaris federated layer to test ONE hypothesis.
Write 1-3 SELECT queries, each small (aggregate! <= 40 result rows), comparing periods (usually by month, or pre/post an event date).
Return JSON: {"queries":[{"purpose":"...","sql":"SELECT ..."}]}"""

SQL_FIX_SYS = """You fix a failing Spark SQL query for Zetaris. Return JSON {"sql":"SELECT ..."} only."""

ANALYST_SYS = """You are the analyst lane of WhyDrop. You receive one hypothesis and the exact query results that test it.
Decide verdict: "supported", "rejected" or "inconclusive". Make 1-3 claims. Every number in a claim MUST be copied from a cited cell.
Cite cells as evidence: {"query_id":"Q..","row":<0-based row index>,"column":"<column name>","value":<exact cell value>}.
estimated_impact_usd: rough monthly net revenue explained by this cause (0 if rejected).
Return JSON: {"verdict":"...","summary":"one sentence","estimated_impact_usd":0,
 "claims":[{"text":"...","evidence":[{"query_id":"Q1","row":0,"column":"n","value":123}],"confidence":0.0}],
 "recommended_action":"..."}"""

VERIFIER_SYS = """You are the verifier lane of WhyDrop. Given a claim and the cited result rows, answer whether the rows support the claim.
Return JSON {"supported": true|false, "reason":"short"}"""


class Investigation:
    def __init__(self, question: str, workers: int = 4, verbose: bool = True):
        self.q = question; self.workers = workers; self.verbose = verbose
        self.state = TaskState(question, time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4])
        self.mem = get_store(); self._qn = 0

    def log(self, *a):
        if self.verbose: print("[whydrop]", *a, flush=True)

    # ---- tools -----------------------------------------------------------------------
    def run_sql(self, sql: str, purpose: str, hyp_id: str) -> dict:
        self._qn += 1; qid = f"Q{self._qn}"
        rec = {"id": qid, "hypothesis": hyp_id, "purpose": purpose, "sql": sql}
        for attempt in range(2):
            try:
                res = zetaris_sql(rec["sql"]); rec.update(res, ok=True); break
            except ZetarisError as e:
                rec.update(ok=False, error=str(e)[:400])
                if attempt == 0:
                    try:
                        fix = llm.chat_json("sql", SQL_FIX_SYS, f"Catalogue:\n{schema_text()}\n\nQuery:\n{rec['sql']}\n\nError:\n{e}", max_tokens=3000)
                        rec["sql_original"] = rec["sql"]; rec["sql"] = fix["sql"]
                    except Exception:
                        break
        self.state.queries[qid] = rec
        self.log(f"{qid} [{hyp_id}] {'ok' if rec.get('ok') else 'ERR'} {rec.get('row_count','')} rows - {purpose[:70]}")
        return rec

    # ---- stages ----------------------------------------------------------------------
    def plan(self):
        past = self.mem.recall(self.q, k=6)
        past_txt = "\n".join(f"- ({m.get('id')}) {m['content'][:300]}" for m in past) or "(none)"
        out = llm.chat_json("planner", PLANNER_SYS, f"Question: {self.q}\n\nData catalogue (Zetaris):\n{schema_text()}\n\n"
                            f"Memory from past investigations (Meterless H-MEM; use as priors, re-test anyway):\n{past_txt}")
        self.state.hypotheses = [dict(h, status="queued") for h in out["hypotheses"][:7]]
        self.state.memory_recalled = past
        self.log(f"planned {len(self.state.hypotheses)} hypotheses (recalled {len(past)} memories)")

    def test(self, h: dict) -> dict:
        h["status"] = "testing"
        try:
            qs = llm.chat_json("sql", SQL_SYS, f"Hypothesis {h['id']}: {h['statement']}\nTest plan: {h.get('test_plan','')}\n"
                               f"Original question: {self.q}\n\nCatalogue:\n{schema_text()}", max_tokens=6000)["queries"][:3]
        except Exception as e:
            h["status"] = "error"; return {"hypothesis": h, "verdict": "inconclusive", "claims": [], "error": str(e)}
        recs = [self.run_sql(q["sql"], q.get("purpose", ""), h["id"]) for q in qs]
        payload = []
        for r in recs:
            payload.append({"query_id": r["id"], "purpose": r["purpose"], "sql": r["sql"],
                            **({"rows": r["rows"][:MAX_ROWS_TO_MODEL]} if r.get("ok") else {"error": r.get("error")})})
        if not any(r.get("ok") for r in recs):
            h["status"] = "inconclusive"; return {"hypothesis": h, "verdict": "inconclusive", "claims": [], "queries": [r["id"] for r in recs]}
        a = llm.chat_json("analyst", ANALYST_SYS, f"Question: {self.q}\nHypothesis {h['id']}: {h['statement']}\n\nResults:\n{json.dumps(payload, default=str)}", max_tokens=5000)
        a["hypothesis"] = h; a["queries"] = [r["id"] for r in recs]
        h["status"] = a.get("verdict", "inconclusive")
        return a

    def verify(self, f: dict) -> dict:
        """Every claim is re-checked: (1) each cited query is re-run on Zetaris and must reproduce the same
        result hash; (2) each cited cell must exist and match; (3) every number in the claim text must be
        grounded in a cited cell (or a simple ratio/difference/% change of two); (4) a second Nemotron lane
        reads claim + rows and must not contradict it."""
        rerun = {}
        for c in f.get("claims", []):
            checks = []; ok = True; cited = []
            ev = c.get("evidence") or []
            if not ev: ok = False; checks.append("no evidence cited")
            for e in ev:
                q = self.state.queries.get(str(e.get("query_id")))
                if not q or not q.get("ok"): ok = False; checks.append(f"{e.get('query_id')}: unknown/failed query"); continue
                if q["id"] not in rerun:
                    try: rerun[q["id"]] = zetaris_sql(q["sql"])["result_hash"] == q["result_hash"]
                    except ZetarisError: rerun[q["id"]] = False
                if not rerun[q["id"]]: ok = False; checks.append(f"{q['id']}: re-run did not reproduce")
                try:
                    cell = q["rows"][int(e["row"])][e["column"]]
                except (KeyError, IndexError, ValueError, TypeError):
                    ok = False; checks.append(f"{q['id']} row {e.get('row')} col {e.get('column')}: cell not found"); continue
                if not _same(cell, e.get("value")): ok = False; checks.append(f"{q['id']}[{e['row']}].{e['column']}={cell} != cited {e.get('value')}")
                cited.append(cell); e["actual"] = cell
            ungrounded = [n for n in _numbers(c.get("text", "")) if not _grounded(n, cited)]
            if ungrounded: ok = False; checks.append(f"ungrounded numbers in text: {ungrounded[:5]}")
            if ok:
                rows = {e["query_id"]: self.state.queries[e["query_id"]]["rows"][:MAX_ROWS_TO_MODEL] for e in ev}
                try:
                    v = llm.chat_json("verifier", VERIFIER_SYS, f"Claim: {c['text']}\nRows:\n{json.dumps(rows, default=str)}", max_tokens=2000)
                    c["llm_check"] = v
                    if v.get("supported") is False: ok = False; checks.append(f"verifier lane: {v.get('reason','')}")
                except Exception as ex:
                    c["llm_check"] = {"error": str(ex)[:100]}
            c["verified"] = ok; c["checks"] = checks or ["cells match, query reproduced, numbers grounded"]
        return f

    # ---- main ------------------------------------------------------------------------
    def run(self) -> dict:
        t0 = time.time(); llm.ROUTING_LOG.clear()
        self.plan(); self.state.save()
        with ThreadPoolExecutor(self.workers) as ex:
            findings = list(ex.map(self.test, self.state.hypotheses))
        self.log("verifying claims")
        with ThreadPoolExecutor(self.workers) as ex:
            findings = list(ex.map(self.verify, findings))
        self.state.findings = findings
        report = self.report(findings, time.time() - t0)
        self.remember(report); self.state.report = report; self.state.save()
        return report

    def report(self, findings, elapsed) -> dict:
        causes, rejected, other = [], [], []
        for f in findings:
            vc = [c for c in f.get("claims", []) if c.get("verified")]
            conf = round(sum(float(c.get("confidence", 0.5)) for c in vc) / len(vc), 2) if vc else 0.0
            item = {"hypothesis": f["hypothesis"]["statement"], "id": f["hypothesis"]["id"], "verdict": f.get("verdict"),
                    "summary": f.get("summary", ""), "impact_usd": _f(f.get("estimated_impact_usd")), "confidence": conf,
                    "claims": f.get("claims", []), "queries": f.get("queries", []), "action": f.get("recommended_action", "")}
            if f.get("verdict") == "supported" and vc: causes.append(item)
            elif f.get("verdict") == "rejected" and vc: rejected.append(item)
            else: other.append(item)
        causes.sort(key=lambda i: -(i["impact_usd"] * max(i["confidence"], 0.1)))
        return {"question": self.q, "run_id": self.state.run_id, "causes": causes, "rejected": rejected, "unverified_or_inconclusive": other,
                "queries": self.state.queries, "routing": list(llm.ROUTING_LOG), "memory_backend": self.mem.backend,
                "memory_recalled": getattr(self.state, "memory_recalled", []), "elapsed_s": round(elapsed, 1)}

    def remember(self, rep):
        items = [{"content": f"[{rep['question']}] VERIFIED CAUSE: {c['hypothesis']} - {c['summary']} (conf {c['confidence']}, queries {','.join(c['queries'])})", "type": "finding", "source": f"whydrop:{rep['run_id']}"} for c in rep["causes"]]
        items += [{"content": f"[{rep['question']}] REJECTED: {r['hypothesis']} - {r['summary']}", "type": "finding", "source": f"whydrop:{rep['run_id']}"} for r in rep["rejected"]]
        if items:
            try: rep["memory_ids"] = self.mem.remember(items)
            except Exception as e: rep["memory_error"] = str(e)[:200]


def _f(x):
    try: return float(str(x).replace("$", "").replace(",", ""))
    except (TypeError, ValueError): return 0.0

def _same(a, b):
    try: fa, fb = float(a), float(str(b).replace(",", "").replace("$", "")); return abs(fa - fb) <= max(0.01 * abs(fa), 0.011)
    except (TypeError, ValueError): return str(a).strip().lower() == str(b).strip().lower()

_NUM = re.compile(r"(?<![\w.])\$?(-?\d[\d,]*\.?\d*)%?")
def _numbers(text):
    out = []
    for m in _NUM.finditer(text):
        s = m.group(1).replace(",", "").rstrip(".")
        try: v = float(s)
        except ValueError: continue
        if re.fullmatch(r"20\d\d", s) or (v <= 31 and float(v).is_integer() and abs(v) < 13): continue  # years / small ordinals / months / days
        out.append(v)
    return out

def _grounded(n, cited):
    nums = [float(c) for c in cited if isinstance(c, (int, float))]
    if any(abs(n - c) <= max(0.015 * abs(c), 0.6) for c in nums): return True
    for a in nums:
        for b in nums:
            if a == b or b == 0: continue
            for d in (a - b, a / b, a / b * 100, (a - b) / b * 100, a + b):
                if abs(abs(n) - abs(d)) <= max(0.03 * abs(d), 0.6): return True
    return False
