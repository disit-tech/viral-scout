## Job: {{posts_per_day}} text / photo post(s) for tomorrow

For {{posts_platforms}} (the posting job puts them out at their times; {{approval_intro}}). Not videos: the film job makes those.

### 0. Is it needed?
Read `{{posts_queue}}` (create it with a `| date | title | post | status |` table header if missing). If tomorrow already has {{posts_per_day}} rows, stop.

### 1. Pick the topics
From the freshest material in `<vault>` (viral-scout notes, the ideas: `{{ideas}} pull`, the swipe file, the tracker, what the films of the next days are about). Mix the formats over the week, never the same one twice in a row:
- **tip / myth**: one useful thing a customer can check or do, with the number and its source;
- **behind the work / proof**: a real job, a real photo, what happened (no made-up customers, quotes or results);
- **question / poll-style**: one question people answer in the comments;
- **challenge** (comment challenges: {{challenges}}): "Comment <KEYWORD> and we'll send you <the free thing>". The free thing must exist (a checklist, a guide, a page on the site, a short tutorial video already made): its URL goes in `reward:`. Never promise a prize or money. "Tag 2 friends" challenges are for Instagram only (`mentions: 2`) and never on Facebook (Facebook demotes tag-bait posts) or LinkedIn.

### 2. Write
One file per post: `<vault>/05 Marketing/Social/posts/<date>-<n>-<slug>.md` in the caption-file format (docs/publish-and-jobs.md#caption-file):
```
photo: <path of a real photo, optional>
challenge: <KEYWORD>        (only for a challenge)
reward: <url>               (only for a challenge)
## LinkedIn
<professional, first line is the hook, short paragraphs, ≤ 1300 characters, ≤ 3 hashtags, link with utm_source=linkedin>
## Facebook
<conversational, ≤ 600 characters, link with utm_source=facebook>
## Threads
<≤ 450 characters, casual, a question or a hot take works best; text only (a photo is not posted there)>
## Instagram
<only when there is a photo; Instagram photo posts are posted by hand>
```
- Facts: re-verify every number today on its official source (WebSearch/WebFetch); a claim you cannot verify is cut. Compliance check as for scripts.
- Photo: only real photos of the business from the vault or the business repo folders (the business rules say where), or a still you make from one of its films with `{{video}} still …`. No stock photos of strangers presented as the business, no AI images presented as real jobs. No photo fits: a text post.
- The business's voice and the CTA rules from the business rules below.

### 3. Queue
Add one row per post to `{{posts_queue}}`: `| <tomorrow> | <title> | `<full path of the post file>` | {{queue_status}} |`. The n-th row of a date posts at the n-th time of publish.posts.times.

### 4. Tell {{owner}}
If delivery is on, per post: `{{notes}} send <photo, or the post file> "📝 Post for <date>: <title>. {{review_line}}" --tags "post"`. Then the daily note line.
