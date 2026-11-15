"""`python -m viral_scout video ...`: the video commands. Hooked into viral_scout/__main__.py by register() + dispatch().

  video doctor                                       which optional tools are installed (also: video <profile> doctor)
  video <profile> info                               the resolved studio: + video: settings
  video <profile> cut <media> <script.md> [--section N] [--slug S] [--broll DIR] [--name X] [--mode auto|voice|camera]
  video <profile> make <media> <script.md> ...      cut + render in one go (--music FILE)
  video <profile> cards <job dir>                    render only the cards (preview the PNGs before the full render)
  video <profile> render <job dir> [--music FILE]    build the master from <job>/edit.json
  video <profile> transcribe <media> [--out FILE.txt] [--language CODE|auto]   plain transcript (+ word times .json)
  video <profile> voice <ref.wav|profile> <out.wav> <text|script.md|file.txt> [--cfg 0.5 0.3] [--exaggeration 0.5]
  video <profile> film new <name> --from <reference film>   a new film folder seeded from a reference film
  video <profile> film words|check|render <film dir> ...
  video <profile> still --top a.png --bottom b.png --top-text ... --bottom-text ... --out still.png [--source ...]
Missing optional tools exit with code 3 and a message saying how to install them.
"""
import argparse
import json
import sys
from pathlib import Path

USAGE = __doc__.split("\n\n", 1)[1]


def register(subparsers) -> None:
    """Adds `video` to the main CLI. Everything after `video` is parsed here, by dispatch()."""
    p = subparsers.add_parser("video", help="video generation: cut, cards, render, voice, film, still, doctor",
                              add_help=False, prefix_chars="\x01")
    p.add_argument("video_args", nargs="*")   # with prefix_chars, "--section" etc. stay plain words here


def dispatch(args) -> int:
    return main(list(getattr(args, "video_args", None) or []))


def _parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="python -m viral_scout video <profile>", description=USAGE,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="action", required=True)
    sub.add_parser("doctor").add_argument("--deep", action="store_true", help="also import torch to report CUDA")
    sub.add_parser("info")
    for name in ("make", "cut"):
        c = sub.add_parser(name)
        c.add_argument("media", help="voice recording (.wav .m4a .mp3) or a phone video")
        c.add_argument("script", help="script .md (a /studio-video script or a content plan) or plain .txt")
        c.add_argument("--section", help="script number or heading text, e.g. 1 for '### 1. Intro'")
        c.add_argument("--name", help="replaces [NAME] in the script (default: video.owner)")
        c.add_argument("--broll", help="folder of B-roll clips to mix in (voice mode)")
        c.add_argument("--mode", choices=["auto", "voice", "camera"], default="auto")
        c.add_argument("--model", help="Whisper model (default large-v3 on GPU, small on CPU)")
        c.add_argument("--slug")
        c.add_argument("--out", help="output base folder (default video.output_dir)")
        if name == "make":
            c.add_argument("--music", help="commercial-library music file, mixed −20 dB under the voice")
    c = sub.add_parser("cards")
    c.add_argument("job")
    r = sub.add_parser("render")
    r.add_argument("job")
    r.add_argument("--music")
    tr = sub.add_parser("transcribe")
    tr.add_argument("media")
    tr.add_argument("--out", help="transcript .txt (default: <media>.txt)")
    tr.add_argument("--model")
    tr.add_argument("--language", help="language code (en, pl, uk...) or auto to detect it (default: video.language, else en)")
    vo = sub.add_parser("voice")
    vo.add_argument("reference", help="reference .wav, or `profile` for video.voice.reference")
    vo.add_argument("out")
    vo.add_argument("text", help="the text, a .txt file, or a script .md (its spoken lines)")
    vo.add_argument("--section")
    vo.add_argument("--cfg", type=float, nargs="+")
    vo.add_argument("--exaggeration", type=float)
    vo.add_argument("--seed", type=int)
    vo.add_argument("--pause", type=float)
    f = sub.add_parser("film")
    fs = f.add_subparsers(dest="film_action", required=True)
    fn = fs.add_parser("new")
    fn.add_argument("name", help="new film folder name (in video.films_dir) or a path")
    fn.add_argument("--from", dest="reference", required=True, help="reference film folder to copy")
    fw = fs.add_parser("words")
    fw.add_argument("dir")
    fw.add_argument("voice")
    fw.add_argument("script")
    fw.add_argument("--section")
    fw.add_argument("--model")
    fc = fs.add_parser("check")
    fc.add_argument("dir")
    fr = fs.add_parser("render")
    fr.add_argument("dir")
    fr.add_argument("--out")
    fr.add_argument("--quality", default="delivery", choices=["draft", "standard", "high", "delivery"])
    st = sub.add_parser("still")
    st.add_argument("--top", required=True)
    st.add_argument("--bottom", required=True)
    st.add_argument("--top-text", required=True)
    st.add_argument("--bottom-text", required=True)
    st.add_argument("--source", default="")
    st.add_argument("--brand", help="label bottom right (default: studio.brand; \"\" for none)")
    st.add_argument("--top-y", type=float, default=0.45)
    st.add_argument("--bottom-y", type=float, default=0.45)
    st.add_argument("--out", required=True)
    return ap


def _doctor(v, deep) -> int:
    from . import deps
    for item, ok, detail in deps.report(v, deep):
        print(f"{'✓' if ok else '✗'} {item}: {detail}")
    print("Research-only use needs none of these. Install: docs/video.md#install")
    return 0


def _job(v, job: str) -> Path:
    p = Path(job)
    if not p.exists() and (v["output_dir"] / job).exists():
        p = v["output_dir"] / job
    return p.resolve()


def main(argv: list[str]) -> int:
    from .deps import MissingDependency
    if not argv or argv[0] in ("-h", "--help", "help"):
        print("usage:\n" + USAGE)
        return 0 if argv else 2
    if argv[0] == "doctor":
        return _doctor(None, "--deep" in argv)
    profile, rest = argv[0], argv[1:]
    if not rest:
        print("usage:\n" + USAGE)
        return 2
    try:
        a = _parser().parse_args(rest)
    except SystemExit as e:
        return int(e.code or 0)
    try:
        from . import settings
        try:
            v = settings.load(profile)
        except FileNotFoundError:
            print(f"error: no such profile: {profile} (python -m viral_scout profiles)", file=sys.stderr)
            return 2
        if a.action == "doctor":
            return _doctor(v, a.deep)
        if a.action == "info":
            print(json.dumps(v, indent=1, default=str, ensure_ascii=False))
            return 0
        if a.action in ("cut", "make"):
            from . import pipeline
            job = pipeline.cut(v, a.media, a.script, a.section, a.name, a.broll, a.mode, a.model, a.slug, a.out)
            if a.action == "make":
                pipeline.render(v, job, a.music)
            return 0
        if a.action == "cards":
            from . import pipeline
            for p in pipeline.render_cards(v, _job(v, a.job)):
                print("card", p)
            return 0
        if a.action == "render":
            from . import pipeline
            pipeline.render(v, _job(v, a.job), a.music)
            return 0
        if a.action == "transcribe":
            from . import pipeline
            print(pipeline.transcript(v, a.media, a.out, a.model, a.language))
            return 0
        if a.action == "voice":
            from . import voice
            return voice.clone(v, a.reference, a.out, a.text, a.cfg, a.exaggeration, a.seed, a.pause, a.section)
        if a.action == "film":
            from . import film
            if not settings.allowed(v, "FILM"):
                print(f"error: mode FILM is not in this profile's video.modes ({', '.join(v['modes'])})", file=sys.stderr)
                return 2
            if a.film_action == "new":
                return film.new(v, a.name, a.reference)
            if a.film_action == "words":
                return film.words(v, a.dir, a.voice, a.script, a.section, a.model)
            if a.film_action == "check":
                return film.check(v, a.dir)
            return film.render(v, a.dir, a.out, a.quality)
        if a.action == "still":
            from . import still
            print(still.make(v, a.top, a.bottom, a.top_text, a.bottom_text, a.out, a.source, a.brand, a.top_y, a.bottom_y))
            return 0
    except MissingDependency as e:
        print(e.message, file=sys.stderr)
        return e.code
    return 2
