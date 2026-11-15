// One-time YouTube login → YOUTUBE_REFRESH_TOKEN (for publish.mjs).
// Needs YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET of a Google Cloud OAuth client of type "Desktop app" (docs/publish-and-jobs.md).
//   node youtube-auth.mjs  → opens Google's consent page, catches the answer on http://127.0.0.1:<port>, prints the refresh token
import { createServer } from "node:http";
import { randomBytes, createHash } from "node:crypto";
import { exec } from "node:child_process";
import { loadEnv } from "./lib.mjs";

const get = loadEnv();
const id = get("YOUTUBE_CLIENT_ID");
const secret = get("YOUTUBE_CLIENT_SECRET");
if (!id || !secret) {
  console.error("Set YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET (env or PUBLISH_ENV_FILE) first. See docs/publish-and-jobs.md → YouTube.");
  process.exit(1);
}
const SCOPES = ["https://www.googleapis.com/auth/youtube.upload", "https://www.googleapis.com/auth/youtube.force-ssl"];
const verifier = randomBytes(32).toString("base64url");
const challenge = createHash("sha256").update(verifier).digest("base64url");
const state = randomBytes(12).toString("hex");

const server = createServer(async (req, res) => {
  const u = new URL(req.url, "http://127.0.0.1");
  if (u.pathname !== "/") return res.writeHead(404).end();
  const code = u.searchParams.get("code");
  if (u.searchParams.get("state") !== state || !code) {
    res.writeHead(400).end(`Login failed: ${u.searchParams.get("error") ?? "no code"}`);
    return;
  }
  const redirect = `http://127.0.0.1:${server.address().port}`;
  const r = await fetch("https://oauth2.googleapis.com/token", {
    method: "POST",
    body: new URLSearchParams({ code, client_id: id, client_secret: secret, redirect_uri: redirect, grant_type: "authorization_code", code_verifier: verifier }),
  });
  const data = await r.json();
  res.writeHead(200, { "Content-Type": "text/plain; charset=utf-8" }).end(data.refresh_token ? "Done. Back to the terminal." : `No refresh token: ${JSON.stringify(data)}`);
  if (data.refresh_token) {
    console.log(`\nYOUTUBE_REFRESH_TOKEN=${data.refresh_token}\n\nPut it in the profile's publish.env_file under the name publish.tokens.youtube maps it to. Treat it like a password.`);
  } else console.error("No refresh token returned:", data);
  server.close();
});

server.listen(0, "127.0.0.1", () => {
  const redirect = `http://127.0.0.1:${server.address().port}`;
  const url = `https://accounts.google.com/o/oauth2/v2/auth?${new URLSearchParams({
    client_id: id,
    redirect_uri: redirect,
    response_type: "code",
    scope: SCOPES.join(" "),
    access_type: "offline",
    prompt: "consent",
    state,
    code_challenge: challenge,
    code_challenge_method: "S256",
  })}`;
  console.log(`Sign in with the channel's Google account:\n${url}\n`);
  exec(process.platform === "win32" ? `start "" "${url}"` : `${process.platform === "darwin" ? "open" : "xdg-open"} "${url}"`);
});
