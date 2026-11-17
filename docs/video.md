# Video generation

`python -m viral_scout video <profile> ...` turns a recording and a script into a finished vertical video for one business. It also clones the owner's voice, renders animated films with HyperFrames and makes stills. Every brand value (name, colors, fonts, logo, caption spelling, voice, folders) comes from the profile. The `/studio-video` skill drives it: script, edit, film, week plan, review, repurpose and the compliance step.

It is the generic version of the `tools/video` scripts a project repo used to carry (moving one over: [below](#moving-a-repo-from-its-own-toolsvideo)). The method behind it is the vault playbook `shared/playbooks/05 Marketing/video-generation.md`.

## What it does

```
recording (voice .wav/.m4a/.mp3, or a phone video) + script (.md)
  → WhisperX word timings (GPU large-v3, CPU small fallback)
  → rough cut: the best take of every script line; flubs, retakes and "uh" dropped (the last good take wins)
  → pauses tightened by word timings (> 0.30 s → 0.12 s), so captions stay frame-exact
  → caption words fixed against the script (spelling, case), then the profile's vocabulary; numbers kept as digits
  → word-highlight captions (accent color, 1-3 words per screen, above the bottom 20%)
  → audio: high-pass, FFT denoise, gentle compression, loudnorm -14 LUFS, limiter
  → picture: camera mode = your footage cropped 9:16; voice mode = brand cards with a slow push-in (+ B-roll)
  → <slug>.mp4 (1080×1920, 30 fps, H.264 + AAC 48 kHz), <slug>.srt, cover.png, edit.json, report.md
```

Then `python -m viral_scout check <profile> <slug>.mp4` runs the pre-publish check on the master.

Modes, as the playbook names them:

| Mode | What it is | Command |
|---|---|---|
| REAL | the owner on camera | `cut` / `make` with a video file (camera mode) |
| VOICE+CARDS | voice + static brand cards. A draft or timing check, not a post | `cut` / `make` with an audio file (voice mode) |
| FILM | an animated HyperFrames film, the voice is the clock | `film words`, `film check`, `film render` |
| TWIN | a paid avatar service | not run by this tool |

`video.modes` in the profile lists the modes a business allows. The tool refuses the others.

## Install

Research-only users need none of this. Everything below is optional and lives outside the main install.

| Part | For | Install |
|---|---|---|
| FFmpeg with libass | everything | `choco install ffmpeg` (Windows), on PATH |
| `.venv-video` (Python 3.11, WhisperX, CUDA torch 2.8) | `cut`, `make`, `transcribe`, `film words` | `pwsh scripts/setup-video.ps1` |
| `viral_scout/video/node` (Playwright, HyperFrames, Chromium) | cards, voice-mode `render`, `film check/render` | `pwsh scripts/setup-video.ps1 -Node` (Node.js 22+) |
| `.venv-voice` (Python 3.11, Chatterbox, CUDA torch 2.6) | `voice` | `pwsh scripts/setup-video.ps1 -Voice` |
| Pillow | `still` | `pip install pillow` in the Python that runs viral_scout |

`-All` does the three, `-Check` prints the plan and installs nothing, `-Cpu` skips the CUDA builds. The first transcription downloads the Whisper model (about 3 GB for large-v3).

WhisperX and Chatterbox need separate envs: Chatterbox pins torch 2.6 and numpy 1.26, WhisperX needs torch 2.8 and numpy 2. The main CLI calls them through a subprocess, so it keeps running on any Python 3.10+.

Already have the tools elsewhere? Point at them instead of installing again:

```
VIRAL_SCOUT_VIDEO_PY=D:/repo/<your-site>/tools/video/.venv/Scripts/python.exe
VIRAL_SCOUT_VOICE_PY=D:/repo/<your-site>/tools/video/.venv-clone/Scripts/python.exe
VIRAL_SCOUT_VIDEO_NODE_MODULES=D:/repo/<your-site>/tools/video/node_modules
```

These can go in `.env`. While they point at a business's install, that install is what every video command and the film job run on: don't delete or move those folders (the venvs, `node_modules`, fonts, films) until `setup-video.ps1 -All` has run here and `video doctor` passes without the env vars. HyperFrames' own Claude skills then come from `$VIRAL_SCOUT_VIDEO_NODE_MODULES/hyperframes/dist/skills/`, not from `viral_scout/video/node/node_modules/`.

`python -m viral_scout video doctor` lists what is installed (`--deep` also reports CUDA). A command that needs a missing tool exits with code 3 and says how to install it.

## Profile blocks

Two blocks in `profiles/<name>.yaml`. `${ENV}` is expanded everywhere, so `${OBSIDIAN_VAULT}` works in nested paths. Relative paths are read from the profile's folder. Brand files (logo, fonts, voice samples) stay outside git, for example under `D:/Videos/<project>/brand/` or in a git-ignored `brands/` folder.

### `studio:` (shared by every studio skill)

| Field | What |
|---|---|
| `brand` | the business name shown on cards and stills |
| `vault_dir` | the project's root in the vault, e.g. `${OBSIDIAN_VAULT}/projects/mysolar` |
| `instructions` | a vault note with free text for this business: voice, offer, pillars, CTA keyword, banned words. Overrides the skill's defaults, never its hard rules |
| `compliance` | the vault note with the industry rules and the disclosure line |
| `cta` | `{text, link}`: the default call to action |

### `video:`

| Field | Default | What |
|---|---|---|
| `owner` | `""` | fills `[NAME]` in scripts and the AI label line |
| `language` | `en` | Whisper language code, or `auto` to let WhisperX detect it |
| `modes` | `[REAL, FILM, VOICE+CARDS]` | allowed modes; add `TWIN` only if the business uses an avatar service |
| `script_dir` | | where the skill writes scripts; `cut` also looks for a script file name here |
| `footage_dir` | | recordings, voice samples, B-roll (outside the vault and git) |
| `output_dir` | `<footage_dir>/out`, else `data/video/<profile>` | one folder per video (`<slug>/`) |
| `films_dir` | `<footage_dir>/films` | HyperFrames film folders; `film` commands take a name from here |
| `music_dir` | | the owner's own licensed tracks; `--music` takes a file name from here (see [Music](#music)) |
| `whisper_model` | large-v3 on GPU, small on CPU | |
| `voice` | `{reference, cfg: 0.5, exaggeration: 0.5, seed: 1, pause: 0.25}` | the owner's 8-12 s reference wav and the Chatterbox knobs |
| `brand_label` | `studio.brand` in capitals | the small label on top of each card |
| `logo` | a glowing dot | PNG or SVG next to the label |
| `card_template` | `viral_scout/video/node/card.html` | your own card page; keep the placeholders and `window.CARD` |
| `colors` | night blue + warm yellow | `bg`, `bg_deep`, `bg_light`, `accent`, `text`, `muted`, `caption`, `caption_outline` (hex); optional `brand_label`: the label's color on the cards (default: `accent`) |
| `fonts` | Segoe UI | `display`, `body`, `caption` (installed font names), `files` (`[{family, path, weight}]` loaded into the cards), `still_bold`, `still_regular` (.ttf for stills) |
| `vocabulary` | none | caption fixes: `{regex: text}` (case-insensitive), or a list of words to keep as written |
| `stat_units` | none | extra units that make a number a stat card (`kwh`, `homes?`) |
| `cta_card` | `{big: studio.cta.text, pill: "Link in bio", triggers: [link, comment, dm, check]}` | the auto-drafted CTA card; a CTA line with a trigger word gets it |
| `ai_label` | `AI voice of me, script written by me. -{owner}` | first caption line when the voice or a realistic visual is AI |
| `formats` | none | formats the owner marked as good references: `[{name, mode, tool, guide, references: [swipe notes], structure, topics, length}]`. `/studio-video` reads them (and their swipe notes) before `script` and `film`. See [3D cutaway films](#3d-cutaway-films) |

Example (solar):

```yaml
studio:
  brand: "Bright Solar"
  vault_dir: ${OBSIDIAN_VAULT}/projects/mysolar
  instructions: ${OBSIDIAN_VAULT}/projects/mysolar/05 Marketing/studio-instructions.md
  compliance: ${OBSIDIAN_VAULT}/projects/mysolar/07 Jurisdiction/2026-10-20-compliance-checklist.md
  cta: {text: "Free Backup Power Check", link: "https://solar.example.com/links"}
video:
  owner: Alex
  modes: [REAL, FILM, VOICE+CARDS]
  script_dir: ${OBSIDIAN_VAULT}/projects/mysolar/05 Marketing/Video Studio/scripts
  footage_dir: D:/Videos/bright-solar
  voice: {reference: D:/Videos/bright-solar/voice/work/refB.wav, cfg: 0.5, exaggeration: 0.6}
  colors: {bg: "#0b1124", bg_deep: "#070b16", bg_light: "#121a33", accent: "#ffc45c", text: "#fbfaf7", muted: "#9aa3c0"}
  fonts: {still_bold: D:/Videos/bright-solar/brand/bricolage-800.ttf, still_regular: D:/Videos/bright-solar/brand/bricolage-600.ttf}
  vocabulary:
    '\bcity ?power\b': CityPower
    '\bstate ?power\b': StatePower
    '\bkwh\b|\bk w h\b': kWh
    '\bkw\b': kW
    '\bpowerwall\b': Powerwall
    '\bgenerac\b': Generac
    '\benphase\b': Enphase
  stat_units: [kwh, kw, "homes?", "outages?"]
```

`python -m viral_scout video <profile> info` prints the resolved settings.

## Commands

```
python -m viral_scout video doctor [--deep]
python -m viral_scout video <profile> info
python -m viral_scout video <profile> cut <media> <script.md> [--section N] [--slug S] [--broll DIR] [--name X] [--mode auto|voice|camera] [--model M] [--out DIR]
python -m viral_scout video <profile> make <media> <script.md> ... [--music FILE]          cut + render
python -m viral_scout video <profile> cards <job>                                           preview the card PNGs
python -m viral_scout video <profile> render <job> [--music FILE]
python -m viral_scout video <profile> transcribe <media> [--out FILE.txt] [--language CODE|auto]   default: video.language, else en; auto = WhisperX detects it
python -m viral_scout video <profile> voice <ref.wav|profile> <out.wav> <text|script.md|file.txt> [--section N] [--cfg 0.5 0.3] [--exaggeration 0.6] [--seed 1]
python -m viral_scout video <profile> film new <name> --from <reference film>
python -m viral_scout video <profile> film words <film> <voice.wav> <script.md> [--section N]
python -m viral_scout video <profile> film check <film>
python -m viral_scout video <profile> film render <film> [--out FILE] [--quality delivery]
python -m viral_scout video <profile> still --top a.png --bottom b.png --top-text "DON'T ..." --bottom-text "DO ..." --out still.png [--source "Source: CDC"]
```

### Music

No music in the master. Music from a platform's library is added by the owner in the app when posting, where the license covers it. The one exception is `--music`, which is off by default: only for a track the owner made or licensed for this use (mixed −20 dB under the voice), never a download from the web or another creator's post.

`<job>` is a folder in `output_dir` (or any path). `<film>` is a folder in `films_dir` (or any path). `<profile>` can also be a path to a YAML file.

### The cut, step by step

1. `cut` writes `<output_dir>/<slug>/edit.json` and keeps the auto draft as `edit.draft.json`. Every script line should print ✓. A ✗ line is not in the recording.
2. Read `dropped` in edit.json (also in report.md). With an AI voice nothing should be dropped.
3. Edit the cards in edit.json: `visuals[].card` is `{kind: stat|headline|list|cta, kicker, big, small, items[], pill, source}`; `*word*` in `big` is highlighted. Or set `broll: <path>` instead of a card. `cover.big` is the cover text (≤ 4 words). Fix caption typos in `words[].w`, never the times.
4. `cards` renders only the card PNGs to `work/cards/` for a look. `render` builds the master. A stat card with `source: "ADD SOURCE"` prints a warning and must not be posted. If `work/voice-48k.wav` was deleted, `render` extracts it again from `recording` in edit.json; when that file is gone too it stops with exit code 1 and names both paths.

The auto draft reads a number spoken digit by digit as one number ("nine one one" → `911`, "one eight hundred" → `1-800`). The fallback cover (a hook without a number) is its first 4 words, minus a trailing function word ("the", "of", "to", "and").

### Script files

The format the skill writes and `cut` reads (one script per `### N. Title` section):

```markdown
### 1. Storm night
**Hook:** "Last year storms left over two million homes in the dark."
**Body:** "I'm [NAME]. The test is on the seventeenth."
**CTA:** "Comment BACKUP and I'll send you the link."
```

The quoted text after **Hook**, **Body**, **CTA** (also `Line N`, `Close`, `Outro`) is spoken. One sentence is one line for the cut and the cards. A file without these labels is plain text: every line that isn't a heading is spoken. `--section 1` picks `### 1. ...`; `--section storm` picks the first heading that contains "storm".

### Number matching

Scripts for an AI voice spell numbers out ("seventeenth", "nine one one"); Whisper writes digits ("17th", "911"). The cut maps both to digits (0-20, 30, 40, 50, 100 and the ordinals to 20th and 30th) and splits "911" into one digit per word. Other spelled-out numbers ("forty eight") still mismatch. Mid-line that is harmless, but at the edge of a line the word can be trimmed off, so check `dropped`. English number words only.

### Films

A film folder holds `SPEC.md`, `index.html`, `compositions/`, `assets/` and `REVIEW.md` (see the playbook §8 and HyperFrames' own skills in `<node_modules>/hyperframes/dist/skills/`, where `<node_modules>` is `$VIRAL_SCOUT_VIDEO_NODE_MODULES` when set, else `viral_scout/video/node/node_modules`).

- `film new <name> --from <reference>` starts a film from a reference film: it copies the folder into `films_dir/<name>` (or to a path) with its code, fonts, sound effects and their credits, and leaves out `out/`, `work/`, `.hyperframes/`, `assets/voice/` contents, `work-words.json`, `voice-check.md`, `REVIEW.md`, `POST.md` and `still.png`. An existing folder is never overwritten. This is how an unattended job gets binary assets it can't write itself.

- `film words` transcribes the voice, aligns it to the script, writes `work-words.json` (`[{w, s, e, i}]`, `i` = script sentence, `w` exactly as in the script) and `voice-check.md`: missing sentences, extra speech (repeats like "two two"), and words longer than 0.8 s, which can hide a repeat the aligner merged. Exit code 1 when it finds any. A first or last word of a sentence that Whisper heard as another word ("Do" as "so", "Save" as "Tape") is kept with the script's text and listed as `heard differently: so → Do`, not as extra speech; listen to those spots. Spelled numbers keep the script's words ("one eight hundred", not "1-800") with the heard word's time shared among them.
- `film check` runs `hyperframes check` (lint, runtime, layout, contrast).
- `film render` renders to `<film>/out/<name>-film.mp4` and reports loudness against about -14 LUFS and -1 dBTP. It changes nothing. A ⚠ line → change the voice and sound effect levels in the composition and render again; as a last resort normalize the audio only (`ffmpeg -i in.mp4 -c:v copy -af loudnorm=I=-14:TP=-1:LRA=11 out.mp4`) and run `check` again.

### 3D cutaway films

An animated 3D explainer of one job: the camera goes where a phone can't (inside the wall, behind the siding). One part lights up at a time, force arrows show where the weight or water goes, pointer labels name the parts, red is wrong and green is right, and 2-3 caption words at a time sit on dark plates. Proven on TikTok by home-improvement and "how to operate X" channels. It suits home services: a danger hook, then the job done right, then a check the homeowner can do from outside, then "get it checked" as the CTA.

**Save a reference.** `python -m viral_scout save <profile> <url> --note "GOOD REFERENCE (format): …"` stores the post in the database, tracks it and writes a swipe note. Set `format: "3D cutaway explainer"` in the note and add the tags `reference` and `format/3d-cutaway`. Then list the note under the profile's `video.formats[].references`. To study it frame by frame: `python -m yt_dlp <url>` from `$VIRAL_SCOUT_YTDLP`, `video <profile> transcribe <mp4>`, and a contact sheet (`ffmpeg -i in.mp4 -vf "fps=1/4,scale=360:-1,tile=4x2" sheet%02d.png`).

**Build it** as a normal film (`/studio-video <profile> film`), with the 3D scenes in Three.js inside the HyperFrames composition:

- The method: the hyperframes skill's `references/types/3d.md` (deterministic frames, one hero object, cutaways and exploded views, light and materials) and `references/runtimes.md` (render from `e.detail.time` in an `hf-seek` listener; heavy setup registers `window.__hf.buildReady`).
- Models: build them from primitives (boards, joists, screws, anchors, gutters are boxes and cylinders). Textures and HDRIs: CC0 only (ambientCG, Poly Haven), credited in `assets/CREDITS.md` like the sound effects. Never the reference's models, voice, music or words: only the format.
- Shots: SHOTS in `SPEC.md` keyed to the voice's words. One step = one visible action. Labels carry real numbers only with a source tag (code section, manufacturer's table).
- Length: 45-75 s. The references run 2-3 min, but a first film is easier to review short.
- The first one is built live with the owner and becomes the quality bar; later films start with `film new <name> --from <that film>`.
- Check like any film: `film check`, snapshots of the dive and the payoff, `film render`. A heavy frame slows every render, so profile the heaviest moment once.

## Triggering it from another repo

Project repos don't copy the tool. They call it:

- **From Claude Code:** `/studio-video <profile> script "<topic>"`, `/studio-video <profile> edit <recording>`, `/studio-video <profile> film <idea>`. The skill lives in this repo at `.claude/skills/studio-video/`; junction it into `~/.claude/skills/` the way `/viral-scout` is (the Obsidian rollout repo owns those junctions) so every repo sees it. A repo can override it with its own `.claude/skills/studio-video/`.
- **From a script or a scheduled job:**
  ```powershell
  $env:PYTHONIOENCODING = "utf-8"
  python -m viral_scout video <profile> make "D:\Videos\<project>\2026-11-15-rec.m4a" "<script.md>" --section 1
  ```
  with the viral-scout repo as the working directory (`Push-Location "<path to viral-scout>"`). Exit codes: 0 done, 1 a step failed (message on stderr), 2 bad arguments or profile, 3 an optional tool is missing.
- **Outputs** land in the profile's `output_dir`, never in the calling repo. Read `report.md` and `edit.json` there.

## Moving a repo from its own tools/video

A project repo that grew its own video scripts (a `tools/video` folder, per-repo video skills) can hand them over to this tool. The steps, in order:

1. Add the `studio:` and `video:` blocks to `profiles/<profile>.yaml` (the example above). Check the voice reference, font and logo paths.
2. Copy the brand files (fonts, logo) from `tools/video/assets/` to a folder outside git, e.g. `D:/Videos/<project>/brand/`, and point `video.fonts` and `video.logo` at them. For the cards, add the fonts to `video.fonts.files` and set `display`.
3. Reuse the existing installs instead of downloading them again: `VIRAL_SCOUT_VIDEO_PY`, `VIRAL_SCOUT_VOICE_PY` and `VIRAL_SCOUT_VIDEO_NODE_MODULES` in viral-scout's `.env` (see [Install](#install)). Or run `scripts/setup-video.ps1 -All`. Then `python -m viral_scout video <profile> doctor`.
4. **Acceptance test: re-render something the old tool made.** Run one old recording through `make` (and one old film through `film words`) and compare with the old output: the same takes, the same `dropped`, the same caption words and times in `edit.json` / `work-words.json`. Captions identical to the old tool's are the bar; any difference is either a bug here or a fix you can name. Don't move on until it passes.
5. Point `video.films_dir` at the film folders, or move them there (they are brand content, so they stay out of this repo), and run `film check` on one.
6. Replace the repo's video skills (script, edit, review, week plan, repurpose, compliance) with `/studio-video <profile> ...` triggers. Move their business-only text (program rules, vocabulary, the CTA keyword, carousel and blog paths) into the note named by `studio.instructions`, the compliance note and `video.vocabulary`.
7. Update any unattended job that called `tools/video` to call `python -m viral_scout video <profile> ...`.
8. Once a week of videos has gone through the new path, delete `tools/video` from that repo (keep the films and recordings). Folders the `VIRAL_SCOUT_*` env vars still point at stay until this repo has its own installs and `video doctor` passes without the env vars.

## Limits

- The cut and the card drafts assume English (number words, stop words). Other languages transcribe and cut, but check `dropped`.
- Voice clone and WhisperX on CPU work but are slow.
- The tool never posts, uploads or calls paid services. TWIN mode is a decision for the skill and the owner, not a command here.
