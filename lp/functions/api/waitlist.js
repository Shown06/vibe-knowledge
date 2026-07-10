/**
 * Vibe Knowledge — Waitlist API (Cloudflare Pages Function)
 * POST /api/waitlist { email } → save to KV + Resend notification
 * GET  /api/waitlist?token=ADMIN_TOKEN → list signups
 */

export async function onRequestPost({ request, env }) {
  let body;
  try { body = await request.json(); } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }
  const email = (body.email || '').trim().toLowerCase();
  if (!email || !email.includes('@')) return json({ error: 'Invalid email' }, 400);

  const ts = new Date().toISOString();
  await env.WAITLIST.put(`email:${email}`, ts);

  if (env.RESEND_API_KEY) {
    notify(env, email, ts).catch(() => {});
  }

  return json({ ok: true, message: "You're on the list." });
}

export async function onRequestGet({ request, env }) {
  const url = new URL(request.url);
  if (!env.ADMIN_TOKEN || url.searchParams.get('token') !== env.ADMIN_TOKEN) {
    return json({ error: 'Unauthorized' }, 401);
  }
  const list = await env.WAITLIST.list({ prefix: 'email:' });
  const emails = await Promise.all(
    list.keys.map(async k => ({
      email: k.name.replace('email:', ''),
      signedUpAt: await env.WAITLIST.get(k.name)
    }))
  );
  return json({ count: emails.length, emails });
}

async function notify(env, email, ts) {
  if (!env.NOTIFY_EMAIL) return;
  const notifyTo = env.NOTIFY_EMAIL;
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${env.RESEND_API_KEY}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({
      from: 'Vibe Knowledge <noreply@vibeknowledge.dev>',
      to: [notifyTo],
      subject: `[Vibe Knowledge] New waitlist signup: ${email}`,
      text: `New signup at ${ts}\n\nEmail: ${email}`
    })
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
  });
}
