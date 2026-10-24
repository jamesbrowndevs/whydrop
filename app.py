"""WhyDrop Streamlit UI: streams agent steps live, shows every SQL query + rows, model routing, and the ranked report.
Run: streamlit run app.py"""
import json, queue, threading, time
import pandas as pd
import streamlit as st
from whydrop.agent import Investigation
from whydrop.report import to_markdown

st.set_page_config(page_title="WhyDrop", page_icon="📉", layout="wide")
st.title("📉 WhyDrop — the agent that can explain *why*")
st.caption("Zetaris federated SQL · Meterless H-MEM memory · NVIDIA Nemotron lanes · every claim verified against query rows")

EXAMPLES = ["Why did revenue drop in September 2026?", "Is our ad spend still working?",
            "Why did Notion Freelance OS sales fall even though we raised the price?",
            "Why are refunds up in the second half of September?", "Did email marketing cause the drop?"]
with st.sidebar:
    ex = st.selectbox("Example questions", EXAMPLES)
    q = st.text_area("Your question", ex, height=90)
    go = st.button("Investigate", type="primary", width="stretch")
    st.markdown("**Lanes**: planner/analyst → Nemotron 3 Super · SQL → Nemotron 3 Nano · verifier → Nemotron 3.5 Lightning")

LANE_ICON = {"planner": "🧭", "sql": "🧮", "analyst": "🔎", "verifier": "✅"}

def render_report(rep):
    st.subheader("Ranked explanation (verified claims only)")
    if not rep["causes"]: st.info("No hypothesis was supported by verified evidence.")
    for i, c in enumerate(rep["causes"], 1):
        with st.container(border=True):
            st.markdown(f"### {i}. {c['hypothesis']}")
            a, b = st.columns(2); a.metric("Confidence", f"{c['confidence']:.2f}"); b.metric("Est. impact / month", f"${c['impact_usd']:,.0f}")
            st.write(c["summary"])
            for cl in c["claims"]:
                cites = "; ".join(f"{e['query_id']} row {e['row']} `{e['column']}`={e.get('actual', e.get('value'))}" for e in cl.get("evidence", []))
                if cl.get("verified"): st.markdown(f"- ✅ {cl['text']}  \n  <small>evidence: {cites}</small>", unsafe_allow_html=True)
                else: st.markdown(f"- ❌ ~~{cl.get('text','')}~~ <small>(excluded: {'; '.join(cl.get('checks', []))})</small>", unsafe_allow_html=True)
            if c.get("action"): st.success(f"Recommended action: {c['action']}")
    with st.expander(f"Rejected hypotheses ({len(rep['rejected'])})", expanded=True):
        for r in rep["rejected"]: st.markdown(f"- **{r['hypothesis']}** — {r['summary']}")
    with st.expander(f"Inconclusive / failed verification ({len(rep['unverified_or_inconclusive'])})"):
        for r in rep["unverified_or_inconclusive"]: st.markdown(f"- {r['hypothesis']} ({r['verdict']})")
    st.subheader("Model routing")
    if rep["routing"]:
        df = pd.DataFrame(rep["routing"])
        st.dataframe(df.groupby(["lane", "model"]).agg(calls=("latency_s", "size"), avg_latency_s=("latency_s", "mean"), tokens=("tokens", "sum")).reset_index(), width="stretch")
    st.download_button("Download report (Markdown)", to_markdown(rep), file_name="whydrop_report.md")

if go and q.strip():
    events: queue.Queue = queue.Queue(); box = {}
    def worker():
        try: box["rep"] = Investigation(q.strip(), verbose=True, on_event=events.put).run()
        except Exception as e: box["err"] = repr(e)
    t = threading.Thread(target=worker, daemon=True); t.start()
    left, right = st.columns([1, 1])
    left.subheader("Agent steps (live)"); right.subheader("SQL on Zetaris + evidence")
    steps, routes = left.container(height=420), left.container(height=220)
    sqlbox = right.container(height=660)
    status = st.status("Investigating… (typically 5–9 minutes)", expanded=False); t0 = time.time()
    while t.is_alive() or not events.empty():
        try: ev = events.get(timeout=0.5)
        except queue.Empty: status.update(label=f"Investigating… {time.time()-t0:.0f}s"); continue
        k, d = ev["kind"], ev["data"]
        if k == "route":
            routes.markdown(f"{LANE_ICON.get(d['lane'],'•')} **{d['lane']}** → `{d['model']}` · {d['latency_s']}s" + (f" · fell back from {d['fallback_from']}" if d.get("fallback_from") else ""))
        elif k == "query":
            with sqlbox.expander(f"{d['id']} [{d['hypothesis']}] {'✅' if d.get('ok') else '⚠️'} {d.get('purpose','')[:80]}"):
                st.code(d["sql"], language="sql")
                if d.get("ok"): st.dataframe(pd.DataFrame(d.get("rows", [])[:50]), width="stretch")
                else: st.error(d.get("error"))
            steps.write(f"🧮 {ev['text']}")
        elif k == "plan":
            steps.markdown("🧭 **Hypotheses**\n" + "\n".join(f"- {h['id']}: {h['statement']}" for h in d))
        elif k == "finding":
            icon = {"supported": "🟢", "rejected": "⚪"}.get(d["verdict"], "🟡"); steps.write(f"{icon} {ev['text']}")
        else: steps.write(f"• {ev['text']}")
    status.update(label=f"Done in {time.time()-t0:.0f}s", state="complete" if "rep" in box else "error")
    if "err" in box: st.error(box["err"])
    else: st.session_state["rep"] = box["rep"]
if "rep" in st.session_state:
    render_report(st.session_state["rep"])
