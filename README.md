# WhyDrop: the agent that can explain *why* sales dropped

GenAI Works Open Agent Hackathon 2026, Track 2 "The Agent That Can Explain Why". Team: Nathan Melia (repo: jamesbrowndevs).
Built during the hackathon window (22-27 Oct 2026) using **Cursor** for development. No pre-existing code apart from the
vendored Meterless agentathon starter (Apache-2.0, `meterless/`, noted below).

Ask "Why did revenue drop in September?" and WhyDrop:
1. **Plans** 5-7 competing hypotheses (Nemotron planner lane), seeded with memories of past investigations (Meterless H-MEM).
2. **Tests** each with real SQL (Nemotron SQL lane) through one tool, `zetaris_sql(query)`, against a **Zetaris** federated layer
   joining CSV/JSON files and a Postgres database.
3. **Analyses** results into claims that must cite exact cells (query id, row, column, value).
4. **Verifies** every claim before showing it: re-runs the query on Zetaris (result hash must reproduce), checks every cited cell,
   checks every number in the claim text is grounded in a cited cell (or simple ratio/delta), and asks an independent Nemotron
   verifier lane. Claims that fail are struck out and never reach the answer.
5. Returns a **ranked explanation** (impact x confidence), **rejected hypotheses** with their evidence, recommended actions,
   every SQL query with its rows, and the model routing log.

## Demo video
▶️ **[Watch the 2.5-minute demo (MP4)](https://github.com/jamesbrowndevs/whydrop/releases/download/v1.0/whydrop_demo.mp4)** ([release v1.0](https://github.com/jamesbrowndevs/whydrop/releases/tag/v1.0)).
The voice-over is computer-generated (Piper TTS). The app footage is a real, unedited run that is sped up 16x while the agent works and labelled on screen.
The scripts that build it are in `demo/`.

## Architecture
```
question -> planner (Nemotron 3 Super / Ultra) -> hypothesis queue (TaskState + H-MEM recall)
         -> SQL lane (Nemotron 3 Nano reasoning) -> zetaris_sql -> Zetaris Lightning REST -> Spark
                                                         |-- WHYDROP_FILES: orders/products/marketing CSV, web_traffic/pricing/release JSON (filestore)
                                                         '-- WHYDROP_PG:    refunds, support_tickets (Postgres via JDBC)
         -> analyst lane (Super) -> verifier (deterministic + Nemotron verifier lane) -> ranked report -> H-MEM (findings remembered)
```

| Piece | File |
|---|---|
| Zetaris tool | `whydrop/zetaris.py` (`zetaris_sql`) |
| Federation setup | `zetaris/register.sh`, `zetaris/register.sql`, `zetaris/sqlite_to_pg.py` |
| Agent loop + verifier | `whydrop/agent.py` |
| Nemotron lanes / routing | `whydrop/llm.py` |
| Meterless memory adapter | `whydrop/memory.py`, `meterless/bridge.ts` |
| Report | `whydrop/report.py` |
| Evals | `evals/run_evals.py` (scores against `data/GROUND_TRUTH.md`) |

## Setup
Requirements: Docker (8 GB), Python 3.10+, Node 20+, an NVIDIA API key (build.nvidia.com, free).

1. **Zetaris**: run the local Zetaris platform (`docker compose up -d` in the `zetaris-platform` download, then `./verify.sh`).
2. **Data**: `python3 scripts/generate_data.py` (already generated in `data/`).
3. **Federate**: `ZP=/path/to/zetaris-platform ./zetaris/register.sh` - copies the files into the Zetaris customer-data volume,
   loads `support.db` into a Postgres database `whydrop_ops`, and registers both via Lightning DDL
   (`CREATE LIGHTNING FILESTORE TABLE ...`, `CREATE DATASOURCE ... OPTIONS (jdbcurl ...)`, `REGISTER DATASOURCE TABLES FROM WHYDROP_PG`).
   Then `docker compose restart driver` so the query engine picks up the new filestore tables.
   Check: `python3 -m whydrop.zetaris "select count(*) from WHYDROP_FILES.orders o join WHYDROP_PG.refunds r on r.order_id=o.order_id"`.
4. **Meterless**: `cd meterless && npm install && npm run setup` (vendors the H-MEM reference engine).
5. **Key**: put your key in `../secrets/nvidia_api_key.txt` (outside the repo) or export `NVIDIA_API_KEY`.
6. `pip install -r requirements.txt` (requests, streamlit, pandas)

## Usage
```bash
streamlit run app.py                                            # UI on http://localhost:8501: live steps, SQL + rows, model routing, ranked report
python3 -m whydrop "Why did revenue drop in September 2026?"     # CLI; report in reports/*.md + .json
python3 evals/run_evals.py                                      # 5 seeded questions, results in evals/results/
```
Env: `ZETARIS_URL` (default http://localhost:3000), `ZETARIS_ENV` (platform .env with admin creds) or `ZETARIS_EMAIL`/`ZETARIS_PASSWORD`,
`WHYDROP_MEMORY=local` (skip Node, local JSONL memory), `WHYDROP_MODEL_<LANE>` to pin a model per lane.

## Model routing (visible)
Each Nemotron call is logged with lane, model, latency, tokens and any fallback. You can see it in three places:
- streamed live in the UI's routing panel
- printed in the CLI log (`[whydrop] route sql -> nvidia/... (3.1s)`)
- summarised at the end of every report (`## Model routing`)

## How it works
Before planning, a fixed **signal scan** runs 7 generic change-detection queries on Zetaris: revenue by product and month, orders by channel,
refunds by product and reason (a Postgres × CSV join), refunds by half-month, support tickets, the event log, and the paid funnel. These rows are
shared with the planner and the analysts and can be cited. Then: plan → SQL → analyse → verify → ranked report → remember.

## Sponsor tech
- **Zetaris**: the only data access path. Two federated sources (file store + Postgres JDBC) queried as one SQL layer, cross-source joins
  (e.g. orders CSV x refunds Postgres). The verifier re-executes every cited query on Zetaris.
- **Meterless**: H-MEM engine (from the agentathon starter) stores every verified cause and rejected hypothesis with provenance
  (`source: whydrop:<run_id>`); the planner recalls them on the next investigation. Clean adapter seam (`MemoryStore`) with a local fallback.
- **NVIDIA Nemotron**: four lanes with explicit routing and fallback - planner/analyst (Nemotron 3 Super 120B, falling back to 3.5 Super / 3 Ultra),
  SQL (Nemotron 3 Nano reasoning), verifier (Nemotron 3.5 Lightning). Every report lists which model served which lane.

## Dependencies
`requests` (Python); `tsx` + Meterless H-MEM reference (Node); Zetaris platform (Docker). License: Apache-2.0 for vendored Meterless code.
