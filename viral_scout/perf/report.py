"""Markdown report for own performance: <output_dir>/<date>-performance.md (Obsidian-friendly)."""
from . import kpis as K

ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌", "n/a": "·"}
PLATFORM = {"youtube": "YouTube", "instagram": "Instagram", "facebook": "Meta", "tiktok": "TikTok"}


def fmt(kid, v):
    if v is None:
        return "—"
    unit = K.KPI_BY_ID[kid][3] if kid in K.KPI_BY_ID else ("x" if kid == "mer" else "")
    if unit == "pct":
        return f"{v:.1f}%"
    if unit == "money":
        return f"{v:,.2f}"
    if unit in ("x",):
        return f"{v:.2f}×"
    if unit == "seconds":
        return f"{v:.1f} s"
    if unit == "score":
        return f"{v:+.0f}"
    if abs(v) >= 1e6:
        return f"{v / 1e6:.1f}M"
    if abs(v) >= 1e4:
        return f"{v / 1e3:.1f}K"
    return f"{v:,.0f}"


def _k(row, kid):
    k = row["kpis"].get(kid)
    return fmt(kid, k["value"]) if k else "—"


def _name(row, n=48):
    t = (row.get("title") or row["id"]).replace("|", "/").replace("\n", " ")
    t = t[:n] + ("…" if len(t) > n else "")
    return f"[{t}]({row['url']})" if row.get("url") else t


def _kpi_section(lines, data, kind):
    acc = data["account"].get(kind)
    if not acc or not acc.get("kpis"):
        return
    meds = data["medians"][kind]
    lines += [f"### {'Organic' if kind == 'organic' else 'Paid'}: account totals and per-video medians", "",
              f"{acc['records']} {'videos' if kind == 'organic' else 'ads'}. *Total* = Σ numerators ÷ Σ denominators over the "
              "records that have both (weighted); *median* = the typical video, the benchmark for diagnostics.", ""]
    for g, gname in K.GROUPS.items():
        ids = [k[0] for k in K.KPIS if k[1] == g and (k[0] in acc["kpis"] or k[0] in meds["all"])]
        if not ids and not (g == "E" and acc.get("mer")):
            continue
        lines += [f"**{g}. {gname}**", "", "| KPI | Total | Median | n | Formula | Denominator |", "|---|---|---|---|---|---|"]
        for kid in ids:
            t = acc["kpis"].get(kid)
            lines.append(f"| {K.KPI_BY_ID[kid][2]} | {fmt(kid, t['value']) if t else '—'} | "
                         f"{fmt(kid, meds['all'].get(kid))} | {meds['n'].get(kid, 0)} | {K.KPI_BY_ID[kid][5]} | "
                         f"{(t or {}).get('denominator') or ''} |")
        if g == "E" and acc.get("mer"):
            lines.append(f"| MER | {fmt('mer', acc['mer']['value'])} | | | total revenue ÷ total marketing spend | "
                         f"{acc['mer']['basis']} |")
        lines.append("")


def markdown(data):
    rows = data["records"]
    org = [r for r in rows if r["kind"] == "organic"]
    paid = [r for r in rows if r["kind"] == "paid"]
    L = ["---", "type: performance", f"profile: {data['name']}", f"date: {data['date'][:10]}",
         f"goal: {data['goal']}", "---", "", f"# Your performance: {data['name']} ({data['date'][:10]})", "",
         f"Your own videos and ads, from official APIs and your own exports. Goal: **{data['goal']}**. Benchmarks are "
         "**your account's medians** (same kind, same length band for retention), not industry averages.", ""]

    s = data["sources"]
    L += ["## Sources", ""]
    for name, n in s["pulled"].items():
        L.append(f"- Pulled **{name}**: {n} records")
    for name, v in s["stored"].items():
        if name.startswith("csv:"):
            L.append(f"- Imported **{name}**: {v['records']} records (last import {v['updated'][:10]})")
    if not rows:
        L.append("- No data yet. Add keys (docs/performance.md) or import a CSV: "
                 f"`python -m viral_scout perf import {data['name']} file.csv --source meta|tiktok|youtube|generic`")
    L.append("")

    if data["unit_economics"]:
        L += ["## Unit economics (from the profile)", "", "| Limit | Value | Formula | Note |", "|---|---|---|---|"]
        for k, v in data["unit_economics"].items():
            val = f"{v['value']:.2f}×" if k == "break_even_roas" else f"{v['value']:,.2f}"
            L.append(f"| {k.replace('_', ' ')} | {val} | {v['formula']} | {v['note']} |")
        L.append("")

    if rows:
        L += ["## KPIs (A Attention · B Retention · C Engagement · D Traffic · E Conversion & profit)", ""]
        _kpi_section(L, data, "organic")
        _kpi_section(L, data, "paid")

    pr = data["priorities"]
    L += ["## Priorities", "", "| Organic | Paid (" + pr["goal"] + ") |", "|---|---|"]
    for a, b in zip(pr["organic"], pr["paid"]):
        L.append(f"| **{a['what']}**: {a['why']} | **{b['what']}**: {b['why']} |")
    L.append("")

    if org:
        L += ["## Organic videos", "", "| Video | Platform | Len | Views | Hook | Avg watch | Avg % | Completion | Eng. | Share | Save | Follow conv. |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(org, key=lambda x: -(x.get("views") or 0)):
            L.append(f"| {_name(r)} | {PLATFORM.get(r['platform'], r['platform'])} | "
                     f"{fmt('avg_watch_time', r['duration']) if r.get('duration') else '—'} | {_k(r, 'views')} | "
                     f"{_k(r, 'hook_rate')} | {_k(r, 'avg_watch_time')} | {_k(r, 'avg_pct_viewed')} | "
                     f"{_k(r, 'completion_rate')} | {_k(r, 'engagement_rate')} | {_k(r, 'share_rate')} | "
                     f"{_k(r, 'save_rate')} | {_k(r, 'follower_conversion')} |")
        L.append("")
    if paid:
        L += ["## Ads", "", "| Ad | Platform | Spend | Impr. | Hook | ThruPlay | Completion | Link CTR | CPC | CPM | CVR | CPA | ROAS | Contribution |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in sorted(paid, key=lambda x: -(x.get("spend") or 0)):
            L.append(f"| {_name(r)} | {PLATFORM.get(r['platform'], r['platform'])} | {fmt('cpa', r.get('spend'))} | "
                     f"{_k(r, 'impressions')} | {_k(r, 'hook_rate')} | {_k(r, 'thruplay_rate')} | "
                     f"{_k(r, 'completion_rate')} | {_k(r, 'link_ctr')} | {_k(r, 'cpc_link') if 'cpc_link' in r['kpis'] else _k(r, 'cpc')} | "
                     f"{_k(r, 'cpm')} | {_k(r, 'cvr')} | {_k(r, 'cpa')} | {_k(r, 'roas')} | {_k(r, 'contribution_margin')} |")
        L.append("")

    if rows:
        L += ["## The 5 tests", "", "Each video against your own medians: ✅ at or above · ⚠️ within 25% below · ❌ more "
              "than 25% below (costs: the other way round) · · not measurable.", "",
              "| Video | Kind | Attention | Retention | Engagement | Action | Business impact |", "|---|---|---|---|---|---|---|"]
        for r in rows:
            cells = []
            for t in r["tests"]:
                cells.append(ICON[t["status"]] + (f" {fmt(t['metric'], t['value'])}" if t["metric"] else ""))
            L.append(f"| {_name(r, 40)} | {r['kind']} | " + " | ".join(cells) + " |")
        L.append("")

    curved = [r for r in rows if r.get("curve")]
    if curved:
        L += ["## Retention curves: where viewers drop", ""]
        for r in curved:
            src = "YouTube audience retention" if r["curve"]["source"] == "retention" else "25/50/75/100% view counts"
            L.append(f"- **{_name(r, 60)}** ({src}): {r['curve_summary']}")
        L.append("")

    if rows:
        L += ["## Diagnostics", ""]
        for r in rows:
            d = r["diagnosis"]
            L.append(f"### {_name(r, 70)}")
            L.append(f"*{r['kind']} · {PLATFORM.get(r['platform'], r['platform'])}"
                     + (f" · {r['duration']:.0f} s" if r.get("duration") else "") + "*")
            L.append("")
            if d["problem"]:
                p = d["problem"]
                L += [f"**Biggest problem: {p['title']}**. {p['evidence']}", "", "Investigate:"]
                L += [f"- {x}" for x in p["investigate"]]
                others = [f["title"] + f" ({f['evidence']})" for f in d["findings"][1:]]
                if others:
                    L += ["", "Also: " + "; ".join(others)]
            else:
                L.append("No clear problem against your own medians. Keep it as the control and test one variable "
                         "at a time against it.")
            if d["caveats"]:
                L += [""] + [f"> {c}" for c in d["caveats"]]
            if r.get("trend"):
                L += ["", "Trend since the first snapshot: " + ", ".join(
                    f"{k} {fmt(k, a)} → {fmt(k, b)}" for k, (a, b) in r["trend"].items())]
            L.append("")

    fat = [r for r in paid if (r.get("fatigue") or {}).get("detected")]
    L += ["## Creative fatigue", ""]
    if fat:
        for r in fat:
            f = r["fatigue"]
            L.append(f"- **{_name(r, 60)}**: frequency {f['frequency'][0]} → {f['frequency'][1]}, CTR {f['ctr'][0]}% → "
                     f"{f['ctr'][1]}% ({f['from']} … {f['to']}). Refresh the hook, keep the body.")
    else:
        L.append("None detected (needs ≥6 daily rows or ≥3 snapshots per ad with frequency rising ≥15% while CTR falls ≥20%).")
    L.append("")

    L += ["## Read this before acting", "",
          "- **Attribution**: platform conversions are claims within that platform's window; compare with your own orders.",
          "- **4× ROAS ≠ profitable**: break-even ROAS = 1 ÷ gross margin; contribution margin is what's left.",
          "- **Like for like**: compare completion and avg % viewed only between videos of similar length.",
          "- **Early vs final**: hook and CTR settle after ~1,000 impressions; CPA needs ~50 conversions per variation.",
          "", "### Platform definitions differ", ""]
    L += [f"- **{a}**: {b}" for a, b in data["platform_differences"]]
    L.append("")
    if s["skipped"]:
        L += ["## Skipped sources", ""] + [f"- {x}" for x in s["skipped"]] + [""]
    if s["errors"]:
        L += ["## Errors", ""] + [f"- {x}" for x in s["errors"][:30]] + [""]
    return "\n".join(L)
