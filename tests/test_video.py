"""Tests for viral_scout.video: the parts that need no heavy tools (script, cut, plan, captions, cards, settings, CLI),
plus an FFmpeg smoke test (camera mode, transcript seeded) that skips when FFmpeg is missing.

  python -m pytest tests            (if pytest is installed)
  python tests/test_video.py        (no dependencies: runs every test_ function)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from viral_scout.video import captions, cards, plan, settings  # noqa: E402
from viral_scout.video.cli import main as video_main  # noqa: E402
from viral_scout.video.cut import build_timeline, match_script_words, norm, rough_cut, tokens  # noqa: E402
from viral_scout.video.script import load_script  # noqa: E402

FIX = Path(__file__).resolve().parent / "fixtures" / "video"
PROFILE = FIX / "profile.yaml"
SCRIPT = FIX / "script.md"


class Skip(Exception):
    pass


def skip(why):
    try:
        import pytest
        pytest.skip(why)
    except ImportError:
        raise Skip(why)


def vset():
    os.environ.setdefault("OBSIDIAN_VAULT", "C:/vault")
    return settings.load(str(PROFILE))


def say(*phrases, word=0.3, gap=0.6):
    """A fake WhisperX transcript: each phrase is spoken word by word, phrases separated by a pause."""
    out, t = [], 0.5
    for ph in phrases:
        for w in ph.split():
            out.append({"w": w, "s": round(t, 3), "e": round(t + word - 0.05, 3)})
            t += word
        t += gap
    return out


# The recording: a flubbed first take of the hook, then the clean take, Whisper's digits ("17th", "911", "4"),
# a misheard word ("gold" for "cold") and the CTA.
TAKES = say(
    "Last year storms left over two million uh homes in the... sorry, let me start again.",
    "Last year storms left over two million homes in the dark.",
    "I'm Alex.",
    "The test is on the 17th.",
    "If the power goes out, call 911 only for emergencies.",
    "Keep your fridge closed, food stays gold for 4 hours.",
    "Comment backup and I'll send you the link.",
)


def script_lines():
    return load_script(SCRIPT, "1", "Alex")["lines"]


# ---- settings -----------------------------------------------------------------------------------------------------
def test_settings_from_profile():
    v = vset()
    assert v["brand"] == "Example Solar Co"
    assert v["brand_label"] == "EXAMPLE SOLAR CO"
    assert v["studio"]["vault_dir"].startswith(os.environ["OBSIDIAN_VAULT"])     # ${OBSIDIAN_VAULT} in a nested block
    assert v["footage_dir"] is None                                              # unset env var → not a folder
    assert v["output_dir"] == ROOT / "data" / "video" / "example-solar-video"
    assert v["script_dir"] == FIX
    assert v["voice"]["reference"] == FIX / "voice" / "ref.wav" and v["voice"]["cfg"] == 0.4
    assert v["voice"]["exaggeration"] == 0.5                                     # default kept
    assert v["cta_card"]["big"] == "Free Backup Check"                           # from studio.cta
    assert v["ai_label"].endswith("-Alex")
    assert settings.allowed(v, "voice+cards") and not settings.allowed(v, "TWIN")
    assert settings.DEFAULTS["cta_card"]["big"] == ""                            # defaults not mutated


def test_vocabulary_forms():
    assert settings.vocabulary({"vocabulary": ["Powerwall"]}) == {r"\bPowerwall\b": "Powerwall"}
    v = vset()
    voc = settings.vocabulary(v)
    assert captions.apply_vocab("city power", voc) == "CityPower"
    assert captions.apply_vocab("State power's", voc) == "StatePower's"
    assert captions.apply_vocab("13 kwh", voc) == "13 kWh"
    assert captions.apply_vocab("powerwall", settings.vocabulary({"vocabulary": ["Powerwall"]})) == "Powerwall"


def test_colors():
    assert settings.ass_color("#ffc45c") == "&H005CC4FF"
    assert settings.hex_rgb("#fff") == (255, 255, 255)
    try:
        settings.hex_rgb("yellow")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


# ---- script ---------------------------------------------------------------------------------------------------------
def test_script_section_and_parts():
    sc = load_script(SCRIPT, "1", "Alex")
    assert sc["title"] == "1. Storm night"
    texts = [l["text"] for l in sc["lines"]]
    assert texts[0] == "Last year storms left over two million homes in the dark."
    assert "I'm Alex." in texts
    assert [l["part"] for l in sc["lines"]][0] == "hook" and sc["lines"][-1]["part"] == "cta"
    assert len(sc["lines"]) == 6
    assert not any("four hours.\" (b)" in t for t in texts)                       # alternative hooks are not spoken
    two = load_script(SCRIPT, "Second", None)
    assert [l["text"] for l in two["lines"]] == ["This is the second script.", "Follow for more."]


def test_script_plain_text_and_missing_section():
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "plain.txt"
        p.write_text("# Title\nFirst sentence here. Second one — with a dash.\n", encoding="utf-8")
        lines = load_script(p)["lines"]
        assert [l["text"] for l in lines] == ["First sentence here.", "Second one, with a dash."]
    try:
        load_script(SCRIPT, "9")
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


# ---- cut: number matching, best take, dropped -------------------------------------------------------------------------
def test_number_words_normalise_to_digits():
    assert norm("seventeenth") == "17th" == norm("17th.")
    assert norm("four") == norm("4") == "4"
    assert norm("twenty-first") != "21st"            # beyond the table: known gap (docs/video.md)
    assert tokens("I'm [NAME].")[1] == "*"


def test_match_script_words_splits_911():
    ws = match_script_words(say("call 911 now"), [{"text": "Call nine one one now.", "part": "body"}])
    assert [w["w"] for w in ws] == ["call", "9", "1", "1", "now"]
    assert ws[1]["s"] < ws[2]["s"] < ws[3]["s"] and ws[3]["e"] <= ws[4]["s"]


def test_match_script_words_joins_and_splits():
    lines = [{"text": "Get a backup plan for kilowatt hours.", "part": "body"}]
    ws = match_script_words(say("get a back up plan for kilowatt-hours"), lines)
    assert [w["w"] for w in ws] == ["get", "a", "backup", "plan", "for", "kilowatt", "hours"]


def test_rough_cut_last_good_take_and_dropped():
    lines = script_lines()
    words = match_script_words(TAKES, lines)
    rc = rough_cut(lines, words, log=lambda m: None)
    assert len(rc["lines"]) == 6 and rc["missing"] == []
    hook = rc["lines"][0]["take"]
    assert words[hook["i"]]["w"] == "Last" and words[hook["j"] - 1]["w"] == "dark."
    assert hook["s"] > 3.0                                                       # the second (clean) take
    assert len(rc["dropped"]) == 1 and "sorry, let me start again." in rc["dropped"][0]
    assert "17th." in [w["w"] for w in words[rc["lines"][2]["take"]["i"]:rc["lines"][2]["take"]["j"]]]


def test_rough_cut_missing_line():
    lines = script_lines() + [{"text": "This sentence was never recorded at all.", "part": "body"}]
    rc = rough_cut(lines, match_script_words(TAKES, lines), log=lambda m: None)
    assert rc["missing"] == ["This sentence was never recorded at all."]


def test_timeline_tightens_and_captions_fix():
    lines = script_lines()
    words = match_script_words(TAKES, lines)
    rc = rough_cut(lines, words, log=lambda m: None)
    segs, timed = build_timeline(rc, words, duration=60)
    total = sum(e - s for s, e in segs)
    assert total < TAKES[-1]["e"] - TAKES[0]["s"]                                # flub and pauses removed
    assert all(b["s"] >= a["s"] for a, b in zip(timed, timed[1:]))
    fixed = captions.fix_words(rc["lines"], timed, settings.vocabulary(vset()))
    said = [w["w"] for w in fixed]
    assert "cold" in said and "gold" not in said                                 # misheard word fixed from the script
    assert "17th." in said and "4" in said                                       # digits kept on screen
    assert "BACKUP" in said                                                      # case from the script
    film = captions.fix_words(rc["lines"], timed, {}, keep_digits=False)
    assert "seventeenth." in [w["w"] for w in film]


def test_ass_and_srt_brand_style():
    lines = script_lines()
    words = match_script_words(TAKES, lines)
    rc = rough_cut(lines, words, log=lambda m: None)
    _, timed = build_timeline(rc, words, duration=60)
    with tempfile.TemporaryDirectory() as d:
        ass, srt = Path(d) / "c.ass", Path(d) / "c.srt"
        captions.write_ass(timed, ass, {0}, {"font": "Arial", "accent": "#00ff00", "text": "#ffffff"})
        text = ass.read_text(encoding="utf-8")
        assert "Style: Cap,Arial,96" in text and "\\c&H0000FF00" in text
        assert text.count("Dialogue:") == len(timed)
        cues = srt.write_text("") or captions.write_srt(timed, srt) or srt.read_text(encoding="utf-8")
        assert cues.startswith("1\n00:00:")
    assert all(len(g) <= captions.MAX_WORDS for g in captions.groups(timed))


# ---- plan: auto cards -------------------------------------------------------------------------------------------------
def test_auto_cards_use_profile_cta_and_units():
    v = vset()
    stat = plan.stat_pattern(v["stat_units"])
    hook = plan.auto_card({"text": "Storms left over two million homes in the dark.", "part": "hook"}, v["cta_card"], stat)
    assert hook["kind"] == "stat" and hook["big"] == "2 million" and hook["source"] == "ADD SOURCE"
    kwh = plan.auto_card({"text": "A battery holds thirteen kWh of energy.", "part": "body"}, v["cta_card"], stat)
    assert kwh["kind"] == "headline"                                              # "thirteen" isn't a number word here
    kwh = plan.auto_card({"text": "A battery holds 13 kWh of energy.", "part": "body"}, v["cta_card"], stat)
    assert kwh["big"] == "13 kWh"
    cta = plan.auto_card({"text": "Comment BACKUP and I'll send you the link.", "part": "cta"}, v["cta_card"], stat)
    assert cta == {"kind": "cta", "big": "Free Backup Check", "pill": "Link in bio"}
    lst = plan.auto_card({"text": "Three things: water, light, and heat.", "part": "body"})
    assert lst["kind"] in ("list", "stat")
    ordinal = plan.auto_card({"text": "The test is on the seventeenth.", "part": "body"}, v["cta_card"], stat)
    assert ordinal["kind"] == "headline"                                          # not "7" + "teenth"
    head = plan.auto_card({"text": "Nobody tells you this.", "part": "body"})
    assert head["kind"] == "headline" and "*" in head["big"]


def test_draft_visuals_and_cover():
    lines = [dict(l, t0=i * 2.0, t1=i * 2.0 + (1.0 if i == 1 else 2.0)) for i, l in enumerate(script_lines())]
    v = vset()
    visuals, cover = plan.draft(lines, [], v["cta_card"], v["stat_units"])
    assert visuals[0]["lines"] == [0, 1]                                         # a short line rides on the previous card
    assert visuals[-1]["card"]["kind"] == "cta"
    assert cover == {"kind": "cover", "big": "*2 million*", "small": ""}


# ---- cards: template with brand values ----------------------------------------------------------------------------------
def test_card_template_filled_with_brand():
    v = vset()
    with tempfile.TemporaryDirectory() as d:
        page = cards.write_template(v, Path(d)).read_text(encoding="utf-8")
    assert "{{" not in page
    assert "--accent:#ffc45c" in page and "--accent-rgb:255,196,92" in page
    assert "EXAMPLE SOLAR CO" in page and 'class="dot"' in page
    assert '--font-display:"Segoe UI Black"' in page
    v2 = dict(v, brand_label="A & B <Co>", colors=dict(v["colors"], accent="#112233"))
    vals = cards.values(v2)
    assert vals["brand_label"] == "A &amp; B &lt;Co&gt;" and vals["accent_rgb"] == "17,34,51"


def test_card_template_override_and_bad_placeholder():
    v = vset()
    with tempfile.TemporaryDirectory() as d:
        t = Path(d) / "mine.html"
        t.write_text("<b style='color:{{accent}}'>{{brand_label}}</b>", encoding="utf-8")
        assert cards.write_template(dict(v, card_template=t), Path(d)).read_text(encoding="utf-8") == \
            "<b style='color:#ffc45c'>EXAMPLE SOLAR CO</b>"
        t.write_text("{{nope}}", encoding="utf-8")
        try:
            cards.write_template(dict(v, card_template=t), Path(d))
            raise AssertionError("expected ValueError")
        except ValueError as e:
            assert "nope" in str(e)


def test_card_specs_from_edit():
    from viral_scout.video.pipeline import card_specs
    edit = {"visuals": [{"id": "v01", "card": {"kind": "headline", "big": "x"}},
                        {"id": "v02", "card": {"kind": "headline", "big": "y"}, "broll": "a.mp4"}],
            "cover": {"kind": "cover", "big": "z"}}
    assert [c["id"] for c in card_specs(edit)] == ["v01", "cover"]


# ---- CLI: clear errors when heavy tools are missing ------------------------------------------------------------------
def _env(**kw):
    old = {k: os.environ.get(k) for k in kw}
    os.environ.update({k: str(x) for k, x in kw.items()})
    return old


def _restore(old):
    for k, x in old.items():
        if x is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = x


def test_cli_doctor_and_usage():
    assert video_main(["doctor"]) == 0
    assert video_main([str(PROFILE), "doctor"]) == 0
    assert video_main([]) == 2
    assert video_main(["no-such-profile", "info"]) == 2


def test_cli_missing_voice_env_exits_3():
    with tempfile.TemporaryDirectory() as d:
        ref = Path(d) / "ref.wav"
        ref.write_bytes(b"RIFF")
        old = _env(VIRAL_SCOUT_VOICE_PY=str(Path(d) / "nope" / "python.exe"))
        try:
            assert video_main([str(PROFILE), "voice", str(ref), str(Path(d) / "o.wav"), "Hello there."]) == 3
        finally:
            _restore(old)


def test_cli_missing_hyperframes_exits_3():
    if not shutil.which("node"):
        skip("node not installed")
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "film").mkdir()
        old = _env(VIRAL_SCOUT_VIDEO_NODE_MODULES=str(Path(d) / "node_modules"))
        try:
            assert video_main([str(PROFILE), "film", "check", str(Path(d) / "film")]) == 3
        finally:
            _restore(old)


def test_cli_missing_whisperx_exits_3():
    if not shutil.which("ffmpeg"):
        skip("ffmpeg not installed")
    import importlib.util
    if importlib.util.find_spec("whisperx"):
        skip("whisperx is installed here")
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=300:duration=2", str(wav))
        old = _env(VIRAL_SCOUT_VIDEO_PY=str(Path(d) / "nope" / "python.exe"))
        try:
            assert video_main([str(PROFILE), "cut", str(wav), str(SCRIPT), "--section", "1", "--out", d]) == 3
        finally:
            _restore(old)


def test_still_with_brand_colors():
    try:
        from PIL import Image
    except ImportError:
        skip("Pillow not installed")
    from viral_scout.video import still
    v = vset()
    with tempfile.TemporaryDirectory() as d:
        a, b = Path(d) / "a.png", Path(d) / "b.png"
        Image.new("RGB", (1080, 1920), (40, 80, 120)).save(a)
        Image.new("RGB", (600, 300), (120, 80, 40)).save(b)
        out = still.make(v, a, b, "Don't heat with the oven", "Test your alarm", Path(d) / "s.png", "Source: test")
        im = Image.open(out)
        assert im.size == (1080, 1350)
        assert im.getpixel((540, 675)) == settings.hex_rgb(v["colors"]["accent"])    # divider in the accent color


# ---- FFmpeg smoke test: camera mode end to end with a seeded transcript ----------------------------------------------
def _ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-v", "error", *args], check=True)


def test_ffmpeg_camera_cut_and_render():
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        skip("ffmpeg not installed")
    from viral_scout.video import media, pipeline
    v = vset()
    with tempfile.TemporaryDirectory() as d:
        rec = Path(d) / "rec.mp4"
        dur = TAKES[-1]["e"] + 1
        _ffmpeg("-f", "lavfi", "-i", f"testsrc=size=320x180:rate=30:duration={dur}",
                "-f", "lavfi", "-i", f"sine=frequency=220:duration={dur}",
                "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(rec))
        work = Path(d) / "smoke" / "work"
        work.mkdir(parents=True)
        (work / f"words-{rec.stat().st_size}.json").write_text(json.dumps(TAKES), encoding="utf-8")   # no WhisperX
        job = pipeline.cut(v, str(rec), str(SCRIPT), section="1", slug="smoke", out=d)
        edit = json.loads((job / "edit.json").read_text(encoding="utf-8"))
        assert edit["mode"] == "camera" and len(edit["lines"]) == 6 and len(edit["dropped"]) == 1
        assert (job / "edit.draft.json").exists()
        master = pipeline.render(v, job)
        info = media.probe(master)
        assert (info["video"]["width"], info["video"]["height"]) == (1080, 1920)
        assert abs(info["duration"] - edit["duration"]) < 0.5
        assert (job / "smoke.srt").exists() and (job / "cover.png").exists()
        report = (job / "report.md").read_text(encoding="utf-8")
        assert "sorry, let me start again." in report and "python -m viral_scout check" in report


def test_mode_not_allowed():
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        skip("ffmpeg not installed")
    from viral_scout.video import pipeline
    v = dict(vset(), modes=["FILM"])
    with tempfile.TemporaryDirectory() as d:
        wav = Path(d) / "a.wav"
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=300:duration=1", str(wav))
        try:
            pipeline.cut(v, str(wav), str(SCRIPT), section="1", out=d)
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert "VOICE+CARDS" in str(e)


# ---- regressions found re-rendering a real film ---------------------------------------------------------------------
def test_docs_have_no_mangled_paths():
    """A path written through a shell that ate the backslashes ("D:\\repo\\viral-scout" → "D:", CR, "epo", VT,
    "iral-scout") or one that mixes slashes."""
    import re
    for p in [*(ROOT / "docs").glob("*.md"), *(ROOT / ".claude" / "skills").rglob("*.md")]:
        text = p.read_bytes().decode("utf-8").replace("\r\n", "\n")
        bad = re.findall(r"[\x00-\x08\x0b\x0c\x0e-\x1f\r]", text)
        assert not bad, f"{p.name}: control characters {bad!r}"
        assert not re.search(r"[A-Za-z]:/[^\s`]*\\", text), f"{p.name}: a path with mixed slashes"
        assert not re.search(r"\b[A-Z]:\n", text), f"{p.name}: a drive letter followed by a line break"


FILM_SCRIPT = ("Power just went out.\nDo these three things first.\nThen report it to Amperio.\n"
               "Call one eight hundred Amperio one, or use the app.\nAbout forty eight for a full freezer.\n"
               "Save this before you need it.\n")
# Whisper hears the first word of line 2, the last of line 3 and the first of line 6 differently
FILM_HEARD = say("power just went out", "so these three things first", "then report it to imperial",
                 "call 1-800 Amperio 1 or use the app", "about 48 for a full freezer", "Tape this before you need it.")


def _film_lines(d):
    p = Path(d) / "film.txt"
    p.write_text(FILM_SCRIPT, encoding="utf-8")
    return load_script(p)["lines"]


def test_film_words_keep_edge_words_heard_differently():
    from viral_scout.video import film
    with tempfile.TemporaryDirectory() as d:
        lines = _film_lines(d)
    out, rc, heard = film.align(lines, FILM_HEARD, {}, log=lambda m: None)
    assert rc["dropped"] == [] and rc["missing"] == []
    assert [(h["heard"], h["script"]) for h in heard] == [("so", "Do"), ("imperial", "Amperio."), ("Tape", "Save")]
    by_line = {}
    for w in out:
        by_line.setdefault(w["i"], []).append(w["w"])
    assert " ".join(by_line[1]) == "Do these three things first."
    assert by_line[2][-1] == "Amperio."
    assert by_line[5][0] == "Save"
    assert [w["w"] for w in out] == FILM_SCRIPT.split()                      # every script word, the script's text
    so = next(w for w in FILM_HEARD if w["w"] == "so")
    assert next(w for w in out if w["w"] == "Do")["s"] == so["s"]           # the heard word's time


def test_film_words_spelled_numbers_keep_script_form():
    from viral_scout.video import film
    with tempfile.TemporaryDirectory() as d:
        lines = _film_lines(d)
    out, _, _ = film.align(lines, FILM_HEARD, {}, log=lambda m: None)
    span = next(w for w in FILM_HEARD if w["w"] == "1-800")
    nums = [w for w in out if w["w"] in ("one", "eight", "hundred") and w["i"] == 3][:3]
    assert [w["w"] for w in nums] == ["one", "eight", "hundred"]
    assert nums[0]["s"] == span["s"] and nums[-1]["e"] == span["e"]
    assert all(a["e"] <= b["s"] for a, b in zip(nums, nums[1:]))
    assert "forty eight" in " ".join(w["w"] for w in out)
    # the cut's captions keep digits
    timed = [dict(w, line=0) for w in say("about 48 for a full freezer")]
    cut_caps = captions.fix_words([{"text": "About forty eight for a full freezer."}], timed)
    assert [w["w"] for w in cut_caps][1] == "48"


def test_film_words_voice_check_report():
    if not shutil.which("ffmpeg"):
        skip("ffmpeg not installed")
    from viral_scout.video import film
    v = vset()
    with tempfile.TemporaryDirectory() as d:
        fd = Path(d) / "film"
        (fd / "work").mkdir(parents=True)
        wav = Path(d) / "vo.wav"
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=300:duration=2", str(wav))
        (fd / "work" / f"words-{wav.stat().st_size}.json").write_text(json.dumps(FILM_HEARD), encoding="utf-8")
        _film_lines(d)
        assert film.words(v, str(fd), str(wav), str(Path(d) / "film.txt")) == 0
        check = (fd / "voice-check.md").read_text(encoding="utf-8")
        assert "heard differently: so → Do" in check and "heard differently: Tape → Save" in check
        extra = check.split("## Extra speech")[1].split("##")[0]
        assert extra.strip().endswith("- none")
        ws = json.loads((fd / "work-words.json").read_text(encoding="utf-8"))
        assert [w["w"] for w in ws][:6] == ["Power", "just", "went", "out.", "Do", "these"]


def test_render_reextracts_missing_voice_wav():
    if not (shutil.which("ffmpeg") and shutil.which("ffprobe")):
        skip("ffmpeg not installed")
    from viral_scout.video import media, pipeline
    with tempfile.TemporaryDirectory() as d:
        rec, work = Path(d) / "rec.wav", Path(d) / "job" / "work"
        work.mkdir(parents=True)
        _ffmpeg("-f", "lavfi", "-i", "sine=frequency=220:duration=1", "-ar", "44100", str(rec))
        wav = pipeline.voice_wav(work, rec)
        assert wav == work / "voice-48k.wav" and wav.exists()
        assert media.probe(wav)["duration"] > 0.9
        info = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=sample_rate,channels", "-of", "csv=p=0",
                               str(wav)], capture_output=True, text=True).stdout.strip()
        assert info == "48000,1"                                                  # the cut's settings
        wav.unlink()
        rec.unlink()
        try:
            pipeline.voice_wav(work, rec)
            raise AssertionError("expected SystemExit")
        except SystemExit as e:
            assert isinstance(e.code, str) and "voice-48k.wav" in e.code and "rec.wav" in e.code   # exit code 1


def test_cover_fallback_trims_function_words():
    assert plan.cover_words("Most homes lose the heat first.") == "Most homes lose"
    assert plan.cover_words("Power just went out.") == "Power just went out"
    assert plan.cover_words("The") == "The"
    lines = [{"text": "Most people forget to unplug the TV.", "part": "hook", "t0": 0, "t1": 2}]
    assert plan.draft(lines, [])[1]["big"] == "Most people forget"


def test_spelled_digit_runs_are_one_number():
    c = plan.auto_card({"text": "If the power goes out, call nine one one only for emergencies.", "part": "body"})
    assert c["kind"] == "stat" and c["big"] == "911" and not c["small"].startswith("one")
    c = plan.auto_card({"text": "Call one eight hundred and ask for the outage line.", "part": "body"})
    assert c["big"] == "1-800"
    assert plan.auto_card({"text": "Storms left over two million homes in the dark.", "part": "hook"})["big"] == "2 million"
    assert plan.auto_card({"text": "About eight hundred homes lost power.", "part": "body"})["big"] == "8 hundred"


def test_card_brand_label_color():
    v = vset()
    assert cards.values(v)["brand_label_color"] == v["colors"]["accent"]       # default: unchanged output
    with tempfile.TemporaryDirectory() as d:
        page = cards.write_template(dict(v, colors=dict(v["colors"], brand_label="#ffffff")), Path(d)).read_text(
            encoding="utf-8")
    assert "--brand-label:#ffffff" in page and "color: var(--brand-label)" in page
    try:
        cards.values(dict(v, colors=dict(v["colors"], brand_label="white")))
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_cli_transcribe_language_plumbing():
    from viral_scout.video import media, pipeline, transcribe
    seen = []

    def fake_transcribe(wav16, cache, model, log, language):
        seen.append(language)
        return [{"w": "hello", "s": 0.0, "e": 0.4}]

    def fake_extract(src, work):
        return work / "voice-48k.wav", work / "voice-16k.wav"

    old_t, old_x = transcribe.transcribe, media.extract_audio
    transcribe.transcribe, media.extract_audio = fake_transcribe, fake_extract
    try:
        with tempfile.TemporaryDirectory() as d:
            rec = Path(d) / "a.m4a"
            rec.write_bytes(b"x")
            out = str(Path(d) / "a.txt")
            assert video_main([str(PROFILE), "transcribe", str(rec), "--out", out]) == 0
            assert video_main([str(PROFILE), "transcribe", str(rec), "--out", out, "--language", "auto"]) == 0
            assert video_main([str(PROFILE), "transcribe", str(rec), "--out", out, "--language", "pl"]) == 0
            pipeline.transcript(dict(vset(), language="uk"), str(rec), out)
            pipeline.transcript(dict(vset(), language=""), str(rec), out)
            assert Path(out).read_text(encoding="utf-8").strip() == "hello"
    finally:
        transcribe.transcribe, media.extract_audio = old_t, old_x
    assert seen == ["en", "auto", "pl", "uk", "en"]                           # default: video.language, else en
    assert transcribe.whisper_language("auto") is None and transcribe.whisper_language("") is None
    assert transcribe.whisper_language("PL") == "pl"


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted((k, f) for k, f in dict(globals()).items() if k.startswith("test_") and callable(f)):
        try:
            fn()
            print("ok  ", name)
        except Skip as e:
            print("skip", name, e)
        except Exception as e:  # noqa: BLE001
            failed += 1
            print("FAIL", name, repr(e))
    sys.exit(1 if failed else 0)
