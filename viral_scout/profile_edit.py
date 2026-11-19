"""Edit a business profile from the dashboard without losing its comments.

  python -m viral_scout profile <name> get            # editable fields as JSON (raw, ${ENV} not expanded)
  python -m viral_scout profile <name> set            # JSON on stdin: {"base": <hash from get>, "set": {path: value}}

Profiles are hand-written YAML full of dated decision comments, and they're git-ignored, so a plain
yaml.dump (which drops every comment) is not an option. Instead each changed field's value is replaced in place
in the text: the key line and every comment outside that value stay as they are. Before writing, the new
text is parsed again and must equal the old profile with exactly the requested changes; otherwise nothing is
written. The previous file is copied to data/profile-backups/ first. Only whitelisted fields can be set.
"""
import copy
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

import yaml

from . import config

# path → kind. list = list of strings; regex / regex_list are compiled to check them; adv = ads.advertisers items.
FIELDS = {
    "display_name": "str", "business": "text",
    "output_dir": "str", "swipe_dir": "str", "taste_note": "str",
    "discover.youtube.keywords": "list", "discover.youtube.hashtags": "list",
    "discover.youtube.window": "window", "discover.youtube.shorts": "bool", "discover.youtube.per_query": "int",
    "discover.tiktok.keywords": "list", "discover.tiktok.hashtags": "list",
    "watch.youtube": "list", "watch.instagram": "list", "watch.tiktok": "list",
    "seeds": "list", "own.youtube": "list", "own.urls": "list",
    "filters.min_views": "int", "filters.max_age_days": "int", "filters.must_match": "regex",
    "filters.exclude": "regex_list", "filters.languages": "langs", "discover.youtube.region": "region",
    "ads.advertisers": "adv", "ads.keywords": "list", "ads.domains": "list", "ads.countries": "list",
    "ads.topic": "list", "ads.exclude_advertisers": "regex_list", "ads.days": "int", "ads.per_query": "int",
    "ads.top": "int",
    "demand.terms": "list", "demand.compare": "list", "demand.geo": "geo", "demand.time": "str",
    "demand.every_days": "int", "demand.lead_weeks": "int",
    "local.query": "str", "local.near": "str", "local.limit": "int",
    "perf.meta_ad_account_id": "str",
    # Paid ads (docs/paid-ads.md): the cap, the accounts and the default brief Claude starts from
    "paid.monthly_cap_usd": "money", "paid.platforms": "paid_platforms",
    "paid.accounts.meta": "str", "paid.accounts.google": "str", "paid.accounts.tiktok": "str",
    "paid.brief.goal": "paid_goal", "paid.brief.daily_budget_usd": "money", "paid.brief.geo": "str",
    "paid.brief.audience": "text", "paid.brief.offer": "str", "paid.brief.landing": "str", "paid.brief.notes": "text",
    # Idea generator schedule (dashboard Schedule page → the studio ideas job, docs/publish-and-jobs.md)
    "jobs.ideas.enabled": "bool", "jobs.ideas.at": "hhmm", "jobs.ideas.days": "jobdays", "jobs.ideas.count": "int",
    # Posting / auto mode (business → Posting page, docs/publish-and-jobs.md#auto-mode)
    "publish.approval": "approval", "publish.per_day": "per_day", "publish.times": "hhmm_list",
    "publish.auto_post.instagram": "bool", "publish.auto_post.facebook": "bool", "publish.auto_post.youtube": "bool",
    "publish.auto_post.linkedin": "bool", "publish.auto_post.tiktok": "bool",
    "publish.posts.enabled": "bool", "publish.posts.per_day": "per_day", "publish.posts.times": "hhmm_list",
    "publish.posts.platforms": "post_platforms",
    "publish.challenges.enabled": "bool", "publish.challenges.dm": "bool", "publish.challenges.reply_text": "str",
    "publish.challenges.reply_text_instagram": "str",
    "jobs.film.enabled": "bool", "jobs.posts.enabled": "bool",
}
MISSING = object()


def _path(name):
    if not re.fullmatch(r"[\w.-]+", name or "") or name.startswith("_"):
        raise ValueError("bad profile name")
    p = config.PROFILES / f"{name}.yaml"
    if not p.exists():
        raise ValueError(f"no profile {name}")
    return p


def _hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _get(d, path):
    for k in path.split("."):
        if not isinstance(d, dict) or k not in d:
            return MISSING
        d = d[k]
    return d


def _put(d, path, v):
    keys = path.split(".")
    for k in keys[:-1]:
        if not isinstance(d.get(k), dict):
            d[k] = {}
        d = d[k]
    d[keys[-1]] = v


def get(name):
    p = _path(name)
    text = p.read_bytes().decode("utf-8")
    raw = yaml.safe_load(text) or {}
    fields = {}
    for path in FIELDS:
        v = _get(raw, path)
        if v is not MISSING:
            fields[path] = v.strip() if isinstance(v, str) and FIELDS[path] == "text" else v
    return {"name": p.stem, "base": _hash(text), "fields": fields, "kinds": FIELDS}


# ---------- validation ----------

def _clean(path, kind, v):
    def s(x, n=300):
        if not isinstance(x, (str, int, float)) or isinstance(x, bool):
            raise ValueError(f"{path}: expected text")
        x = str(x).strip()
        if len(x) > n:
            raise ValueError(f"{path}: longer than {n} characters")
        return x

    def lst(x, item=s, n=200):
        if not isinstance(x, list):
            raise ValueError(f"{path}: expected a list")
        out = [item(i) for i in x]
        out = [i for i in out if i not in ("", None, {})]
        if len(out) > n:
            raise ValueError(f"{path}: more than {n} entries")
        return out

    def rx(x):
        x = s(x, 2000)
        try:
            re.compile(x)
        except re.error as e:
            raise ValueError(f"{path}: not a valid pattern ({e}): {x}")
        return x

    if kind == "text":
        return s(v, 4000)
    if kind == "str":
        return s(v, 500)
    if kind == "int":
        if isinstance(v, bool) or not re.fullmatch(r"\d{1,9}", str(v).strip()):
            raise ValueError(f"{path}: expected a whole number")
        return int(v)
    if kind == "money":
        try:
            f = round(float(v), 2)
        except (TypeError, ValueError):
            raise ValueError(f"{path}: expected an amount in USD") from None
        if isinstance(v, bool) or not 0 <= f <= 100000:
            raise ValueError(f"{path}: expected an amount between 0 and 100000")
        return int(f) if f == int(f) else f
    if kind == "paid_platforms":
        if not isinstance(v, list) or any(x not in ("meta", "google", "tiktok") for x in v):
            raise ValueError(f"{path}: a list of meta, google, tiktok")
        return list(dict.fromkeys(v))
    if kind == "paid_goal":
        if v not in ("leads", "sales", "traffic", "awareness", "messages", "calls"):
            raise ValueError(f"{path}: leads, sales, traffic, awareness, messages or calls")
        return v
    if kind == "bool":
        if not isinstance(v, bool):
            raise ValueError(f"{path}: expected true/false")
        return v
    if kind == "window":
        if v not in ("hour", "today", "week", "month", "year"):          # YouTube's upload-date filter values
            raise ValueError(f"{path}: hour, today, week, month or year")
        return v
    if kind == "langs":                       # ISO 639-1 codes, first = the main one (asked for in keyword search)
        out = lst(v, lambda x: s(x, 40).lower())
        bad = [x for x in out if not re.fullmatch(r"[a-z]{2}", x)]
        if bad:
            raise ValueError(f"{path}: two-letter language codes like en, pl, uk ({', '.join(bad)})")
        return list(dict.fromkeys(out))
    if kind == "region":
        v = s(v, 5).upper()
        if v and not re.fullmatch(r"[A-Z]{2}", v):
            raise ValueError(f"{path}: a two-letter country code like US")
        return v
    if kind == "geo":
        v = s(v, 30)
        if v and not re.fullmatch(r"[A-Z]{2}(-[A-Z0-9]{1,4}){0,2}", v):
            raise ValueError(f"{path}: a Google Trends geo like US, US-IL or US-IL-602")
        return v
    if kind == "hhmm":
        v = s(v, 5)
        if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", v):
            raise ValueError(f"{path}: a time like 08:00")
        return v
    if kind == "approval":
        if v not in ("owner", "auto"):
            raise ValueError(f"{path}: owner or auto")
        return v
    if kind == "per_day":
        if isinstance(v, bool) or not re.fullmatch(r"[1-5]", str(v).strip()):
            raise ValueError(f"{path}: 1 to 5 a day")
        return int(v)
    if kind == "hhmm_list":
        out = [x.strip() for x in (v if isinstance(v, list) else str(v).split(",")) if str(x).strip()]
        bad = [x for x in out if not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", x)]
        if bad or not out or len(out) > 5:
            raise ValueError(f"{path}: 1 to 5 times like 11:30 ({', '.join(bad)})")
        return out
    if kind == "post_platforms":
        if not isinstance(v, list) or any(x not in ("facebook", "linkedin") for x in v):
            raise ValueError(f"{path}: a list of facebook, linkedin")
        return list(dict.fromkeys(v))
    if kind == "jobdays":                     # "daily" or weekday names (jobs/schedule.py)
        days = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")
        items = [x.strip() for x in (v if isinstance(v, list) else str(v).split(","))]
        if items == ["daily"]:
            return "daily"
        bad = [x for x in items if x not in days]
        if bad or not items:
            raise ValueError(f"{path}: daily or weekday names like Monday ({', '.join(bad)})")
        return items[0] if len(items) == 1 else [d for d in days if d in items]
    if kind == "regex":
        return rx(v) if str(v).strip() else ""
    if kind == "regex_list":
        return lst(v, rx)
    if kind == "list":
        return lst(v)
    if kind == "adv":
        def adv(x):
            if isinstance(x, dict):
                n, m = s(x.get("name") or "", 120), s(x.get("match") or "", 300)
                if m:
                    rx(m)
                return {"name": n, "match": m} if n and m else n
            return s(x, 120)
        return lst(v, adv)
    raise ValueError(f"{path}: unknown field")


# ---------- in-place text patching ----------

_KEY = re.compile(r"^(\s*)([\w.-]+|'[^']*'|\"[^\"]*\"):(\s.*|)$")


def _indent(line):
    return len(line) - len(line.lstrip(" "))


def _is_content(line):
    t = line.strip()
    return bool(t) and not t.startswith("#")


def _find(lines, keys, start=0, end=None, indent=0):
    """Line index of `keys` (a.b.c) inside lines[start:end] at `indent`, or (None, deepest found, its indent)."""
    end = len(lines) if end is None else end
    i = start
    while i < end:
        line = lines[i]
        if _is_content(line) and _indent(line) == indent:
            m = _KEY.match(line)
            if m and m.group(2).strip("'\"") == keys[0]:
                if len(keys) == 1:
                    return i, None
                b_end = _block_end(lines, i)
                child = next((_indent(lines[j]) for j in range(i + 1, b_end) if _is_content(lines[j])), None)
                if child is None or child <= indent:
                    return None, (i, keys[1:], indent)
                found, miss = _find(lines, keys[1:], i + 1, b_end, child)
                return (found, miss) if found is not None else (None, miss or (i, keys[1:], indent))
        i += 1
    return None, None


def _block_end(lines, i):
    """End (exclusive) of the value under the key at line i: deeper lines, or '- ' items at the same indent."""
    ind = _indent(lines[i])
    j = i + 1
    last = i
    while j < len(lines):
        line = lines[j]
        if _is_content(line):
            if _indent(line) > ind or (_indent(line) == ind and line.lstrip().startswith("- ")):
                last = j
            else:
                break
        j += 1
    return last + 1


def _flow(v):
    out = yaml.safe_dump(v, default_flow_style=True, allow_unicode=True, width=10 ** 6, sort_keys=False).strip()
    return out[:-4].rstrip() if out.endswith("\n...") else out.removesuffix("...").strip()


def _render(key, v, ind, kind, was_block):
    pad = " " * ind
    if kind == "text" and isinstance(v, str) and v:
        style = "|-" if "\n" in v else ">-"
        body = v.split("\n") if "\n" in v else _wrap(v, 110 - ind - 2)
        return [f"{pad}{key}: {style}"] + [f"{pad}  {ln}" if ln else "" for ln in body]
    if isinstance(v, list) and v:
        one = f"{pad}{key}: {_flow(v)}"
        if not was_block and len(one) <= 120:
            return [one]
        return [f"{pad}{key}:"] + [f"{pad}  - {_flow(x)}" for x in v]
    return [f"{pad}{key}: {_flow(v)}"]


def _wrap(text, width):
    words, out, cur = text.split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}" if cur else w
    return out + ([cur] if cur else [])


def _trailing_comment(line):
    """A '# ...' comment after an inline value (outside quotes), to keep it."""
    q = None
    for i, c in enumerate(line):
        if q:
            q = None if c == q else q
        elif c in "'\"":
            q = c
        elif c == "#" and i and line[i - 1] == " ":
            return line[i:]
    return ""


def _comment_gap(line, comment):
    before = line[:line.rindex(comment)]
    return before[len(before.rstrip()):] or "   "


def _item_key(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False)


def _merge_list(lines, found, end, v):
    """A block list under lines[found]: unchanged items keep their own lines and comments, new ones are added."""
    old, pending, item_ind = {}, [], None
    j = found + 1
    while j < end:
        line = lines[j]
        if not _is_content(line):
            pending.append(line)
            j += 1
            continue
        if line.lstrip().startswith("- ") and (item_ind is None or _indent(line) == item_ind):
            item_ind = _indent(line)
            k = j + 1
            while k < end and (not _is_content(lines[k]) or _indent(lines[k]) > item_ind):
                k += 1
            while k - 1 > j and not _is_content(lines[k - 1]):    # comments after the item belong to the next one
                k -= 1
            chunk = lines[j:k]
            try:
                parsed = yaml.safe_load("\n".join(ln[item_ind:] for ln in chunk))
                if isinstance(parsed, list) and len(parsed) == 1:
                    old.setdefault(_item_key(parsed[0]), pending + chunk)
            except yaml.YAMLError:
                pass
            pending = []
            j = k
            continue
        j += 1
    pad = " " * (item_ind if item_ind is not None else _indent(lines[found]) + 2)
    out = [lines[found]]
    for x in v:
        out.extend(old.pop(_item_key(x), None) or [f"{pad}- {_flow(x)}"])
    return out


def _apply(lines, path, v, kind, tree):
    keys = path.split(".")
    found, miss = _find(lines, keys)
    if found is not None:
        ind = _indent(lines[found])
        end = _block_end(lines, found)
        was_block = end - found > 1
        comment = _trailing_comment(lines[found]) if not was_block else ""
        # keep comment lines that sat at the end of the old block (they usually belong to the next key)
        while end - 1 > found and not _is_content(lines[end - 1]):
            end -= 1
        if was_block and isinstance(v, list) and v and kind != "text":
            lines[found:end] = _merge_list(lines, found, end, v)
            return
        new = _render(keys[-1], v, ind, kind, was_block)
        if comment and len(new) == 1:
            new[0] = f"{new[0]}{_comment_gap(lines[found], comment)}{comment}"
        lines[found:end] = new
        return
    if miss:                                  # parent exists, key doesn't: add it at the end of the parent block
        at, rest, ind = miss
        m = _KEY.match(lines[at])
        inline = (m.group(3) or "").strip() if m else ""
        if inline and not inline.startswith("#"):   # parent is a one-line value like {a: 1}: rewrite that line
            parent = keys[:len(keys) - len(rest)]
            new = f"{' ' * ind}{parent[-1]}: {_flow(_get(tree, '.'.join(parent)))}"
            comment = _trailing_comment(lines[at])
            lines[at] = f"{new}{_comment_gap(lines[at], comment)}{comment}" if comment else new
            return
        end = _block_end(lines, at)
        while end - 1 > at and not _is_content(lines[end - 1]):
            end -= 1
        child = next((_indent(lines[j]) for j in range(at + 1, end) if _is_content(lines[j])), ind + 2)
        nested = {}
        _put(nested, ".".join(rest), v)
        lines[end:end] = _render_tree(nested, child, kind)
        return
    if path == "display_name":                # top-level: right after name:, or at the top
        at = next((i for i, ln in enumerate(lines) if ln.startswith("name:")), -1)
        lines[at + 1:at + 1] = _render("display_name", v, 0, kind, False)
        return
    nested = {}
    _put(nested, path, v)
    if lines and lines[-1].strip():
        lines.append("")
    lines.extend(_render_tree(nested, 0, kind))


def _render_tree(d, ind, kind):
    out = []
    for k, v in d.items():
        if isinstance(v, dict):
            out.append(f"{' ' * ind}{k}:")
            out.extend(_render_tree(v, ind + 2, kind))
        else:
            out.extend(_render(k, v, ind, kind, False))
    return out


def set_fields(name, patch, base=None):
    p = _path(name)
    text = p.read_bytes().decode("utf-8")
    if base and base != _hash(text):
        raise ValueError("The profile changed since this page loaded (edited elsewhere). Reload and try again.")
    raw = yaml.safe_load(text) or {}
    expected = copy.deepcopy(raw)
    lines = text.splitlines()
    changed = []
    for path, v in (patch or {}).items():
        if path not in FIELDS:
            raise ValueError(f"{path}: not editable here")
        v = _clean(path, FIELDS[path], v)
        old = _get(raw, path)
        if FIELDS[path] == "text" and isinstance(old, str):
            old = old.strip()
        if old == v or (old is MISSING and v in ("", [], None)):
            continue
        _put(expected, path, v)
        _apply(lines, path, v, FIELDS[path], expected)
        changed.append(path)
    if not changed:
        return {"changed": [], "base": _hash(text)}
    nl = "\r\n" if "\r\n" in text else "\n"        # keep the file's own line endings
    new_text = nl.join(lines) + nl
    try:
        got = yaml.safe_load(new_text) or {}
    except yaml.YAMLError as e:
        raise ValueError(f"Not saved: the edit would break the YAML ({e}). The file is unchanged.")
    for path in changed:                      # folded text loads with its own whitespace: compare stripped
        if FIELDS[path] == "text":
            _put(got, path, (_get(got, path) or "").strip())
    if got != expected:
        raise ValueError("Not saved: the edited file didn't read back as expected. The file is unchanged.")
    backups = config.ROOT / "data" / "profile-backups"
    backups.mkdir(parents=True, exist_ok=True)
    # Two edits in one second must not overwrite the first backup (the one with the original text).
    stamp = f"{p.stem}-{datetime.now():%Y%m%d-%H%M%S}"
    dest, n = backups / f"{stamp}.yaml", 1
    while dest.exists():
        dest, n = backups / f"{stamp}-{n}.yaml", n + 1
    shutil.copy2(p, dest)
    p.write_bytes(new_text.encode("utf-8"))
    config.load(p.stem)                       # still loads with the defaults merged
    return {"changed": changed, "base": _hash(new_text)}


def cli(argv):
    if len(argv) >= 2 and argv[1] == "delete":      # Settings → Delete business (moves everything to data/deleted/)
        from .profile_delete import delete
        confirm = argv[argv.index("--confirm") + 1] if "--confirm" in argv[:-1] else ""
        try:
            print(json.dumps(delete(argv[0], confirm), ensure_ascii=False))
            return 0
        except ValueError as e:
            print(json.dumps({"error": str(e)}, ensure_ascii=False))
            return 1
    if len(argv) < 2 or argv[1] not in ("get", "set"):
        print("usage: python -m viral_scout profile <name> get | set | delete --confirm <name>  (set reads JSON from stdin)")
        return 2
    try:
        if argv[1] == "get":
            print(json.dumps(get(argv[0]), ensure_ascii=False))
            return 0
        body = json.loads(sys.stdin.read() or "{}")
        out = set_fields(argv[0], body.get("set") or {}, body.get("base"))
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except ValueError as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        return 1
