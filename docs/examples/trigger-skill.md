---
name: ideas
description: Marketing ideas and content packs for Homeworks. Thin trigger for viral-scout's /studio-ideas skill (profile myhomes). Use when the user asks for ideas, "generate ideas", posts for an idea, or on a schedule.
---

# Ideas (Homeworks)

Run `/studio-ideas myhomes $ARGUMENTS` and follow it. Examples: `/ideas` · `/ideas 8 holiday lights` · `/ideas posts` · `/ideas posts 40`.
- Method: `D:/repo/viral-scout/.claude/skills/studio-ideas/SKILL.md` (+ `packs.md`). Homeworks specifics: `$OBSIDIAN_VAULT/projects/myhomes/05 Marketing/studio-instructions.md`.
- CLI, from `D:/repo/viral-scout`, always this form: `python -m viral_scout ideas myhomes <info | pull | push <file> | tracked <ids…> | pack <id> "<note.md>" [--dry-run]>`. The profile fixes the project (`homes`), so it can't touch solar or Acme Agency ideas.
- Daily run: `pwsh D:/repo/viral-scout/scripts/ideas-daily.ps1 -Profile myhomes` (add `-PostsOnly` for a packs-only run).
- This repo's rules still apply to every text: `CLAUDE.md` (compliance, prices, `site.insured`).
