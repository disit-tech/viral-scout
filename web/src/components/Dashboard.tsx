"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import type { Item, Profile } from "@/lib/types";
import { num, when } from "@/lib/format";
import PostsBoard from "./PostsBoard";

/** The Videos page: every post of the business on one board (the board's Show selector picks the view). */
export default function Dashboard({ profile, local }: { profile: Profile; local: boolean }) {
  const [items, setItems] = useState<Item[]>(profile.items);
  useEffect(() => {                     // old ?tab= links whose content moved to the business tab bar
    const t = new URLSearchParams(window.location.search).get("tab");
    const moved: Record<string, string> = { swipe: "swipe", ideas: "swipe#ideas", health: "runs" };
    if (t && moved[t]) window.location.replace(`/p/${encodeURIComponent(profile.name)}/${moved[t]}`);
  }, [profile.name]);

  function patch(key: string, p: Partial<Item>) {
    setItems((all) => all.map((i) => (i.key === key ? { ...i, ...p } : i)));
  }

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span>Last run {when(profile.date)} · {num(items.filter((i) => !i.dismissed).length)} posts · {profile.sources.hashtags} hashtags · {profile.sources.keywords} keywords · {profile.sources.watch} watched</span>
        <Link href={`/p/${profile.name}/settings#videos`} className="hover:text-text">Edit sources →</Link>
      </div>
      <PostsBoard items={items} profile={profile.name} local={local} run={profile.date} onChange={patch} />
    </div>
  );
}
