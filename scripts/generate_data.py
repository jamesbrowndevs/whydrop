"""Generate WhyDrop's synthetic seller dataset (Jun-Sep 2026) with planted causes.

Planted causes of the September revenue drop (see data/GROUND_TRUTH.md):
  1. Price rise: "Notion Freelance OS" (P001) goes from $19 to $29 on 2026-09-01; its conversion falls sharply.
  2. Broken ad campaign: Meta campaign "fall_launch" keeps spending from 2026-09-08, but its landing URL
     404s, so paid-social sessions stop turning into orders (clicks stay up, sessions/landings collapse).
  3. Refund spike: "Python Scraper Pack" (P003) ships v2 on 2026-09-15 with a broken zip; refunds and
     support tickets with reason "file corrupted" spike.
Red herrings: email and organic traffic stay flat; a small seasonal dip of about 3% applies to everything.
"""
import json, sqlite3, random
from datetime import date, timedelta
from pathlib import Path
import numpy as np, pandas as pd

rng = np.random.default_rng(42); random.seed(42)
OUT = Path(__file__).resolve().parent.parent / "data"; OUT.mkdir(exist_ok=True)
START, END = date(2026, 6, 1), date(2026, 9, 30)
days = [START + timedelta(d) for d in range((END - START).days + 1)]

products = pd.DataFrame([
    ("P001", "Notion Freelance OS", 19.0), ("P002", "Telegram Alert Bot Template", 12.0),
    ("P003", "Python Scraper Pack", 15.0), ("P004", "Solana Token Scanner", 15.0),
    ("P005", "Prompt Library for Sellers", 7.0)], columns=["product_id", "name", "base_price"])
mix = {"P001": .34, "P002": .18, "P003": .22, "P004": .16, "P005": .10}
sources = {"organic": 520, "email": 180, "paid_social": 360, "referral": 140}
conv = {"organic": .022, "email": .045, "paid_social": .018, "referral": .03}

PRICE_DAY, ADS_BROKEN, BAD_ZIP = date(2026, 9, 1), date(2026, 9, 8), date(2026, 9, 15)
def price(pid, d):
    base = float(products.set_index("product_id").loc[pid, "base_price"])
    return 29.0 if pid == "P001" and d >= PRICE_DAY else base

traffic, orders, spend, refunds, tickets = [], [], [], [], []
oid = rid = tid = 0
for d in days:
    season = 0.97 if d.month == 9 else 1.0
    weekday = 1.08 if d.weekday() < 5 else 0.88
    for src, base in sources.items():
        sess = int(rng.poisson(base * season * weekday))
        clicks = None
        if src == "paid_social":
            clicks = sess + int(rng.poisson(15))
            if d >= ADS_BROKEN:   # clicks keep coming (and costing) but landing 404s
                sess = int(rng.poisson(8))
        traffic.append({"date": d.isoformat(), "source": src, "sessions": sess,
                        "product_page_views": int(sess * rng.uniform(1.6, 2.1)),
                        "landing_404s": int(clicks - sess) if (src == "paid_social" and d >= ADS_BROKEN) else int(rng.poisson(1))})
        if src == "paid_social":
            spend.append({"date": d.isoformat(), "channel": "meta", "campaign": "summer_evergreen" if d.month < 9 else "fall_launch",
                          "impressions": clicks * int(rng.integers(55, 70)), "clicks": clicks,
                          "spend_usd": round(clicks * rng.uniform(0.38, 0.46), 2)})
        n = rng.binomial(sess, conv[src])
        for _ in range(n):
            pid = rng.choice(list(mix), p=list(mix.values()))
            if pid == "P001" and d >= PRICE_DAY and rng.random() < 0.55:
                continue  # price-sensitive buyers walk away
            oid += 1
            o = {"order_id": f"O{oid:05d}", "date": d.isoformat(), "product_id": pid, "channel": src,
                 "unit_price_usd": price(pid, d), "quantity": 1,
                 "country": rng.choice(["GB", "US", "DE", "IN", "CA", "AU"], p=[.25, .35, .1, .12, .1, .08])}
            orders.append(o)
            p_ref = 0.40 if (pid == "P003" and d >= BAD_ZIP) else 0.03
            if rng.random() < p_ref:
                rid += 1; rd = d + timedelta(int(rng.integers(0, 4)))
                reason = "file corrupted" if (pid == "P003" and d >= BAD_ZIP and rng.random() < .85) else \
                    random.choice(["not as described", "bought by mistake", "duplicate purchase", "changed mind"])
                refunds.append((f"R{rid:05d}", o["order_id"], min(rd, END).isoformat(), o["unit_price_usd"], reason))
                if reason == "file corrupted" or rng.random() < .3:
                    tid += 1
                    tickets.append((f"T{tid:05d}", o["order_id"], min(rd, END).isoformat(), "refund" if reason != "file corrupted" else "download",
                                    "Zip won't open, says archive is damaged" if reason == "file corrupted" else f"Requesting refund: {reason}"))

pd.DataFrame(orders).to_csv(OUT / "orders.csv", index=False)
pd.DataFrame(spend).to_csv(OUT / "marketing_spend.csv", index=False)
products.to_csv(OUT / "products.csv", index=False)
(OUT / "web_traffic.json").write_text(json.dumps(traffic, indent=1))
(OUT / "pricing_changes.json").write_text(json.dumps([
    {"date": "2026-09-01", "product_id": "P001", "old_price_usd": 19.0, "new_price_usd": 29.0, "note": "repositioned as premium"}], indent=1))
(OUT / "release_log.json").write_text(json.dumps([
    {"date": "2026-08-03", "product_id": "P004", "version": "1.1", "note": "added Raydium filter"},
    {"date": "2026-09-15", "product_id": "P003", "version": "2.0", "note": "new scrapers bundled; zip rebuilt with new packer"}], indent=1))
db = OUT / "support.db"; db.unlink(missing_ok=True)
con = sqlite3.connect(db)
con.execute("CREATE TABLE refunds (refund_id TEXT PRIMARY KEY, order_id TEXT, date TEXT, amount_usd REAL, reason TEXT)")
con.execute("CREATE TABLE support_tickets (ticket_id TEXT PRIMARY KEY, order_id TEXT, date TEXT, category TEXT, message TEXT)")
con.executemany("INSERT INTO refunds VALUES (?,?,?,?,?)", refunds)
con.executemany("INSERT INTO support_tickets VALUES (?,?,?,?,?)", tickets)
con.commit(); con.close()
print(f"orders={len(orders)} refunds={len(refunds)} tickets={len(tickets)} traffic_rows={len(traffic)}")
