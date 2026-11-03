# Marketing workflow

How to use viral-scout as a weekly habit for short-form video, whether you're a solo founder or a small team.

## The loop

```
 every morning (scheduled)          weekly (30 min)                 per video
┌───────────────────────────┐   ┌────────────────────────────┐   ┌──────────────────────────┐
│ run → report              │   │ read ideas note            │   │ swipe note: status idea  │
│ /viral-scout analyze      │──▶│ save 2–3 references        │──▶│ → scripted → filmed      │
│ → ideas note              │   │ dismiss junk               │   │ → posted                 │
│ Telegram: 🔥 alerts        │   │ tune profile (hashtags,    │   │ track your own post as a │
└───────────────────────────┘   │ watch list)                │   │ seed to compare          │
                                └────────────────────────────┘   └──────────────────────────┘
```

## Daily (automatic)

`scripts/run-daily.ps1 -Profile <name> -Analyze`, scheduled with Task Scheduler with "wake the computer to run" on. See [setup](setup.md#scheduling). Each morning you get:
- `<date>-viral-scout.md`: the data report.
- `<date>-viral-ideas.md`: patterns this week, a breakdown table (format, hook type, why it works) and **5 ideas adapted to your business**.
- **Telegram messages** for new 🔥 outliers and fast risers, each post once.

If you only have 2 minutes: read **Patterns this week** and **Ideas** in the ideas note.

## Weekly (30 minutes)

1. **Pick.** Open the latest ideas note and pick 1–3 ideas to film this week.
2. **Save the references.** In Claude Code: "save Daisy's spectrum and the Oliver skit". Or from the shell:
   ```
   python -m viral_scout save <profile> <ID> --note "spectrum: one situation, 7 phrases polite → rude"
   ```
   This creates a note in the swipe folder with the stats, thumbnail, hook, transcript and a "## Our version" section to fill in.
3. **Clean up.** `python -m viral_scout dismiss <profile> <ID> ...` for anything off-topic, so it never shows up again.
4. **Tune the profile:**
   - Hashtags under "Suggested hashtags" that fit → add them to `hashtags:`.
   - "Creators who keep showing up" → add them to `watch: youtube:`.
   - Junk that keeps slipping through → add a word to `exclude:`.
5. **Track your own post.** Once your video is out, `add` its URL. Each run shows its growth next to the posts that inspired it.

## Per video

Open the swipe note:
1. **Why it works:** the format, the hook type, and why people watch to the end. The skill fills this in when it saves.
2. **Our version:** your hook line (in the language you film in), three beats (hook → body → payoff/CTA), and on-screen text.
3. **`status`** in the frontmatter: `idea` → `scripted` → `filmed` → `posted`, or `skip`.

`swipe.base` in the same folder shows every saved post as a table grouped by status, or as cards with thumbnails.

## Reading the report

| You see | It means | Do |
|---|---|---|
| 🔥 mega, high **× usual** | the format beat the creator's own normal by 10× or more | study the hook and structure: this is the best signal |
| High **per day**, low × usual | a big creator doing what they always do | note the series format; don't copy the account |
| High **rise/day** | taking off right now | move fast: film this week while it's still rising |
| ⏳ | under 6 hours old | check again tomorrow |
| Same creator again and again | a reliable source of formats | add them to the watch list |

## Rules worth keeping

- **Copy formats, not footage.** Re-enact scenes with your own people. Never repost someone else's clip.
- **Copy the structure of a hook, not its words.** Write the hook in your audience's language and situation.
- **One idea per video**, 40–60 s, with text on screen doing the teaching. This is what the outliers have in common.
- **Make a series of what works.** "Vocabulary Chaos #5" and "Food Chaos #6" show that numbered series bring viewers back.

## Using it for another business

1. Copy `profiles/_template.yaml` to `profiles/<business>.yaml` and fill it in. See [profiles](profiles.md).
2. Run it once and look at what slipped through the filters. Tune `must_match` and `exclude`.
3. Schedule it. Each business gets its own reports, swipe folder and alert thresholds.
