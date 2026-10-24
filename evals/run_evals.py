"""Run the 5 seeded 'why' questions and score against data/GROUND_TRUTH.md (planted causes).
The ground truth is never shown to the agent; scoring is keyword-based over VERIFIED claims only."""
import json, pathlib, re, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from whydrop.agent import Investigation
from whydrop.report import to_markdown

def text(items):
    return " ".join(i["hypothesis"] + " " + i["summary"] + " " + " ".join(c["text"] for c in i["claims"] if c.get("verified")) for i in items).lower()

CAUSE = {  # planted cause -> regex any-of, must appear in a SUPPORTED, verified cause
    "broken_meta_campaign": r"paid[_ ]social|meta|fall_launch|404|landing",
    "p001_price_rise": r"p001|notion|price (rise|increase)|\$?29",
    "p003_refund_spike": r"p003|scraper|corrupt|v2\.0|zip",
}
EVALS = [
    ("Why did revenue drop in September 2026?", ["broken_meta_campaign", "p001_price_rise", "p003_refund_spike"], None),
    ("Is our ad spend still working?", ["broken_meta_campaign"], None),
    ("Why did Notion Freelance OS sales fall even though we raised the price?", ["p001_price_rise"], None),
    ("Why are refunds up in the second half of September?", ["p003_refund_spike"], None),
    ("Did email marketing cause the drop?", [], "email"),
]
def score(rep, need, reject_kw):
    sup = text(rep["causes"]); rej = text(rep["rejected"]); detail = {}
    for c in need: detail[c] = bool(re.search(CAUSE[c], sup))
    if reject_kw:  # pass if email is rejected (flat) and NOT presented as a supported cause
        # a supported cause "blames" email only if email is its subject and it is not negated (e.g. "not an email failure", "flat")
        neg = re.compile(r"\b(not|no|unrelated|rather than|flat|did not|didn't)\b")
        email_supported = any(re.match(r"\W*(the )?email", i["hypothesis"].lower()) and not neg.search((i["hypothesis"] + " " + i["summary"]).lower()) for i in rep["causes"])
        detail["email_rejected"] = (reject_kw in rej) and not email_supported
    return all(detail.values()), detail

def _run(q):
    for attempt in range(2):
        try: return Investigation(q, verbose=False).run()
        except Exception as e: err = repr(e)
    return {"question": q, "run_id": "error", "causes": [], "rejected": [], "unverified_or_inconclusive": [], "queries": {}, "routing": [], "memory_backend": "-", "elapsed_s": 0, "error": err}

if __name__ == "__main__":
    from concurrent.futures import ProcessPoolExecutor
    out = pathlib.Path(__file__).parent / "results"; out.mkdir(exist_ok=True); results = []
    with ProcessPoolExecutor(len(EVALS)) as ex:
        reps = list(ex.map(_run, [q for q, _, _ in EVALS]))
    for i, ((q, need, rk), rep) in enumerate(zip(EVALS, reps), 1):
        ok, d = score(rep, need, rk)
        (out / f"q{i}.md").write_text(to_markdown(rep)); (out / f"q{i}.json").write_text(json.dumps(rep, indent=1, default=str))
        results.append({"q": q, "pass": ok, "detail": d, "causes": len(rep["causes"]), "rejected": len(rep["rejected"]), "elapsed_s": rep["elapsed_s"]})
        print(f"Q{i} {'PASS' if ok else 'FAIL'} {d} ({rep['elapsed_s']}s)", flush=True)
    planted = {"broken_meta_campaign": False, "p001_price_rise": False, "p003_refund_spike": False}
    for r in results:
        for k, v in r["detail"].items():
            if k in planted and v and r["q"].startswith("Why did revenue"): planted[k] = True
    summary = {"date": time.strftime("%Y-%m-%d %H:%M %Z"), "questions_passed": sum(r["pass"] for r in results), "of": len(results),
               "q1_planted_causes_found": sum(planted.values()), "results": results}
    (out / "summary.json").write_text(json.dumps(summary, indent=1)); print(json.dumps({k: summary[k] for k in ("questions_passed", "of", "q1_planted_causes_found")}))
