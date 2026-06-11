// 認証ユーティリティ (Cloudflare Pages Functions / Web Crypto)
// 外部依存なし。JWT(HS256)をWeb Cryptoで署名・検証する。
// マルチユーザー前提で payload に sub(=userId) を持たせる。

const enc = new TextEncoder();

function b64urlEncode(bytes) {
  let bin = "";
  const arr = bytes instanceof Uint8Array ? bytes : new Uint8Array(bytes);
  for (const b of arr) bin += String.fromCharCode(b);
  return btoa(bin).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function b64urlDecodeToString(str) {
  const pad = str.length % 4 === 0 ? "" : "=".repeat(4 - (str.length % 4));
  const b64 = str.replace(/-/g, "+").replace(/_/g, "/") + pad;
  return atob(b64);
}

async function hmacKey(secret) {
  return crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign", "verify"]
  );
}

// JWT 署名。expSeconds 秒後に失効。
export async function signJWT(payload, secret, expSeconds = 60 * 60 * 24 * 30) {
  const now = Math.floor(Date.now() / 1000);
  const body = { ...payload, iat: now, exp: now + expSeconds };
  const header = { alg: "HS256", typ: "JWT" };
  const headerB64 = b64urlEncode(enc.encode(JSON.stringify(header)));
  const bodyB64 = b64urlEncode(enc.encode(JSON.stringify(body)));
  const data = `${headerB64}.${bodyB64}`;
  const key = await hmacKey(secret);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(data));
  return `${data}.${b64urlEncode(sig)}`;
}

// JWT 検証。正当なら payload を返す。不正・失効なら null。
export async function verifyJWT(token, secret) {
  if (!token || typeof token !== "string") return null;
  const parts = token.split(".");
  if (parts.length !== 3) return null;
  const [headerB64, bodyB64, sigB64] = parts;
  const data = `${headerB64}.${bodyB64}`;
  const key = await hmacKey(secret);
  let sigBytes;
  try {
    const sigStr = b64urlDecodeToString(sigB64);
    sigBytes = Uint8Array.from(sigStr, (c) => c.charCodeAt(0));
  } catch {
    return null;
  }
  const valid = await crypto.subtle.verify("HMAC", key, sigBytes, enc.encode(data));
  if (!valid) return null;
  let payload;
  try {
    payload = JSON.parse(b64urlDecodeToString(bodyB64));
  } catch {
    return null;
  }
  if (payload.exp && Math.floor(Date.now() / 1000) > payload.exp) return null;
  return payload;
}

export function parseCookies(request) {
  const header = request.headers.get("Cookie") || "";
  const out = {};
  for (const part of header.split(";")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    out[part.slice(0, i).trim()] = decodeURIComponent(part.slice(i + 1).trim());
  }
  return out;
}

export function sessionCookie(token, maxAgeSeconds = 60 * 60 * 24 * 30) {
  // Secure + HttpOnly + SameSite=Lax。Pages は HTTPS なので Secure 可。
  return `vk_session=${token}; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=${maxAgeSeconds}`;
}

export function clearSessionCookie() {
  return `vk_session=; Path=/; HttpOnly; Secure; SameSite=Lax; Max-Age=0`;
}

// 認証必須API用。検証OKなら { userId } を返し、NGなら null。
export async function requireAuth(request, env) {
  const secret = env.VK_JWT_SECRET;
  if (!secret) return null;
  const token = parseCookies(request).vk_session;
  const payload = await verifyJWT(token, secret);
  if (!payload || !payload.sub) return null;
  return { userId: payload.sub };
}

export function jsonResponse(obj, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { "Content-Type": "application/json", ...extraHeaders },
  });
}
