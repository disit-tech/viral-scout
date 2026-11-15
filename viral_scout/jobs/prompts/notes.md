## Job: {{owner}}'s notes and replies → new versions

`{{notes}} list` shows the new notes. What each one answers is under "↪ about"; voice/photo files are downloaded (path after 📎). Transcribe voice notes first (WhisperX, or the `/studio-video` skill's transcribe step; let it detect the language).

For each note:
- **Changes to a script** ("about" is a script for idea #N): rewrite the script (rules of the script job: sources, compliance), update the vault file, send the new version with `{{ideas}} script N <file>`, then `{{notes}} done <id> "new script version sent"`.
- **Changes to a video draft** (about a video sent for review): apply them in the film folder (see its REVIEW.md) with the `/studio-video` skill and `{{video}} …`, re-render, check loudness and a few frames, send it with `{{notes}} send <mp4> "<what changed>" --reply <id>`, then `done`.
- **Changes to a blog draft**: edit the draft (keep it a draft), re-check compliance, send the new version for review (`{{ideas}} blog <slug> "<title>" <summary-file>`), then `done`.
- **Anything else you can do safely here** (vault notes, research, ideas, scripts, video work): do it, then `done` with a one-line result.
- **Not unattended** (see "Never" below): answer `{{notes}} skip <id> "needs a live session: …"` and add it to the daily note.

Films are not made here: the film job does that.
