SEG = [
 ("title", "When revenue drops, a small online seller gets a chart, not an answer. WhyDrop is an agent that explains why, and proves every claim it makes."),
 ("problem", "The clues are scattered across order exports, ad spend, web traffic, and a refunds database. Most sellers have no analyst to join them up, and a chatbot that guesses can send them after the wrong fix."),
 ("zetaris", "Zetaris federates all of it into one SQL layer. Here are the registered sources: four file sources, and a Postgres database holding refunds and support tickets. The agent has exactly one tool: run SQL on Zetaris."),
 ("ask", "In the WhyDrop app, I ask in plain English: why did revenue drop in September?"),
 ("run", "This is a real run, sped up. First, a fixed signal scan runs on Zetaris. Then the Nemotron planner proposes competing hypotheses, using memories of past investigations from Meterless. Each hypothesis is tested with real SQL, including joins between the Postgres refunds and the order files. The routing panel shows which Nemotron model served each step: Super plans and analyses, Nano writes SQL, and Lightning verifies."),
 ("report", "The answer is ranked by impact. Every claim cites the exact query, row and column behind it. Claims that fail verification are struck out, and hypotheses the data contradicts are listed as rejected, with their evidence."),
 ("trust", "Before any claim is shown, its query is re-run on Zetaris and must reproduce. Each cited cell must match, every number must be grounded in the data, and an independent Nemotron verifier must agree."),
 ("results", "We tested it on five questions over a seeded dataset with three planted causes: a broken Meta campaign sending clicks to 404 pages, a price rise, and a corrupted product release. On the latest run it found all three, and passed five out of five. Results vary between runs, and every run is logged in the repo."),
 ("arch", "Zetaris for federated data, Meterless for long-term memory, and NVIDIA Nemotron for reasoning, with the routing visible throughout. Built in Cursor."),
 ("end", "WhyDrop. The code is on GitHub at jamesbrowndevs slash whydrop."),
]
