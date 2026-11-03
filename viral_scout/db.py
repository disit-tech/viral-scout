"""SQLite history: every run stores a snapshot of each post's numbers, so later runs can measure growth."""
import json
import sqlite3
from datetime import datetime, timezone

from .models import Item, parse_date

SCHEMA = """
create table if not exists items (
  key text primary key, platform text, id text, url text, title text, channel text, channel_url text,
  followers integer, published text, found_by text, first_seen text, last_seen text, tracked integer default 0
);
create table if not exists snapshots (
  key text, ts text, views integer, likes integer, comments integer,
  primary key (key, ts)
);
create table if not exists runs (ts text primary key, profile text, summary text);
"""


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.executescript(SCHEMA)
        cols = {r[1] for r in self.db.execute("pragma table_info(items)")}
        for col in ("hook", "transcript", "description"):
            if col not in cols:
                self.db.execute(f"alter table items add column {col} text")
        for col in ("dismissed", "saved", "alerted"):
            if col not in cols:
                self.db.execute(f"alter table items add column {col} integer default 0")
        self.now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    def previous(self, key):
        """Latest snapshot from an earlier run: (ts, views, likes)."""
        return self.db.execute(
            "select ts, views, likes from snapshots where key=? and ts<? order by ts desc limit 1",
            (key, self.now)).fetchone()

    def seen_before(self, key):
        return self.db.execute("select 1 from items where key=? and first_seen<?", (key, self.now)).fetchone() is not None

    def save(self, item: Item, tracked=False):
        self.db.execute(
            """insert into items (key, platform, id, url, title, channel, channel_url, followers, published,
                                  found_by, first_seen, last_seen, tracked)
               values (?,?,?,?,?,?,?,?,?,?,?,?,?)
               on conflict(key) do update set url=excluded.url, title=excluded.title, channel=excluded.channel,
                 channel_url=excluded.channel_url, followers=coalesce(excluded.followers, followers),
                 published=coalesce(excluded.published, published), found_by=excluded.found_by,
                 last_seen=excluded.last_seen, tracked=max(tracked, excluded.tracked)""",
            (item.key, item.platform, item.id, item.url, item.title, item.channel, item.channel_url, item.followers,
             item.published.isoformat() if item.published else None, json.dumps(item.found_by),
             self.now, self.now, int(tracked)))
        if item.views is not None or item.likes is not None:
            self.db.execute("insert or replace into snapshots values (?,?,?,?,?)",
                            (item.key, self.now, item.views, item.likes, item.comments))

    def add_rise(self, item: Item):
        prev = self.previous(item.key)
        if not prev:
            return
        ts, views, likes = prev
        days = (datetime.fromisoformat(self.now) - datetime.fromisoformat(ts)).total_seconds() / 86400
        if days < 0.04:          # under an hour apart: too noisy
            return
        old, new = (views, item.views) if item.views is not None and views is not None else (likes, item.likes)
        if old is not None and new is not None:
            item.rise_per_day = max(new - old, 0) / days

    def to_recheck(self, max_age_days, limit):
        """Posts worth re-measuring: tracked seeds plus recent posts we've seen, best first."""
        rows = self.db.execute(
            """select i.key, i.platform, i.id, i.url, i.title, i.channel, i.channel_url, i.followers, i.published,
                      i.found_by, i.tracked, max(s.views), max(s.likes)
               from items i left join snapshots s on s.key = i.key
               where i.tracked = 1 or i.published >= datetime('now', ?)
               group by i.key order by i.tracked desc, coalesce(max(s.views), max(s.likes), 0) desc limit ?""",
            (f"-{max_age_days} days", limit)).fetchall()
        out = []
        for r in rows:
            it = Item(platform=r[1], id=r[2], url=r[3], title=r[4], channel=r[5], channel_url=r[6], followers=r[7],
                      published=parse_date(int(datetime.fromisoformat(r[8]).timestamp())) if r[8] else None,
                      found_by=json.loads(r[9] or "[]"))
            out.append((it, bool(r[10])))
        return out

    def text(self, key):
        """Cached (hook, transcript, description) for a post."""
        return self.db.execute("select hook, transcript, description from items where key=?", (key,)).fetchone()

    def save_text(self, item: Item):
        self.db.execute("update items set hook=?, transcript=?, description=? where key=?",
                        (item.hook, item.transcript, item.description, item.key))

    def find(self, ref):
        """A post by id, key or URL → (key, url) or None."""
        return self.db.execute("select key, url from items where id=? or key=? or url=? limit 1",
                               (ref, ref, ref)).fetchone()

    def flag(self, key, col, value=1):
        assert col in ("dismissed", "saved", "alerted", "tracked")
        self.db.execute(f"update items set {col}=? where key=?", (value, key))

    def dismissed(self):
        return {r[0] for r in self.db.execute("select key from items where dismissed=1")}

    def was_alerted(self, key):
        r = self.db.execute("select alerted from items where key=?", (key,)).fetchone()
        return bool(r and r[0])

    def log_run(self, profile, summary):
        self.db.execute("insert or replace into runs values (?,?,?)", (self.now, profile, json.dumps(summary)))
        self.db.commit()

    def commit(self):
        self.db.commit()
