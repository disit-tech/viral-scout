"""Live activity: what is running right now, line by line, and what Apify is doing (and costing).

Every `run`, `ads` and `perf` command is wrapped in track(): it writes data/activity/<id>.log (everything the
command prints, plus progress lines that --quiet hides from the terminal) and data/activity/<id>.json
(profile, kind, pid, started, status). It doesn't matter who started it: CLI, scheduled task, MCP or dashboard.

  python -m viral_scout activity              # JSON for the dashboard's Activity page (jobs + Apify)
  python -m viral_scout activity --jobs-only  # local jobs only, no Apify calls (the nav's "running" dot)
  python -m viral_scout activity register <profile> <kind> <log> <pid>   # show a run started some other way

Apify reads here are free (run list, actor lookup, usage limits) and cached for a few seconds.
"""
import json
import os
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import config

LIVE = config.ROOT / "data" / "activity"
_CURRENT = {"log": None}


def _now():
    return datetime.now(timezone.utc)


def _write_json(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


class _Tee:
    """Writes to the terminal and to the live log, flushing each line so the dashboard sees it at once."""

    def __init__(self, stream, fh):
        self.stream, self.fh = stream, fh

    def write(self, s):
        try:
            self.stream.write(s)
        except (ValueError, OSError):
            pass
        try:
            self.fh.write(s)
            self.fh.flush()
        except (ValueError, OSError):
            pass
        return len(s)

    def flush(self):
        for f in (self.stream, self.fh):
            try:
                f.flush()
            except (ValueError, OSError):
                pass

    def __getattr__(self, name):
        return getattr(self.stream, name)


def note(msg):
    """A progress line for the live log only (what --quiet keeps off the terminal)."""
    fh = _CURRENT["log"]
    if fh:
        try:
            fh.write(f"{msg}\n")
            fh.flush()
        except (ValueError, OSError):
            pass


@contextmanager
def track(profile, kind, argv=None):
    LIVE.mkdir(parents=True, exist_ok=True)
    started = _now()
    jid = f"{started.strftime('%Y%m%d-%H%M%S')}-{profile}-{kind}"
    log_path, st_path = LIVE / f"{jid}.log", LIVE / f"{jid}.json"
    st = {"id": jid, "profile": profile, "kind": kind, "pid": os.getpid(), "started": started.isoformat(),
          "status": "running", "log": str(log_path), "cmd": "python -m viral_scout " + " ".join(argv or [])}
    _write_json(st_path, st)
    fh = open(log_path, "a", encoding="utf-8", buffering=1)
    fh.write(f"[{started.astimezone().strftime('%H:%M:%S')}] start: {st['cmd']}\n")
    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = _Tee(old_out, fh), _Tee(old_err, fh)
    _CURRENT["log"] = fh
    status, error = "done", None
    try:
        yield st
    except SystemExit as e:
        status = "done" if e.code in (0, None) else "failed"
        raise
    except BaseException as e:  # noqa: BLE001 (record it, then re-raise)
        status, error = "failed", f"{type(e).__name__}: {e}"[:500]
        raise
    finally:
        sys.stdout, sys.stderr = old_out, old_err
        _CURRENT["log"] = None
        end = _now()
        fh.write(f"[{end.astimezone().strftime('%H:%M:%S')}] {status}"
                 f"{': ' + error if error else ''} after {int((end - started).total_seconds())} s\n")
        fh.close()
        st.update(status=status, finished=end.isoformat(), error=error)
        _write_json(st_path, st)


def register(profile, kind, log, pid, started=None):
    """Status file for a run started without track() (e.g. an older process), so the page shows it too."""
    LIVE.mkdir(parents=True, exist_ok=True)
    started = started or _now().isoformat()
    jid = f"{started[:19].replace('-', '').replace(':', '').replace('T', '-')}-{profile}-{kind}"
    st = {"id": jid, "profile": profile, "kind": kind, "pid": int(pid), "started": started, "status": "running",
          "log": str(log), "cmd": "(started before live logging)"}
    _write_json(LIVE / f"{jid}.json", st)
    return st


def _alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        # os.kill(pid, 0) would *terminate* the process on Windows, so ask the kernel instead.
        import ctypes
        k = ctypes.windll.kernel32
        h = k.OpenProcess(0x1000, False, int(pid))          # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return False
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259                # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except OSError:
        return False


def _tail(path, n=200):
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - 256_000))
            lines = f.read().decode("utf-8", "replace").splitlines()
        return lines[-n:], size
    except OSError:
        return [], 0


_STEP = re.compile(r"^(ads|discover|watch|own|re-check|enrich|perf|demand)[: ]", re.I)
_COUNT = re.compile(r":\s*(\d+)\s+(ads|posts|items|videos)\b")


def _progress(lines):
    """A short summary from the log: current step, sources done, ads/posts so far."""
    step, sources, found, done_queries, errors = None, [], 0, 0, 0
    for line in lines:
        s = line.strip()
        if re.match(r"^ads: [a-z_]+$", s):
            sources.append(s[5:])
            step = f"ads source {s[5:]}"
        elif _STEP.match(s):
            step = s[:120]
        m = _COUNT.search(s)
        if m:
            done_queries += 1
            found += int(m.group(1))
            step = s[:120]
        if s.lower().startswith("error") or " error" in s.lower()[:40]:
            errors += 1
    return {"step": step, "sources": sources, "queries_done": done_queries, "found": found, "errors": errors}


def plan_for(profile, kind):
    """What an ads run will do, per source (from the profile and the keys that are set): the progress bar's total.
    Meta logs one line per advertiser/keyword search; Google and TikTok log one line when they finish."""
    if kind != "ads":
        return None
    try:
        from .ads import sources
        a = config.load(profile).get("ads") or {}
        plan = []
        for s in a.get("sources") or sources.SOURCES:
            if not sources.available(s):
                continue
            if s == "apify_meta":
                n = len(sources._advertiser_entries(a)) + len(a.get("keywords") or [])
                plan.append({"source": s, "steps": n, "what": f"{n} Facebook/Instagram searches (one Apify run each)"})
            elif s == "apify_google":
                p = sources.google_payload(a)
                b = len(list(sources.google_batches(p))) if p else 0
                plan.append({"source": s, "steps": 1 if b else 0,
                             "what": f"Google Transparency: {b} Apify runs of up to {sources.GOOGLE_BATCH} competitors"})
            elif s == "apify_tiktok_top":
                plan.append({"source": s, "steps": 1, "what": "TikTok Top Ads: 1 Apify run"})
            else:
                plan.append({"source": s, "steps": 1, "what": s})
        return plan
    except Exception:  # noqa: BLE001 (a plan is a nicety; never break the page)
        return None


def jobs(limit=12, tail=200):
    out = []
    if not LIVE.exists():
        return out
    for p in sorted(LIVE.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        if p.name.startswith("_"):
            continue
        try:
            st = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if st.get("status") == "running" and not _alive(st.get("pid")):
            st["status"] = "stopped"          # the process is gone without writing done/failed
        lines, size = _tail(st.get("log", ""), tail)
        started = datetime.fromisoformat(st["started"])
        end = datetime.fromisoformat(st["finished"]) if st.get("finished") else _now()
        try:
            last_write = datetime.fromtimestamp(Path(st.get("log", "")).stat().st_mtime, timezone.utc)
        except OSError:
            last_write = None
        prog = _progress(lines if size <= 256_000 else _tail(st.get("log", ""), 5000)[0])
        plan = plan_for(st["profile"], st["kind"]) if st["status"] == "running" else None
        if plan:
            prog["total_steps"] = sum(p["steps"] for p in plan)
            prog["plan"] = plan
        st.update(elapsed_s=int((end - started).total_seconds()), log_lines=lines, log_bytes=size,
                  quiet_s=int((_now() - last_write).total_seconds()) if last_write else None,
                  progress=prog)
        out.append(st)
        if len(out) >= limit:
            break
    out.sort(key=lambda j: (j["status"] != "running", j["started"]), reverse=False)
    running = [j for j in out if j["status"] == "running"]
    rest = sorted([j for j in out if j["status"] != "running"], key=lambda j: j["started"], reverse=True)
    return running + rest


def _apify_get(path, token, **params):
    import requests
    r = requests.get(f"https://api.apify.com/v2/{path}", params={"token": token, **params}, timeout=15)
    r.raise_for_status()
    return r.json()["data"]


def apify(hours=6):
    token = os.environ.get("APIFY_TOKEN")
    if not token:
        return {"configured": False}
    cache = LIVE / "_apify-cache.json"
    try:
        c = json.loads(cache.read_text(encoding="utf-8"))
        if time.time() - c.get("at", 0) < 8:
            return c["data"]
    except (OSError, ValueError):
        c = {}
    names = c.get("names", {})
    try:
        lim = _apify_get("users/me/limits", token)
        runs = _apify_get("actor-runs", token, desc=1, limit=40)["items"]
    except Exception as err:  # noqa: BLE001
        return {"configured": True, "error": str(err)[:200]}
    since = _now() - timedelta(hours=hours)
    rows = []
    for r in runs:
        started = datetime.fromisoformat(r["startedAt"].replace("Z", "+00:00"))
        if started < since and r["status"] not in ("RUNNING", "READY"):
            continue
        aid = r["actId"]
        if aid not in names:
            try:
                a = _apify_get(f"acts/{aid}", token)
                names[aid] = f"{a['username']}~{a['name']}"
            except Exception:  # noqa: BLE001
                names[aid] = aid
        fin = r.get("finishedAt")
        secs = ((datetime.fromisoformat(fin.replace("Z", "+00:00")) if fin else _now()) - started).total_seconds()
        rows.append({"actor": names[aid], "status": r["status"], "started": started.isoformat(),
                     "seconds": int(secs), "usd": round(r.get("usageTotalUsd") or 0, 4), "id": r["id"]})
    used = (lim.get("current") or {}).get("monthlyUsageUsd") or 0
    cap = (lim.get("limits") or {}).get("maxMonthlyUsageUsd") or 0
    data = {"configured": True, "used_usd": round(used, 2), "limit_usd": cap,
            "cycle_end": ((lim.get("monthlyUsageCycle") or {}).get("endAt") or "")[:10],
            "running": sum(1 for r in rows if r["status"] in ("RUNNING", "READY")),
            "window_usd": round(sum(r["usd"] for r in rows), 2), "window_hours": hours, "runs": rows,
            "cap_per_run": os.environ.get("APIFY_MAX_USD_PER_RUN", "0.5")}
    try:
        LIVE.mkdir(parents=True, exist_ok=True)
        _write_json(cache, {"at": time.time(), "data": data, "names": names})
    except OSError:
        pass
    return data


def status(jobs_only=False):
    out = {"now": _now().isoformat(), "jobs": jobs(tail=40 if jobs_only else 200)}
    if jobs_only:
        out["jobs"] = [{k: j[k] for k in ("id", "profile", "kind", "status", "elapsed_s")} for j in out["jobs"]]
    else:
        out["apify"] = apify()
    return out


def cli(args):
    if args and args[0] == "register":
        if len(args) < 5:
            print("usage: activity register <profile> <kind> <log> <pid> [started-iso]")
            return 2
        print(json.dumps(register(*args[1:6]), indent=1))
        return 0
    print(json.dumps(status(jobs_only="--jobs-only" in args), ensure_ascii=False))
    return 0
