"""Render docs/slides.html -> docs/WhyDrop_slides.pdf with the latest eval results (needs Chrome/Chromium)."""
import json, pathlib, subprocess, shutil
d = pathlib.Path(__file__).parent; s = json.load(open(d.parent / "evals/results/summary.json"))
rows = "".join(f"<tr><td>{r['q']}</td><td>{'✅ pass' if r['pass'] else '❌ fail'}</td><td>{r['causes']}</td><td>{r['rejected']}</td><td>{r['elapsed_s']:.0f}s</td></tr>" for r in s["results"])
tbl = f"<table><tr><th>Question</th><th>Result</th><th>Causes</th><th>Rejected</th><th>Time</th></tr>{rows}</table><p><b>{s['questions_passed']}/{s['of']} passed</b> · {s['q1_planted_causes_found']}/3 planted causes found on the headline question · run {s['date']}</p>"
html = (d / "slides.html").read_text().replace("__EVALTABLE__", tbl); out = d / "_slides_built.html"; out.write_text(html)
chrome = shutil.which("google-chrome") or shutil.which("chromium")
subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={d/'WhyDrop_slides.pdf'}", out.as_uri()], check=True, capture_output=True)
out.unlink(); print(d / "WhyDrop_slides.pdf")
