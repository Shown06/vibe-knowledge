import { requireAuth, jsonResponse } from "../_auth.js";

export async function onRequestGet({ request, env }) {
  const auth = await requireAuth(request, env);
  if (!auth) return jsonResponse({ ok: false }, 401);
  return jsonResponse({ ok: true, userId: auth.userId });
}
