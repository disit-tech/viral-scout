## Job: one finished film per day

{{per_day}} film(s) per post date (posting times {{times}}). {{approval_intro}} Quality bar and look: the reference film named in the business rules below. Static text cards with captions are not a film: every film moves (camera, transitions, events timed to the words, sound).

### 0. Is a film needed?
Read the queue `{{queue}}` (`{{publish}} plan --days 14` prints it with the free dates). If {{buffer}} or more films are queued for future dates and not posted, stop: the buffer is full. Otherwise the new film gets the first free date from tomorrow on (a date is free until it holds {{per_day}} films). Two films on one date must differ in topic and format.

### 1. Topic (first match wins)
1. `{{ideas}} pull`: an idea with stage `script_ok`, then one with stage `script` (its script is in `<vault>/05 Marketing/Video Studio/scripts/*-idea<ID>.md`). Run `{{ideas}} stage <ID> making`.
2. The tracker `<vault>/05 Marketing/Video Studio/video-tracker.md`: the first ✍️ scripted row whose mode is not REAL (REAL = the owner on camera: never animate those) and has no film yet.
3. Otherwise write a new script from the freshest material (viral-scout notes in `<vault>`, the best-scored idea). It must fit the date and must not repeat a topic already tracked or queued.

Whatever the source: read {{perf_report}} first. Copy what the best of our own posted films did (hook type, length, format) and avoid what the weakest did; note in the script which one you learned from.

### 2. Script and facts
- Length 35–60 s, hook in the first 2 s, one CTA (the link above with `utm_source=<platform>&utm_campaign=<slug>`, or the comment keyword).
- Re-verify every number and claim today on the official source (WebSearch/WebFetch). A claim you cannot verify today is cut, not guessed. Every number gets its source on screen. Spoken numbers as words.
- Compliance check; fix everything it flags. Save the script note `<vault>/05 Marketing/Video Studio/scripts/{{today}}-<slug>.md` with a verified-facts block (fact, URL, date checked) and a compliance block.

### 3. Build the film
Follow the `/studio-video` skill, mode `film`, and read the shared notes it lists for films first (the film pipeline playbook and the craft lessons). Start with `{{video}} doctor` (tools, voice, GPU). Create the film folder with `{{video}} film new <slug> --from <reference film>`: it copies the reference's code, fonts and sound effects (binary files you can't write yourself) and leaves out its renders, voice and review. Then the voice, the film and the render with `{{video}} …`.
1. **Voice check:** a cloned voice can repeat a word, and captions hide it. Transcribe the voice, compare word by word with the script, and flag any single word longer than about 0.8 s. Regenerate that line or mute the extra word; transcribe again until it matches.
2. Captions from the script text, timed to the words, readable on a phone: `{{video}} film captions <slug>` writes `compositions/captions.html` from `work-words.json`, in the reference film's caption look. Spelled numbers back to digits ("three hundred" → "300") and word fixes go in the film's `captions.json` (`merge`, `fix`; docs/video.md#films). Run it again after every `film words`. Never run a film folder's own script (`make_captions.py` and the like): it is refused.
3. Loudness about −14 LUFS, true peak ≤ −1 dBTP, background under the voice. `film render` only reports it: a ⚠ line → change the voice and sound effect levels in the composition and render again. Last resort, the audio only (when the business rules allow ffmpeg): `ffmpeg -i <in.mp4> -c:v copy -af loudnorm=I=-14:TP=-1:LRA=11 <out.mp4>`. Then `{{check}} <mp4>` on the master.
4. Review like a viewer, at least 2 rounds (contact sheet every 2–3 s plus a frame at every scene change), written in the film's REVIEW.md. Fix: nothing moving for > 2 s, unreadable text, overlaps, captions over the action, a number without a source, glitches at cuts, an ending that is not the CTA.
5. Transcribe the final mp4 once more (`{{video}} transcribe <mp4> --out <film>/out/<slug>-final.txt`): it must say exactly the script. A transcript is redone when the media is newer than its `.json`; add `--force` to redo it anyway.

### 4. Deliver
1. Posting pack `POST.md` in the film folder: one "▶ PLATFORM (format · goal)" block per platform in {{platforms}}, each with its OWN text (not one caption pasted everywhere), how to post, the AI label line when the voice or picture is AI, and the UTM link for that platform. `{{publish}} today` sends it to {{owner}} on the post date.
2. The "Don't / Do" still when the topic has an honest pair, made as the `/studio-video` film mode says (a ❌ and a ✅ frame from the render, cropped between the film's heading and its captions, labels of 3-5 words that match each picture, a short source tag; `{{video}} still …` → `still.png` in the film folder). Read the PNG before sending. No honest pair: skip it.
3. Caption file `caption.md` in the film folder for the posting job (format: docs/publish-and-jobs.md#caption-file): `ai: true` when the voice or picture is AI, `title:` for YouTube, then `## Instagram`, `## Facebook`, `## YouTube`, `## LinkedIn`, `## Threads`, `## TikTok` sections (Threads: ≤ 450 characters, conversational, the link to the film is added for you) (TikTok: the owner pastes it into the draft, so ready to paste, ≤ 2200 characters, 3-5 hashtags), each its own text with that platform's UTM link (LinkedIn: plain professional tone, no hashtag wall, at most 3 hashtags). If the CTA is a comment keyword, add the header lines `challenge: <KEYWORD>` and `reward: <url of what they get>` (comment challenges: {{challenges}}). Check it with `{{publish}} plan` (the post command itself is not yours).
4. Queue row in `{{queue}}`: `| <post date> | <title> | `<full mp4 path>` | <script link> | {{queue_status}} |`. Tracker row → 🎬 film rendered <MM-DD>, the full mp4 path and the post date.
5. Delivery: `{{notes}} send <mp4> "🎬 Video for <date>: <title>. {{review_line}}" --tags "film idea<ID>"` (leave out `idea<ID>` when it didn't come from an idea; the business tag is added for you). If it came from an idea: `{{ideas}} stage <ID> draft --draft <mp4 path>`.
6. Last step, only if the film was delivered: write the slug into `{{done_file}}`.

If something fails: write what broke in the daily note, put an idea back with `{{ideas}} stage <ID> script_ok`, and do not write the .done file (the next hourly run retries, at most {{max_tries}} runs a day).
