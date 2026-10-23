"""zetaris_sql(query): the agent's only data tool. Runs SQL on the local Zetaris Lightning
stack through its REST API (ui:3000 -> api -> driver -> Spark) and returns rows.

Credentials are read from the Zetaris platform .env (ZETARIS_ENV, default
/tmp/zp/zetaris-platform/.env) or ZETARIS_EMAIL / ZETARIS_PASSWORD. Never logged."""
from __future__ import annotations
import hashlib, json, os, re, time, uuid
import requests

BASE = os.environ.get("ZETARIS_URL", "http://localhost:3000")
ENV_FILE = os.environ.get("ZETARIS_ENV", "/tmp/zp/zetaris-platform/.env")
MAX_ROWS = 500

# Catalogue the agent sees. Two federated sources: files (CSV/JSON filestore) + Postgres (JDBC).
SCHEMA = {
    "WHYDROP_FILES.orders": "order_id, date (yyyy-MM-dd), product_id, channel (organic|email|paid_social|...), unit_price_usd, quantity, country  -- one row per order; revenue = unit_price_usd*quantity  [CSV file]",
    "WHYDROP_FILES.products": "product_id, name, base_price  [CSV file]",
    "WHYDROP_FILES.marketing_spend": "date, channel (e.g. meta), campaign, impressions, clicks, spend_usd  -- daily ad spend; meta ads drive orders.channel='paid_social'  [CSV file]",
    "WHYDROP_FILES.web_traffic": "date, source (organic|email|paid_social|...), sessions, product_page_views, landing_404s  -- daily per source  [JSON file]",
    "WHYDROP_FILES.pricing_changes": "date, product_id, old_price_usd, new_price_usd, note  [JSON file]",
    "WHYDROP_FILES.release_log": "date, product_id, version, note  -- product file releases  [JSON file]",
    "WHYDROP_PG.refunds": "refund_id, order_id, date, amount_usd, reason  [Postgres]",
    "WHYDROP_PG.support_tickets": "ticket_id, order_id, date, category, message  [Postgres]",
}

def schema_text() -> str:
    return "\n".join(f"- {t}: {c}" for t, c in SCHEMA.items()) + (
        "\nDialect: Spark SQL. All columns may be stored as strings: CAST numerics (CAST(x AS DOUBLE)) and dates (to_date(date)). "
        "Use date_format(to_date(date),'yyyy-MM') for months. Always qualify tables as shown. Data covers 2026-06-01..2026-09-30.")

class ZetarisError(RuntimeError):
    pass

class ZetarisClient:
    def __init__(self):
        self._token = None; self._org = None; self._t = 0.0

    def _creds(self):
        e, p = os.environ.get("ZETARIS_EMAIL"), os.environ.get("ZETARIS_PASSWORD")
        if not (e and p) and os.path.exists(ENV_FILE):
            kv = dict(l.split("=", 1) for l in open(ENV_FILE).read().splitlines() if "=" in l and not l.startswith("#"))
            e = e or kv.get("ZETARIS_ADMIN_EMAIL", "admin@zetaris.com"); p = p or kv.get("ZETARIS_ADMIN_PASSWORD")
        if not p:
            raise ZetarisError("no Zetaris credentials (set ZETARIS_ENV or ZETARIS_EMAIL/ZETARIS_PASSWORD)")
        return e.strip().strip('"'), p.strip().strip('"')

    def _login(self):
        e, p = self._creds()
        r = requests.post(f"{BASE}/api/auth/login", json={"username": e, "password": p}, timeout=30)
        txt = r.text
        tok = re.search(r"[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}", txt)
        org = re.search(r'"orgId"\s*:\s*(\d+)', txt)
        if not (tok and org):
            raise ZetarisError(f"Zetaris login failed (HTTP {r.status_code})")
        self._token, self._org, self._t = tok.group(0), org.group(1), time.time()

    def query(self, sql: str, page_limit: int = MAX_ROWS) -> dict:
        if not self._token or time.time() - self._t > 600:
            self._login()
        sql = sql.strip().rstrip(";")
        t0 = time.time()
        r = requests.post(f"{BASE}/api/proxy/query/sql/start", timeout=300,
                          headers={"Authorization": f"Bearer {self._token}", "X-Org-ID": self._org, "X-Request-ID": str(uuid.uuid4())},
                          json={"select": sql, "pageLimit": page_limit})
        try:
            j = r.json()
        except ValueError:
            raise ZetarisError(f"HTTP {r.status_code}: {r.text[:300]}")
        if "records" not in j:
            raise ZetarisError(str(j.get("msg") or j)[:600])
        rows = [{k: _num(v) for k, v in rec.items()} for rec in j["records"]]
        return {"rows": rows, "row_count": j.get("totalCount", len(rows)), "truncated": j.get("totalPages", 1) > 1,
                "elapsed_s": round(time.time() - t0, 2), "result_hash": hashlib.sha1(json.dumps(rows, sort_keys=True).encode()).hexdigest()[:12]}

def _num(v):
    if isinstance(v, str):
        if re.fullmatch(r"-?\d+", v):
            return int(v)
        if re.fullmatch(r"-?\d*\.\d+(E-?\d+)?|-?\d+E-?\d+", v):
            return float(v)
    return v

_client = ZetarisClient()

def zetaris_sql(query: str) -> dict:
    """Run a read-only SQL query on Zetaris. Returns {rows, row_count, truncated, elapsed_s, result_hash}."""
    if not re.match(r"^\s*(with|select)\b", query, re.I):
        raise ZetarisError("only SELECT/WITH queries are allowed")
    return _client.query(query)

if __name__ == "__main__":
    import sys
    print(json.dumps(zetaris_sql(sys.argv[1] if len(sys.argv) > 1 else "select count(*) n from WHYDROP_FILES.orders"), indent=1))
