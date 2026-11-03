"use client";

export type ActionBody =
  | { profile: string; action: "save"; ref: string; note?: string }
  | { profile: string; action: "dismiss"; ref: string }
  | { profile: string; action: "track"; ref: string }
  | { profile: string; action: "status"; ref: string; status: string };

export async function runAction(body: ActionBody): Promise<{ ok: boolean; output: string }> {
  const res = await fetch("/api/action", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({ ok: false, output: `HTTP ${res.status}` }));
  return { ok: res.ok && data.ok, output: data.output ?? "" };
}

export function cli(body: ActionBody): string {
  const q = (s: string) => (/^[\w.:/-]+$/.test(s) ? s : `"${s.replace(/"/g, '\\"')}"`);
  switch (body.action) {
    case "save":
      return `python -m viral_scout save ${body.profile} ${q(body.ref)}${body.note ? ` --note ${q(body.note)}` : ""}`;
    case "dismiss":
      return `python -m viral_scout dismiss ${body.profile} ${q(body.ref)}`;
    case "track":
      return `python -m viral_scout add ${body.profile} ${q(body.ref)}`;
    case "status":
      return `python -m viral_scout status ${body.profile} ${q(body.ref)} ${body.status}`;
  }
}
