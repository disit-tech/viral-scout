# Video quality framework

What makes a short video good, and how viral-scout measures each part. A video can win attention and fail at conversion, or win conversions and fail on profit, so judge every video against its own goal.

## The 5 tests every video must pass

| Test | Question | Measured by | For other people's videos | For your own videos and ads |
|---|---|---|---|---|
| 1. Attention | Does it stop the right people scrolling? | hook rate, first views, first-frame performance | × usual, × niche, hook and first-frame scores | hook rate, 2 s/3 s views, CPM (performance module) |
| 2. Retention | Does it keep viewers interested? | watch time, completion, drop-off, replays | growth per day, pacing and retention scores (watch time is private) | average watch time, % viewed, retention curve |
| 3. Engagement | Does it make viewers care? | shares, saves, comments | (likes + comments) ÷ views; shares and saves on TikTok; viewer questions | share, save, comment and follower rates |
| 4. Action | Does it drive the next step? | CTR, CVR, follows, leads | spoken CTA (last 5 s), CTA score | CTR, CVR, CPL |
| 5. Business impact | Does it pay off efficiently? | CPA, CAC, ROAS, contribution, lift | not observable (private) | CPA, CAC, ROAS, MER, contribution margin |

The video page shows these as pass / warn / fail / n/a. For other people's videos they rest on public signals and say so.

## The 20 creative criteria and the 100-point score

The AI step rates each criterion 1–5 with a reason (`viral_scout/scorecard.py`; the `/viral-scout` skill fills it in). Criteria roll up into 9 weighted groups:

| Group (points) | Criteria |
|---|---|
| Hook and first frame (15) | Hook (1–3 s) · First-frame impact |
| Audience relevance (15) | Target audience · Engagement |
| Retention, storytelling and pacing (15) | Retention · Watch time · Pacing · Storytelling · Pattern interrupts |
| Clarity and value proposition (15) | Clarity · Value proposition · Emotional impact |
| Credibility and proof (10) | Credibility / proof · Authenticity |
| CTA and conversion readiness (10) | CTA · Conversion potential |
| Visual and audio production (10) | Visual appeal · Audio quality |
| Platform-native execution (5) | Platform fit · Shareability |
| Accessibility and compliance (5) | captions, accurate claims, rights to music and footage |

Score = Σ (group rating ÷ 5 × group points). Verdicts: 85+ excellent, 70+ strong, 55+ promising, 40+ needs work, below 40 weak.

**It's a subjective creative assessment, not a prediction of views or sales.** The scorecard always sits next to the real numbers.

## A strong structure (30-second example)

| Time | Part | Job |
|---|---|---|
| 0–3 s | Hook | Stop the scroll with a problem, a claim or a striking visual |
| 3–10 s | Problem | Why this matters to the viewer |
| 10–20 s | Solution | The answer, product or transformation |
| 20–27 s | Proof | A demo, evidence or a real result |
| 27–30 s | CTA | The obvious next step |

This is a useful pattern, not a rule. Entertainment and education run on different timing. viral-scout pulls the hook (first 4 s) and the CTA (last 5 s) from every transcript, and the AI breakdown names each video's 3 beats.

## Production standards: the pre-publish check

`python -m viral_scout check <profile> <your-video>`, or the dashboard's **Check a video** page, measures your own draft with ffmpeg (and Whisper if installed):

| Area | Check | Target used |
|---|---|---|
| Aspect ratio | width ÷ height | 9:16 vertical |
| Resolution | pixels | at least 1080×1920 |
| Frame rate | fps | 24 or more |
| Audio | present, integrated loudness, true peak | about -14 LUFS (-16 to -12); peaks ≤ -1 dBTP |
| Black frames | at the start | under 0.2 s |
| First visual change | first scene cut | within 3 s |
| Pacing | average shot length | 4 s or less (heuristic) |
| Pattern interrupts | longest single shot | 8 s or less |
| Silence in the hook | silence in the first 3 s | under 0.5 s |
| Speech start | first words | within 1 s |
| CTA | words in the last 5 s | present |
| By eye | captions readable and timed, safe zones, branding, accurate claims and rights, readable on a phone | checklist |

Frames (first, 1 s, 3 s, middle, last) are saved so the AI step can judge first-frame impact and on-screen text, then fill the scorecard. These targets are practical starting points, not platform rules.

## KPIs, formulas and diagnosis

All the performance KPIs (attention, retention, engagement, traffic, conversion and profit), their formulas and denominators, the differences in how platforms define a view, the diagnostic ("high hook rate, low retention → …") and organic vs paid priorities are in [performance.md](performance.md). They need **your own** accounts' data: impressions, watch time, clicks and sales are private to the account that posted, so no tool can read them for someone else's video.

## Testing and improving

1. Set one primary goal (reach, followers, leads, sales, profit).
2. Define the audience and its problem or desire.
3. Make several variations: different hooks, angles, demos, offers, CTAs.
4. Compare fairly: the same audience, placement and period.
5. Read early signals (hook rate, retention, CTR, engagement), then the final outcome (qualified leads, sales, CPA, profit).
6. Read the retention curve: what's on screen where people leave?
7. Watch for creative fatigue as frequency rises.
8. Change the weakest part that matters, allowing for sample size.
9. Scale only validated winners, not views or cheap clicks.

Don't compare a 7-second entertainment clip with a 45-second sales video on completion rate.

## What's easy to forget

- **Offer:** great creative can't save a weak product, price or proposition.
- **Landing page:** clicks aren't sales. Speed, trust, checkout and message match all matter.
- **Profit:** a 4× ROAS isn't automatically profitable; margins and other costs decide.
- **Attribution:** purchases the platform reports aren't necessarily extra sales; attribution windows and overlapping channels inflate them.
- **Audience quality:** 5,000 views from the right buyers can beat a million irrelevant ones.
- **Unit economics:** the most you can afford per customer comes from your margins and payback period, not an industry benchmark.
