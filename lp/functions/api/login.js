import { signJWT, sessionCookie, jsonResponse } from "../_auth.js";

export async function onRequestPost({ request, env }) {
  let body;
  try { body = await request.json(); } catch { return jsonResponse({ error: "invalid JSON" }, 400); }

  const { username, password } = body || {};
  const validUser = env.VK_USER || "shown";
  const validPass = env.VK_PASSWORD;

  if (!validPass) return jsonResponse({ error: "server misconfigured" }, 500);
  if (username !== validUser || password !== validPass) {
    return jsonResponse({ error: "ユーザー名またはパスワードが違います" }, 401);
  }

  const secret = env.VK_JWT_SECRET;
  if (!secret) return jsonResponse({ error: "server misconfigured" }, 500);

  const token = await signJWT({ sub: validUser }, secret);
  return new Response(JSON.stringify({ ok: true }), {
    status: 200,
    headers: {
      "Content-Type": "application/json",
      "Set-Cookie": sessionCookie(token),
    },
  });
}
