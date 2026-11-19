// LinkedIn Posts API (versioned REST): text, image or video post as a member or an organization.
// Token: LINKEDIN_ACCESS_TOKEN (w_member_social, or w_organization_social for a Page), author: LINKEDIN_AUTHOR
// (urn:li:person:… or urn:li:organization:…). `python -m viral_scout publish <p> connect linkedin` fills both.
// Docs: learn.microsoft.com/linkedin/marketing/community-management/shares/posts-api (videos-api, images-api).
import { readFileSync, statSync } from "node:fs";

/** LinkedIn "little text": reserved characters are escaped; #tag becomes a hashtag entity. */
export function littleText(s) {
  const esc = (x) => x.replace(/[\\|{}@[\]()<>*_~#]/g, (c) => `\\${c}`);
  const out = [];
  let last = 0;
  for (const m of s.matchAll(/#([\p{L}\p{N}_]+)/gu)) {
    out.push(esc(s.slice(last, m.index)), `{hashtag|\\#|${m[1]}}`);
    last = m.index + m[0].length;
  }
  out.push(esc(s.slice(last)));
  return out.join("");
}

export function client(token, version) {
  const base = "https://api.linkedin.com/rest";
  const headers = { Authorization: `Bearer ${token}`, "LinkedIn-Version": version || "202509", "X-Restli-Protocol-Version": "2.0.0" };
  async function call(path, body) {
    const r = await fetch(`${base}${path}`, { method: "POST", headers: { ...headers, "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const text = await r.text();
    if (!r.ok) throw new Error(`LinkedIn ${path}: HTTP ${r.status} ${text.slice(0, 300)}`);
    return { data: text ? JSON.parse(text) : {}, headers: r.headers };
  }
  return { call, headers };
}

async function uploadImage(li, author, file) {
  const { data } = await li.call("/images?action=initializeUpload", { initializeUploadRequest: { owner: author } });
  const r = await fetch(data.value.uploadUrl, { method: "PUT", headers: { Authorization: li.headers.Authorization }, body: readFileSync(file) });
  if (!r.ok) throw new Error(`LinkedIn image upload: HTTP ${r.status}`);
  return data.value.image;
}

async function uploadVideo(li, author, file) {
  const size = statSync(file).size;
  const { data } = await li.call("/videos?action=initializeUpload", {
    initializeUploadRequest: { owner: author, fileSizeBytes: size, uploadCaptions: false, uploadThumbnail: false },
  });
  const buf = readFileSync(file);
  const etags = [];
  for (const part of data.value.uploadInstructions) {
    const r = await fetch(part.uploadUrl, { method: "PUT", headers: { "Content-Type": "application/octet-stream" }, body: buf.subarray(part.firstByte, part.lastByte + 1) });
    if (!r.ok) throw new Error(`LinkedIn video part upload: HTTP ${r.status}`);
    etags.push(r.headers.get("etag"));
  }
  await li.call("/videos?action=finalizeUpload", { finalizeUploadRequest: { video: data.value.video, uploadToken: data.value.uploadToken ?? "", uploadedPartIds: etags } });
  return data.value.video;
}

/** One post. media: {video?: path, image?: path, title?: string}. Returns {id, link}. */
export async function linkedinPost({ token, author, version, text, media = {} }) {
  if (!token || !author) throw new Error("LINKEDIN_ACCESS_TOKEN / LINKEDIN_AUTHOR missing");
  const li = client(token, version);
  let content;
  if (media.video) content = { media: { title: (media.title || "").slice(0, 200), id: await uploadVideo(li, author, media.video) } };
  else if (media.image) content = { media: { id: await uploadImage(li, author, media.image) } };
  const body = {
    author,
    commentary: littleText(text),
    visibility: "PUBLIC",
    distribution: { feedDistribution: "MAIN_FEED", targetEntities: [], thirdPartyDistributionChannels: [] },
    lifecycleState: "PUBLISHED",
    isReshareDisabledByAuthor: false,
    ...(content ? { content } : {}),
  };
  const { headers } = await li.call("/posts", body);
  const id = headers.get("x-restli-id") || headers.get("x-linkedin-id") || "";
  return { id, link: id ? `https://www.linkedin.com/feed/update/${id}/` : null };
}
