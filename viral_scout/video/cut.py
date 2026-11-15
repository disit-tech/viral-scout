"""Step 2–3: script-aware rough cut (best take of every line, flubs dropped) and pause trimming by word timings.

Pause trimming works on the WhisperX word times instead of re-detecting silence (what auto-editor does), so the
captions stay frame-exact with the cut. Gaps between words longer than MAX_GAP shrink to KEEP_GAP.

Number matching (NUM): Whisper writes digits ("17th", "911"), scripts for an AI voice spell them out. Both sides are
normalised to digits so a spelled-out word at the edge of a take is not trimmed off. Anything the cut removed is
listed in edit.json `dropped`: with an AI voice there are no real flubs, so read it.
English number words only; other languages still cut, but spelled-out numbers may mismatch.
"""
import re
from difflib import SequenceMatcher

NUM = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
    "seventeen eighteen nineteen twenty".split())}
NUM.update({"thirty": "30", "forty": "40", "fifty": "50", "hundred": "100"})
# ordinals: the script spells "seventeenth" for the AI voice, Whisper writes "17th"
_ORD = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth thirteenth "
        "fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth twentieth").split()
NUM.update({w: f"{i}{'th' if 10 <= i % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(i % 10, 'th')}"
            for i, w in enumerate(_ORD, 1)})
NUM["thirtieth"] = "30th"
FILLERS = {"uh", "um", "erm", "uhm", "hmm"}
WILD = "*"

PAD_IN, PAD_OUT = 0.08, 0.14  # breathing room around each kept take (s)
MAX_GAP, KEEP_GAP = 0.30, 0.12  # pauses inside a take longer than MAX_GAP shrink to KEEP_GAP
MIN_SCORE = 0.62  # below this a line counts as missing
PREFER_LATER = 0.06  # a later take within this score of the best wins (the last take is usually the clean one)


def norm(word: str) -> str:
    w = word.lower().strip()
    w = re.sub(r"[^\w'*$%]", "", w.replace("’", "'"))
    w = w.replace(",", "").strip("'")
    return NUM.get(w, w)


def tokens(text: str) -> list[str]:
    out = []
    for raw in re.split(r"[\s/]+", text):  # "grid-tied" stays one token ("gridtied"), like Whisper's word
        if re.fullmatch(r"\[[^\]]+\]", raw.strip(".,!?;:")):
            out.append(WILD)
            continue
        t = norm(raw)
        if t:
            out.append(t)
    return out


def match_script_words(words: list[dict], lines: list[dict]) -> list[dict]:
    """Make the transcript split words the way the script does: "back up" → BACKUP, "grid tied" → grid-tied
    (two words joined), "kilowatt-hours" → kilowatt hours (one word split, time shared by length).
    Otherwise the rough cut sees a mismatch at the edge of a take and trims the word off."""
    seq = [t for line in lines for t in tokens(line["text"])]
    single = set(seq)
    pairs = set(zip(seq, seq[1:]))
    out: list[dict] = []
    k = 0
    while k < len(words):
        w = words[k]
        a = norm(w["w"])
        if k + 1 < len(words):
            b = norm(words[k + 1]["w"])
            if a + b in single and (a, b) not in pairs:
                out.append({**w, "w": w["w"] + words[k + 1]["w"], "e": words[k + 1]["e"]})
                k += 2
                continue
        if a.isdigit() and 1 < len(a) <= 4 and a not in single and _has_run(seq, list(a)):
            # "nine one one" in the script, "911" from Whisper: one word → one digit each, time shared
            t, span = w["s"], (w["e"] - w["s"]) / len(a)
            for c in a:
                out.append({**w, "w": c, "s": round(t, 3), "e": round(t + span, 3)})
                t += span
            k += 1
            continue
        parts = [norm(p) for p in re.split(r"(?<=\w)-(?=\w)", w["w"])]
        if len(parts) > 1 and a not in single and all(p in single for p in parts):
            t, span = w["s"], w["e"] - w["s"]
            total = sum(len(p) for p in parts)
            for raw, p in zip(re.split(r"(?<=\w)-(?=\w)", w["w"]), parts):
                e = t + span * len(p) / total
                out.append({**w, "w": raw, "s": round(t, 3), "e": round(e, 3)})
                t = e
            k += 1
            continue
        out.append(w)
        k += 1
    return out


def _has_run(seq: list[str], run: list[str]) -> bool:
    """True if `run` appears in `seq` as consecutive tokens ("9 1 1" for Whisper's "911"; not "48" for "40 8")."""
    n = len(run)
    return any(seq[i:i + n] == run for i in range(len(seq) - n + 1))


def _close(a: str, b: str) -> bool:
    """A misheard word ("gold" for "cold"): same length ±1, one letter off. Digits never count as close."""
    return (a != b and not a.isdigit() and not b.isdigit() and len(a) >= 3 and abs(len(a) - len(b)) <= 1
            and SequenceMatcher(None, a, b).ratio() >= 0.75)


def _ratio(a: list[str], b: list[str]) -> float:
    # a placeholder in the script ([NAME]) is left out: whatever was said there only costs a little
    return SequenceMatcher(None, [x for x in a if x != WILD], b, autojunk=False).ratio()


def find_takes(line_toks: list[str], words: list[dict]) -> list[dict]:
    """All non-overlapping windows of the transcript that look like this line, best first."""
    said = [norm(w["w"]) for w in words]
    n = len([t for t in line_toks if t != WILD])
    cands = []
    for i in range(len(said)):
        if said[i] in FILLERS:
            continue
        for m in range(max(1, n - 3), n + 4):
            j = i + m
            if j > len(said):
                break
            win = [t for t in said[i:j] if t not in FILLERS]
            score = _ratio(line_toks, win)
            if score >= MIN_SCORE:
                cands.append((score, i, j))
    cands.sort(key=lambda c: (-c[0], c[1]))
    taken: list[tuple[float, int, int]] = []
    for c in cands:
        if all(c[2] <= t[1] or c[1] >= t[2] for t in taken):
            taken.append(c)
    takes = []
    for score, i, j in taken:
        i, j = _trim(line_toks, said, i, j)
        takes.append({"score": round(score, 3), "i": i, "j": j, "s": words[i]["s"], "e": words[j - 1]["e"]})
    return takes


def _trim(line_toks: list[str], said: list[str], i: int, j: int) -> tuple[int, int]:
    """Drop leading/trailing words that aren't in the line (a filler, the start of the next attempt)."""
    toks = [t for t in line_toks if t != WILD]
    sm = SequenceMatcher(None, toks, said[i:j], autojunk=False)
    blocks = [b for b in sm.get_matching_blocks() if b.size]
    if not blocks:
        return i, j
    a0, b0 = i + blocks[0].b, i + blocks[-1].b + blocks[-1].size
    # Keep a misheard first/last word ("you lose cold" heard as "gold"): trimming it cuts the word out of the audio.
    first, last = blocks[0], blocks[-1]
    # (the best-scoring window often stops just short of it, so look one word outside the window too)
    if first.a > 0 and a0 > 0 and _close(toks[first.a - 1], said[a0 - 1]):
        a0 -= 1
    if last.a + last.size < len(toks) and b0 < len(said) and _close(toks[last.a + last.size], said[b0]):
        b0 += 1
    return a0, b0


def choose(takes: list[dict]) -> dict | None:
    if not takes:
        return None
    best = max(t["score"] for t in takes)
    good = [t for t in takes if t["score"] >= best - PREFER_LATER]
    return max(good, key=lambda t: t["s"])


def rough_cut(lines: list[dict], words: list[dict], log=print) -> dict:
    """Picks one take per script line, in script order. Returns {"lines": [...], "dropped": [...], "missing": [...]}."""
    used: list[tuple[int, int]] = []
    out, missing = [], []
    after = 0  # end of the previous line's take: takes come in script order
    all_takes = [find_takes(tokens(line["text"]), words) for line in lines]
    for k, line in enumerate(lines):
        takes = [t for t in all_takes[k] if all(t["j"] <= a or t["i"] >= b for a, b in used)]
        # A short line ("One.") also matches inside a later line ("leave one lamp", "nine one one");
        # "last take wins" would grab that one and the later line goes missing. So prefer takes after the
        # previous line and before the next line's first take (retakes of a line sit next to each other).
        nxt = [t["i"] for t in all_takes[k + 1] if t["i"] >= after] if k + 1 < len(lines) else []
        before = min(nxt) if nxt else len(words)
        pick = (choose([t for t in takes if after <= t["i"] < before])
                or choose([t for t in takes if t["i"] >= after]) or choose(takes))
        if pick:
            after = max(after, pick["j"])
        if not pick:
            missing.append(line["text"])
            log(f"  ✗ line {k + 1} not found in the recording: {line['text']}")
            continue
        used.append((pick["i"], pick["j"]))
        others = len(takes) - 1
        log(f"  ✓ line {k + 1}: take at {pick['s']:.1f}s (match {pick['score']:.2f}{f', {others} other take(s)' if others else ''})")
        out.append({**line, "take": pick})
    kept = sorted(used)
    dropped, prev = [], 0
    for a, b in kept:
        if a > prev:
            dropped.append(" ".join(w["w"] for w in words[prev:a]))
        prev = b
    if prev < len(words):
        dropped.append(" ".join(w["w"] for w in words[prev:]))
    return {"lines": out, "dropped": [d for d in dropped if d.strip()], "missing": missing}


def build_timeline(cut: dict, words: list[dict], duration: float) -> tuple[list[tuple[float, float]], list[dict]]:
    """Source segments to keep (in output order) + every kept word with its new time and line index."""
    segs: list[tuple[float, float]] = []
    timed: list[dict] = []
    t = 0.0
    for k, line in enumerate(cut["lines"]):
        i, j = line["take"]["i"], line["take"]["j"]
        ws = [w for w in words[i:j] if norm(w["w"]) not in FILLERS]
        # sub-segments: split at long pauses
        chunk_s = max(0.0, ws[0]["s"] - PAD_IN)
        prev_e = ws[0]["e"]
        groups = [[ws[0]]]
        for w in ws[1:]:
            if w["s"] - prev_e > MAX_GAP:
                groups.append([w])
            else:
                groups[-1].append(w)
            prev_e = w["e"]
        for g, grp in enumerate(groups):
            s = chunk_s if g == 0 else grp[0]["s"] - KEEP_GAP / 2
            e = grp[-1]["e"] + (PAD_OUT if g == len(groups) - 1 else KEEP_GAP / 2)
            e = min(e, duration)
            if segs and segs[-1][0] < s < segs[-1][1]:  # adjacent takes: don't play the same audio twice
                s = segs[-1][1]
            offset = t - s
            for w in grp:
                timed.append({"w": w["w"], "s": round(w["s"] + offset, 3), "e": round(w["e"] + offset, 3), "line": k})
            segs.append((round(s, 3), round(e, 3)))
            t += e - s
        line["t0"] = round(t - sum(e - s for s, e in segs[len(segs) - len(groups):]), 3)
        line["t1"] = round(t, 3)
    return segs, timed
