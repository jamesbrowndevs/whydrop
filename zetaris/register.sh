#!/usr/bin/env bash
# Federate the WhyDrop sources into the local Zetaris Lightning stack.
#  - CSV/JSON files  -> WHYDROP_FILES (Lightning FILESTORE tables over the customer-data volume)
#  - SQLite support.db -> Postgres DB whydrop_ops -> WHYDROP_OPS (Lightning JDBC datasource)
# Usage: ZP=/tmp/zp/zetaris-platform ./register.sh   (reads creds from $ZP/.env; prints none)
set -euo pipefail
ZP="${ZP:-/tmp/zp/zetaris-platform}"; HERE="$(cd "$(dirname "$0")" && pwd)"; DATA="$HERE/../data"
set -a; . "$ZP/.env"; set +a
D=$(docker ps -qf name=zetaris-driver-1); P=$(docker ps -qf name=zetaris-postgres-1)
ROOT=/home/zetaris/customer-data/shared/whydrop
for f in orders products marketing_spend; do docker exec $D mkdir -p $ROOT/$f; docker cp "$DATA/$f.csv" $D:$ROOT/$f/; done
for f in pricing_changes release_log web_traffic; do docker exec $D mkdir -p $ROOT/$f; docker cp "$DATA/$f.json" $D:$ROOT/$f/; done
docker exec -u 0 $D chmod -R a+rX $ROOT
if [ "${SKIP_PG:-0}" != 1 ]; then
  docker exec $P psql -q -U "${POSTGRES_USER:-zetaris}" -d metastore -c "DROP DATABASE IF EXISTS whydrop_ops" -c "CREATE DATABASE whydrop_ops"
  python3 "$HERE/sqlite_to_pg.py" "$DATA/support.db" | docker exec -i $P psql -q -U "${POSTGRES_USER:-zetaris}" -d whydrop_ops
fi
TMP=$(mktemp); chmod 600 "$TMP"; trap 'rm -f "$TMP"; docker exec -u 0 $D rm -f /tmp/whydrop_r.sql' EXIT
sed -e "s|@PGUSER@|${POSTGRES_USER:-zetaris}|" -e "s|@PGPASS@|${POSTGRES_PASSWORD}|" "$HERE/register.sql" > "$TMP"
docker cp "$TMP" $D:/tmp/whydrop_r.sql; docker exec -u 0 $D chown zetaris /tmp/whydrop_r.sql
docker exec $D bash -c 'cd ~/zetaris-ndp-driver && bash bin/lightning-sql.sh --email "$ZETARIS_ADMIN_EMAIL" --password "$ZETARIS_ADMIN_PASSWORD" -f /tmp/whydrop_r.sql' > /tmp/whydrop_register.log 2>&1 \
  && echo "registered" || { grep -aE 'ERROR|LightningException' /tmp/whydrop_register.log | sed 's/password "[^"]*"/password "***"/g' | head -5; exit 1; }
