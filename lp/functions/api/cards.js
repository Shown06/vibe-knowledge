import { requireAuth, jsonResponse } from "../_auth.js";

export async function onRequestGet({ request, env }) {
  const auth = await requireAuth(request, env);
  if (!auth) return jsonResponse({ error: "Unauthorized" }, 401);

  const [data, flaggedRaw] = await Promise.all([
    env.VK_DATA.get("vk_data"),
    env.VK_DATA.get("vk_flagged"),
  ]);

  let flagged = [];
  if (flaggedRaw) {
    try {
      const parsed = JSON.parse(flaggedRaw);
      if (Array.isArray(parsed)) flagged = parsed;
    } catch {
      flagged = [];
    }
  }

  if (!data) return jsonResponse({ cards: [], terms: {}, generated: "—", flagged });

  let obj;
  try {
    obj = JSON.parse(data);
  } catch {
    obj = { cards: [], terms: {}, generated: "—" };
  }
  obj.flagged = flagged;

  return new Response(JSON.stringify(obj), {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
