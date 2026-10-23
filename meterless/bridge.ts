// WhyDrop <-> Meterless H-MEM bridge. Reads a JSON array of ops on stdin, writes JSON results.
// ops: {op:"add", content, type?, source?} | {op:"query", text, threshold?} | {op:"history", id}
// State persists in $WHYDROP_HMEM_DIR (default .whydrop-hmem/), so findings survive across sessions.
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadHMEM } from "./src/engine.ts";
const here = path.dirname(fileURLToPath(import.meta.url));
const chunks: Buffer[] = [];
for await (const c of process.stdin) chunks.push(c as Buffer);
const ops = JSON.parse(Buffer.concat(chunks).toString() || "[]");
const { HMEM, source } = await loadHMEM();
const hmem = new HMEM({ persistDir: process.env.WHYDROP_HMEM_DIR || path.join(here, ".whydrop-hmem") });
const out: any[] = [];
for (const o of ops) {
  if (o.op === "add") {
    const r = hmem.add({ content: o.content, type: o.type || "general", source: o.source || "whydrop" });
    out.push({ id: r.id, layer: r.layer });
  } else if (o.op === "query") {
    const r = hmem.query(o.text, { threshold: o.threshold ?? 0.1 });
    out.push({ strategy: r.trace?.strategy, memories: r.memories.map((m: any) => ({ id: m.memory.id, relevance: m.relevance, content: m.memory.content, source: m.memory.source })) });
  } else if (o.op === "history") {
    out.push(hmem.ledger.history(o.id).map((e: any) => ({ action: e.action, actor: e.actor, ts: e.timestamp })));
  } else out.push({ error: `unknown op ${o.op}` });
}
process.stdout.write(JSON.stringify({ engine: source, results: out }));
