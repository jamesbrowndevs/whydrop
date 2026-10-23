"""Render an investigation report as Markdown: ranked causes, each claim citing its query + rows."""
from __future__ import annotations
import json

def _cite(c):
    return "; ".join(f"`{e.get('query_id')}` row {e.get('row')} `{e.get('column')}`={e.get('actual', e.get('value'))}" for e in c.get("evidence", []))

def to_markdown(rep: dict) -> str:
    L = [f"# WhyDrop: {rep['question']}", "", f"_run {rep['run_id']} - {rep['elapsed_s']}s - memory: {rep['memory_backend']} - data: Zetaris (WHYDROP_FILES + WHYDROP_PG)_", ""]
    L.append("## Ranked explanation (verified claims only)")
    if not rep["causes"]: L.append("_No hypothesis was supported by verified evidence._")
    for i, c in enumerate(rep["causes"], 1):
        L += [f"### {i}. {c['hypothesis']}", f"**Confidence {c['confidence']:.2f}** - est. impact ${c['impact_usd']:,.0f}/month - {c['summary']}", ""]
        for cl in c["claims"]:
            if cl.get("verified"): L.append(f"- {cl['text']}  \n  _evidence: {_cite(cl)}_")
            else: L.append(f"- ~~{cl.get('text','')}~~ (UNVERIFIED, excluded: {'; '.join(cl.get('checks', []))})")
        if c.get("action"): L.append(f"\n**Recommended action:** {c['action']}")
        L.append("")
    L.append("## Rejected hypotheses (tested, evidence says no)")
    for r in rep["rejected"]:
        vc = [cl for cl in r["claims"] if cl.get("verified")]
        L.append(f"- **{r['hypothesis']}** - {r['summary']}" + (f"  \n  _evidence: {_cite(vc[0])}_" if vc else ""))
    if rep["unverified_or_inconclusive"]:
        L.append("\n## Inconclusive / failed verification")
        for r in rep["unverified_or_inconclusive"]:
            L.append(f"- {r['hypothesis']} ({r['verdict']})")
    L.append("\n## Queries (run on Zetaris)")
    for q in rep["queries"].values():
        L.append(f"<details><summary>{q['id']} [{q['hypothesis']}] {q['purpose']} - {'%s rows' % q.get('row_count') if q.get('ok') else 'ERROR'}</summary>\n\n```sql\n{q['sql']}\n```\n\n"
                 + (f"```json\n{json.dumps(q.get('rows', [])[:15], default=str)}\n```" if q.get("ok") else str(q.get("error", ""))) + "\n</details>")
    L.append("\n## Model routing (Nemotron lanes)")
    agg = {}
    for r in rep["routing"]: agg.setdefault((r["lane"], r["model"]), []).append(r["latency_s"])
    for (lane, m), v in sorted(agg.items()): L.append(f"- {lane}: `{m}` x{len(v)} (avg {sum(v)/len(v):.1f}s)")
    return "\n".join(L) + "\n"
