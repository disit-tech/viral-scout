"""HTTP client for the ideas API (today the solar site's /api/ideas and /api/blog-review).

The requests are the same as solar site/scripts/ideas.mjs sends: same paths, methods, headers and JSON
bodies (compact, `project` first on push). The project slug always comes from the profile; it can't be passed in.
"""
import json
import time
import urllib.error
import urllib.request
from urllib.parse import quote

from . import packs as packs_mod
from .settings import (BATCH_MAX, FIELDS, IDEAS_MAX, PLATFORMS, REQUIRED, STAGES, IdeasError)

PUSH_TIMEOUT = 180


def urllib_transport(method, url, headers, body, timeout=60):
    """→ (status, text). Network errors raise IdeasError."""
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        base = url.split("/api/")[0]
        raise IdeasError(f"Can't reach {base}: is the site running? {e}") from e


def dumps(obj):
    """JSON.stringify: compact, unicode as is."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))


class Client:
    def __init__(self, project, base, secret, transport=None):
        self.project, self.base, self.secret = project, base.rstrip("/"), secret
        self.transport = transport or urllib_transport

    def call(self, method, body=None, path="/api/ideas", timeout=None):
        headers = {"Authorization": f"Bearer {self.secret}", "Content-Type": "application/json"}
        data = dumps(body).encode("utf-8") if body is not None else None
        status, text = self.transport(method, f"{self.base}{path}", headers, data, **({"timeout": timeout} if timeout else {}))
        if not 200 <= status < 300:
            raise IdeasError(f"{status} {text}")
        return json.loads(text) if text else {}

    # reads
    def pull(self):
        return self.call("GET", None, f"/api/ideas?project={quote(self.project, safe='')}")

    def ensure_own(self, ids):
        """Refuse ids that aren't this project's ideas. tracked / repost / script / stage carry no project in the
        API body, so without this a typo could touch another project's idea."""
        mine = {i["id"] for i in self.pull().get("ideas", [])}
        other = [i for i in ids if i not in mine]
        if other:
            raise IdeasError(f"not {self.project} ideas: {', '.join('#' + str(i) for i in other)}")

    # writes
    def push(self, batch):
        if batch.get("project") not in (None, self.project):
            raise IdeasError(f"the batch says project {batch['project']!r}, this profile is {self.project!r}")
        body = {"project": self.project, **{k: v for k, v in batch.items() if k not in ("project", "pushed")}}
        # The service posts each idea to Telegram before it answers: a batch of 5-20 can take a while.
        return self.call("POST", body, timeout=PUSH_TIMEOUT)

    def _batch_rows(self, name):
        name = (name or "").strip()
        return {(i.get("title") or "").strip(): i for i in self.pull().get("ideas", []) if i.get("batch") == name}

    def push_once(self, batch, sleep=time.sleep, settle_s=20, settle_max=9):
        """push, safe to run again: ideas of this batch already in the service (same batch name and title) are not
        sent again, and one stored without its Telegram message is posted (repost) instead of pushed twice.
        After a timeout the service may still be working on the request, so the batch is watched until it stops
        changing before anything is resent. Returns {created, messages: {id: message id or None}, skipped, retried}."""
        name = batch.get("batch")
        titles = [(i.get("title") or "").strip() for i in batch.get("ideas") or []]
        missing = lambda have: [i for i, t in zip(batch["ideas"], titles) if t not in have]  # noqa: E731
        have = self._batch_rows(name)
        skipped = len(titles) - len(missing(have))
        first_try = None
        if missing(have):
            try:
                self.push({**batch, "ideas": missing(have)})
            except IdeasError as e:
                if str(e)[:1] == "4":          # the API refused the body (HTTP 4xx): nothing was stored
                    raise
                # A timeout, a dropped connection or a 5xx: part of it may be stored and posted, and the service
                # may still be at it. Wait until the batch stops changing, then send only what isn't there.
                first_try = str(e)[:200]
                have = self._settle(name, sleep, settle_s, settle_max)
                if missing(have):
                    self.push({**batch, "ideas": missing(have)})
        have = self._batch_rows(name)
        # Stored but never posted (the bot's message failed, or the request died in between): post it now, once.
        unposted = [have[t]["id"] for t in titles if t in have and not have[t].get("tgMessageId") and have[t].get("status") == "sent"]
        if unposted:
            self.call("PATCH", {"ids": unposted, "repost": True})
            have = self._batch_rows(name)
        if missing(have):
            raise IdeasError(f"not stored: {[i.get('title') for i in missing(have)]}; run the same push again (it sends only what is missing)")
        rows = [have[t] for t in dict.fromkeys(titles)]
        out = {"batch": name, "created": [r["id"] for r in rows], "messages": {str(r["id"]): r.get("tgMessageId") for r in rows},
               "already_there": skipped, "reposted": unposted}
        if first_try:
            out["first_try"] = first_try
        return out

    def _settle(self, name, sleep, every, tries):
        """The batch's rows once two looks in a row agree (ids and message ids), at most `tries` looks."""
        last = None
        for _ in range(tries):
            try:
                rows = self._batch_rows(name)
            except IdeasError:
                rows = None
            snap = None if rows is None else sorted((r["id"], r.get("tgMessageId")) for r in rows.values())
            if snap is not None and snap == last:
                return rows
            last = snap
            sleep(every)
        if last is None:
            raise IdeasError("the ideas service doesn't answer; nothing resent (run the same push again later: it only sends what is missing)")
        return self._batch_rows(name)

    def tracked(self, ids):
        self.ensure_own(ids)
        return self.call("PATCH", {"ids": ids, "status": "tracked"})

    def repost(self, ids):
        self.ensure_own(ids)
        return self.call("PATCH", {"ids": ids, "repost": True})

    def script(self, idea_id, text):
        self.ensure_own([idea_id])
        return self.call("PATCH", {"id": idea_id, "script": text})

    def stage(self, idea_id, stage, draft=None):
        self.ensure_own([idea_id])
        body = {"id": idea_id, "stage": stage}
        if draft is not None:
            body["draftPath"] = draft
        return self.call("PATCH", body)

    def pack(self, idea_id, sections, note, store_only=False):
        body = {"id": idea_id, "project": self.project, "pack": sections, "note": note}
        if store_only:
            body["send"] = False
        return self.call("PATCH", body)

    def blog(self, slug, title, summary):
        return self.call("POST", {"slug": slug, "title": title, "summary": summary}, "/api/blog-review")

    def blog_list(self):
        return self.call("GET", None, "/api/blog-review")

    def status(self, all_projects=False):
        q = "" if all_projects else f"?project={quote(self.project, safe='')}"
        return self.call("GET", None, f"/api/status{q}")

    def test_bot(self, role):
        return self.call("POST", {"project": self.project, "role": role}, "/api/status")

    def blog_published(self, review_id):
        return self.call("PATCH", {"id": review_id, "status": "published"}, "/api/blog-review")


def check_batch(batch, ic):
    """Field limits the API enforces, plus the profile's score threshold and banned words → (errors, warnings)."""
    errors, warnings = [], []
    if not isinstance(batch, dict):
        return ["the file must be a JSON object {batch, ideas}"], []
    name = batch.get("batch")
    if not isinstance(name, str) or not name.strip() or len(name.strip()) > BATCH_MAX:
        errors.append(f"batch: a name of 1-{BATCH_MAX} chars is required")
    ideas = batch.get("ideas")
    if not isinstance(ideas, list) or not 1 <= len(ideas) <= IDEAS_MAX:
        return errors + [f"ideas: 1-{IDEAS_MAX} ideas required"], warnings
    allowed = set(ic["packs"].get("platforms") or PLATFORMS) & set(PLATFORMS)
    threshold = ic["score"].get("threshold")
    banned = ic["packs"].get("banned_words") or []
    for n, idea in enumerate(ideas, 1):
        where = f"idea {n} ({str(idea.get('title', ''))[:40]})" if isinstance(idea, dict) else f"idea {n}"
        if not isinstance(idea, dict):
            errors.append(f"{where}: not an object")
            continue
        for k in REQUIRED:
            if not str(idea.get(k) or "").strip():
                errors.append(f"{where}: {k} is required")
        for k, lim in FIELDS.items():
            v = idea.get(k)
            if v is None:
                continue
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{where}: {k} must be non-empty text (or left out)")
            elif len(v.strip()) > lim:
                errors.append(f"{where}: {k} is {len(v.strip())} chars, the API allows {lim}")
        extra = set(idea) - set(FIELDS) - {"score", "platforms", "replaces", "variantOf"}
        if extra:
            warnings.append(f"{where}: unknown fields are dropped by the API: {', '.join(sorted(extra))}")
        s = idea.get("score")
        if s is not None:
            if not isinstance(s, int) or isinstance(s, bool) or not 0 <= s <= 50:
                errors.append(f"{where}: score must be a whole number 0-50")
            elif threshold and s < threshold:
                errors.append(f"{where}: score {s} is under the profile's threshold {threshold}")
        for k in ("replaces", "variantOf"):
            v = idea.get(k)
            if v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 1):
                errors.append(f"{where}: {k} must be an idea id")
        if idea.get("replaces") and idea.get("variantOf"):
            errors.append(f"{where}: use replaces or variantOf, not both")
        pl = idea.get("platforms")
        if pl is not None:
            if not isinstance(pl, list) or len(pl) > 12:
                errors.append(f"{where}: platforms must be a list of at most 12 keys")
            else:
                bad = [p for p in pl if p not in allowed]
                if bad:
                    errors.append(f"{where}: platforms not allowed here: {', '.join(map(str, bad))} "
                                  f"(allowed: {', '.join(sorted(allowed))})")
        text = "\n".join(str(idea.get(k) or "") for k in ("title", "hook", "cta"))
        e, w = packs_mod.text_problems(where, text, banned)
        warnings += e + w   # ideas are drafts for rating; banned words only block a pack
    return errors, warnings


def check_stage(stage):
    if stage not in STAGES:
        raise IdeasError(f"stage must be one of {', '.join(STAGES)}")
