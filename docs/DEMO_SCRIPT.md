# WhyDrop demo video script (target 2:30, max 3:00)
Record: the Streamlit UI (`streamlit run app.py`) + the Zetaris UI (http://localhost:3000). To save time, pre-run one investigation and cut the waiting.

| Time | Screen | Voice-over |
|---|---|---|
| 0:00–0:15 | Title slide | "Small sellers see revenue drop and get a chart, not an answer. WhyDrop is an agent that explains *why*, and proves every claim." |
| 0:15–0:35 | Zetaris UI: WHYDROP_FILES + WHYDROP_PG data sources | "The data is scattered: order CSVs, ad spend, traffic JSON, and refunds in Postgres. Zetaris federates all of it into one SQL layer, and that is the agent's only tool." |
| 0:35–0:50 | WhyDrop UI, type "Why did revenue drop in September 2026?", click Investigate | "I ask the question in plain English." |
| 0:50–1:20 | Left: signal scan + hypotheses streaming. Routing panel | "It starts with a signal scan on Zetaris, recalls past findings from Meterless memory, and the Nemotron planner proposes competing hypotheses. You can see the routing: Super plans and analyses, Nano writes SQL, Lightning verifies." |
| 1:20–1:45 | Right: expand a query with a cross-source join, show its rows | "Each hypothesis is tested with real SQL. Here it joins Postgres refunds to CSV orders, through Zetaris." |
| 1:45–2:15 | Ranked report: causes, confidence, evidence cites, struck-out claims, rejected list | "The answer is ranked by impact: a broken Meta campaign sending clicks to 404 pages, a price rise that cost buyers, and a corrupted v2.0 release driving refunds. Every number cites a cell. Claims that fail verification are struck out. Email was tested and rejected." |
| 2:15–2:35 | Eval summary + architecture slide | "On 5 seeded questions with planted causes, WhyDrop scored 5 of 5 on the latest run (runs vary; earlier runs scored 3 and 4). Zetaris for data, Meterless for memory, Nemotron for reasoning, built in Cursor." |
| 2:35–2:45 | Repo URL | "github.com/jamesbrowndevs/whydrop" |
