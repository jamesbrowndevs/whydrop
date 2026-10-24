# WhyDrop: submission write-up
GenAI Works Open Agent Hackathon 2026 · Track 2 "The Agent That Can Explain Why" · Team: Nathan Melia · Repo: https://github.com/jamesbrowndevs/whydrop

## What it does
A small online seller asks "Why did revenue drop in September?". WhyDrop runs a fixed signal scan over all its data, plans 5–7 competing
hypotheses, tests each one with real SQL, and returns a ranked explanation. Every claim cites exact cells (query, row, column,
value), and every claim is re-verified before it is shown. Hypotheses that the evidence contradicts are listed as rejected, with the evidence.

## Zetaris integration
- **The only data path.** The agent has one tool, `zetaris_sql(query)` (`whydrop/zetaris.py`), which calls the local Zetaris platform's
  Lightning REST API (Spark SQL engine).
- **Federation across two kinds of source** (`zetaris/register.sh`, `zetaris/register.sql`):
  - `WHYDROP_FILES`: Lightning filestore tables over CSV (orders, products, marketing_spend) and JSON (web_traffic, pricing_changes, release_log).
  - `WHYDROP_PG`: a Postgres database (refunds, support_tickets) registered with `CREATE DATASOURCE … jdbcurl` + `REGISTER DATASOURCE TABLES`.
- **Cross-source joins** are part of normal operation, e.g. Postgres `refunds` × CSV `orders` to attribute refunds to products.
- **Schema profiling via Zetaris:** distinct categorical values are pulled through Zetaris at start-up so the SQL lane uses exact filter strings.
- **Verification on Zetaris:** the verifier re-executes every cited query on Zetaris, and the result hash must reproduce.

## Meterless integration
- **H-MEM memory engine** from the Meterless agentathon starter (`meterless/`, vendored reference engine, Apache-2.0), called via
  `meterless/bridge.ts` from the Python adapter `whydrop/memory.py`.
- After each run, every verified cause and rejected hypothesis is stored with provenance (`source: whydrop:<run_id>`). At the start of the
  next investigation the planner recalls relevant memories as priors (it still re-tests them).
- Task state (hypothesis queue, queries, findings) is persisted per run. A local JSONL fallback with the same interface
  (`WHYDROP_MEMORY=local`) keeps the agent running without Node.

## NVIDIA Nemotron's role
All reasoning runs on Nemotron via NVIDIA's OpenAI-compatible API (`whydrop/llm.py`), split into lanes with explicit routing and fallback:

| Lane | Primary model | Job |
|---|---|---|
| planner | nemotron-3-super-120b-a12b | hypotheses from the question, signal scan and memory |
| sql | nemotron-3-nano-omni-30b-a3b-reasoning | Spark SQL per hypothesis; fixes failing SQL |
| analyst | nemotron-3-super-120b-a12b | verdict + claims citing exact cells |
| verifier | nemotron-3.5-lightning-30b-a3b | independent check of each claim against its rows |

In practice the API often serves planner and analyst calls from the fallback, Nemotron 3.5 Super VL, when 3 Super errors or is busy. Every call is logged (lane, model, latency, tokens, fallbacks). The routing is streamed live in the UI and printed in each report.

## How the claims are kept honest
1. The cited query is re-run on Zetaris, and the result must reproduce.
2. Each cited cell must exist and match the value cited.
3. Every number in the claim text must come from a cited cell, or from a simple delta, ratio or % change of two cited cells.
4. A separate Nemotron verifier lane must not contradict the claim.

Claims that fail any check are struck out and never reach the answer.

## Evaluation
`evals/run_evals.py` runs 5 seeded questions against a synthetic dataset with 3 planted causes and 2 red herrings (`data/GROUND_TRUTH.md`;
the agent never sees the ground truth). Scoring only counts verified claims. Latest results: `evals/results/summary.json`: 5/5 on 24 Oct 2026 (earlier runs 3/5 and 4/5; LLM runs vary).

## Cursor use
<!-- TODO (Nathan): confirm before submitting, and add screenshots to docs/img/. -->
Development was done with AI-assisted coding in the Cursor environment during the hackathon window. Screenshots: _to add_.

## Pre-existing code declaration
- All WhyDrop code (`whydrop/`, `app.py`, `zetaris/`, `evals/`, `scripts/`, the dataset) was written during the hackathon window (from 23 Oct 2026).
  No WhyDrop code existed before the window.
- **Third-party code used, not written by us:**
  - The Meterless agentathon starter and H-MEM reference engine (Apache-2.0, in `meterless/`; `meterless/bridge.ts` is ours).
  - The Zetaris platform (run locally, not included in the repo).
  - Open-source Python and Node libraries listed in `requirements.txt` and `meterless/package.json`.
- The git history was committed in batches, so several early commits share a timestamp (24 Oct 2026, 00:43 UK).

## Future work
Connectors for real Shopify, Gumroad and Stripe data; scheduled "watchdog" runs that alert when a metric drops and attach the explanation;
causal-impact estimates instead of rough impact; and a multi-tenant hosted version.
