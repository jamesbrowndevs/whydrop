"""CLI: python -m whydrop "Why did revenue drop in September 2026?" [--out reports/]"""
import argparse, json, pathlib, re
from .agent import Investigation
from .report import to_markdown

ap = argparse.ArgumentParser(prog="whydrop"); ap.add_argument("question"); ap.add_argument("--out", default="reports"); ap.add_argument("--quiet", action="store_true")
a = ap.parse_args()
rep = Investigation(a.question, verbose=not a.quiet).run()
out = pathlib.Path(a.out); out.mkdir(exist_ok=True); slug = re.sub(r"\W+", "-", a.question.lower())[:50].strip("-")
(out / f"{slug}.json").write_text(json.dumps(rep, indent=1, default=str)); md = to_markdown(rep); (out / f"{slug}.md").write_text(md)
print(md.split("## Queries")[0]); print(f"full report: {out / (slug + '.md')}")
