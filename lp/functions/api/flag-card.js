// Vibe Knowledge — カード訂正報告API (Cloudflare Pages Function)
// POST /api/flag-card { card_id } → VK_DATA KV の "vk_flagged" キー(JSON配列)に追記
// 認証必須。既存の cards.js / _auth.js のパターンに準拠。

import { requireAuth, jsonResponse } from "../_auth.js";

const FLAGGED_KEY = "vk_flagged";

export async function onRequestPost({ request, env }) {
  const auth = await requireAuth(request, env);
  if (!auth) return jsonResponse({ error: "Unauthorized" }, 401);

  let body;
  try {
    body = await request.json();
  } catch {
    return jsonResponse({ error: "Invalid JSON" }, 400);
  }

  const cardId = body && body.card_id != null ? String(body.card_id).trim() : "";
  if (!cardId) return jsonResponse({ error: "card_id required" }, 400);

  const raw = await env.VK_DATA.get(FLAGGED_KEY);
  let flagged = [];
  if (raw) {
    try {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) flagged = parsed;
    } catch {
      flagged = [];
    }
  }

  if (!flagged.includes(cardId)) {
    flagged.push(cardId);
    await env.VK_DATA.put(FLAGGED_KEY, JSON.stringify(flagged));
  }

  return jsonResponse({ ok: true, card_id: cardId, total_flagged: flagged.length });
}
