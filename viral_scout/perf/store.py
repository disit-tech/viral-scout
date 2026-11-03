"""SQLite for own performance, in the profile's data/<profile>.sqlite but in its own tables:

  perf_records    latest normalized record per key (API pulls and CSV imports)
  perf_snapshots  (key, ts) → a few KPIs and counts per run, for trends and creative fatigue
"""
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
create table if not exists perf_records (key text primary key, source text, kind text, updated text, record text);
create table if not exists perf_snapshots (key text, ts text, kind text, data text, primary key (key, ts));
"""
SNAP_KPIS = ["hook_rate", "avg_pct_viewed", "completion_rate", "engagement_rate", "share_rate", "ctr", "link_ctr",
             "cpm", "cpc", "cvr", "cpa", "roas", "frequency"]
SNAP_COUNTS = ["impressions", "reach", "views", "spend", "clicks", "link_clicks", "conversions"]


class PerfStore:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        self.now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def replace_source(self, source, records):
        """A successful API pull replaces that source's records (ads that stopped running drop out)."""
        self.db.execute("delete from perf_records where source=?", (source,))
        self.upsert(records)

    def upsert(self, records):
        for r in records:
            self.db.execute("insert or replace into perf_records values (?,?,?,?,?)",
                            (r["key"], r["source"], r["kind"], self.now, json.dumps(r, ensure_ascii=False, default=str)))
        self.db.commit()

    def records(self):
        return [json.loads(row[0]) for row in self.db.execute("select record from perf_records order by key")]

    def sources(self):
        return {s: (n, u) for s, n, u in self.db.execute(
            "select source, count(*), max(updated) from perf_records group by source")}

    def snapshot(self, rows):
        for row in rows:
            data = {k: row["kpis"][k]["value"] for k in SNAP_KPIS if k in row["kpis"]}
            data.update({k: row.get(k) for k in SNAP_COUNTS if row.get(k) is not None})
            last = self.db.execute("select data from perf_snapshots where key=? order by ts desc limit 1",
                                   (row["key"],)).fetchone()
            if last and json.loads(last[0]) == json.loads(json.dumps(data)):
                continue                       # unchanged (e.g. a rebuild without new data): no duplicate point
            self.db.execute("insert or replace into perf_snapshots values (?,?,?,?)",
                            (row["key"], self.now, row["kind"], json.dumps(data)))
        self.db.commit()

    def close(self):
        self.db.close()

    def history(self, key, limit=60):
        rows = self.db.execute("select ts, data from perf_snapshots where key=? order by ts desc limit ?", (key, limit))
        return [(ts, json.loads(d)) for ts, d in reversed(rows.fetchall())]
