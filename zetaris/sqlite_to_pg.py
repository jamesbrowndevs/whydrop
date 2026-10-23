"""Dump support.db (SQLite) as Postgres DDL+INSERTs on stdout."""
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
print("CREATE TABLE refunds (refund_id TEXT PRIMARY KEY, order_id TEXT, date DATE, amount_usd DOUBLE PRECISION, reason TEXT);")
print("CREATE TABLE support_tickets (ticket_id TEXT PRIMARY KEY, order_id TEXT, date DATE, category TEXT, message TEXT);")
q = lambda v: "NULL" if v is None else (repr(v) if isinstance(v, (int, float)) else "'" + str(v).replace("'", "''") + "'")
for t in ["refunds", "support_tickets"]:
    for r in c.execute(f"select * from {t}"):
        print(f"INSERT INTO {t} VALUES ({','.join(map(q, r))});")
