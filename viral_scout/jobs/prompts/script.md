## Job: one video script for an approved idea

1. `{{ideas}} pull` → every idea (JSON).
2. If any idea has stage `script`, `script_ok` or `making` → stop, do nothing (one in flight at a time).
3. Pick the idea: status `approved` or `tracked`, no stage, highest score, then newest. None → stop quietly.
4. Write the script with the `/studio-video` skill, mode `script` (it lists the shared method notes to read first: the video playbook §3-§4, the craft lessons, platform approaches). Format: Hook / Body / CTA as quoted spoken lines, on-screen cards, B-roll, captions per platform, sources. Use the idea's comments and reason tags. Every number needs a source; mark anything unverifiable [VERIFY]. Mode and voice as the business rules say; an AI voice or avatar means an AI label on every platform.
5. Compliance check (see above); fix what it flags.
6. Save it as `<vault>/05 Marketing/Video Studio/scripts/{{today}}-idea<ID>.md` (frontmatter: type: video-script, idea: <ID>, status: waiting-approval).
7. Send the review version (≤ 3000 characters, plain text): `{{ideas}} script <ID> <file>` (stage → script). Delivery off → leave it in the vault only.
8. Add it to `<vault>/05 Marketing/Video Studio/video-tracker.md` (✍️ scripted, link) and one line to the daily note.
