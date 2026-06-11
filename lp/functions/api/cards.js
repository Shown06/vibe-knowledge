import { requireAuth, jsonResponse } from "../_auth.js";

export async function onRequestGet({ request, env }) {
  const auth = await requireAuth(request, env);
  if (!auth) return jsonResponse({ error: "Unauthorized" }, 401);

  const data = await env.VK_DATA.get("vk_data");
  if (!data) return jsonResponse({ cards: [], terms: {}, generated: "—" });

  return new Response(data, {
    status: 200,
    headers: { "Content-Type": "application/json; charset=utf-8" },
  });
}
