/**
 * Vibe Knowledge — Waitlist Worker (Cloudflare Workers)
 *
 * Routes:
 *   POST /api/waitlist  { email }  → save to KV + notify via Resend
 *   GET  /api/waitlist  (admin)    → list all emails (requires ?token=ADMIN_TOKEN)
 *
 * Environment variables (set via wrangler secret put):
 *   RESEND_API_KEY   — Resend API key (free tier: 3000 emails/month)
 *   NOTIFY_EMAIL     — where to receive "new signup" notifications
 *   ADMIN_TOKEN      — secret for listing emails
 *
 * KV namespace binding: WAITLIST (bind in wrangler.toml)
 */

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    // Serve static LP for all non-API routes
    if (!url.pathname.startsWith('/api/')) {
      return new Response('Not found', { status: 404 });
    }

    if (url.pathname === '/api/waitlist') {
      if (request.method === 'POST') return handleSignup(request, env);
      if (request.method === 'GET') return handleList(request, env);
    }

    return new Response('Not found', { status: 404 });
  }
};

async function handleSignup(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: 'Invalid JSON' }, 400);
  }

  const email = (body.email || '').trim().toLowerCase();
  if (!email || !email.includes('@')) {
    return json({ error: 'Invalid email' }, 400);
  }

  // Idempotent: store with email as key, ISO timestamp as value
  const ts = new Date().toISOString();
  await env.WAITLIST.put(`email:${email}`, ts);

  // Notify via Resend (fire-and-forget — don't block the response)
  if (env.RESEND_API_KEY && env.NOTIFY_EMAIL) {
    notify(env, email, ts).catch(() => {});
  }

  return json({ ok: true, message: "You're on the list." });
}

async function handleList(request, env) {
  const url = new URL(request.url);
  const token = url.searchParams.get('token');
  if (!env.ADMIN_TOKEN || token !== env.ADMIN_TOKEN) {
    return json({ error: 'Unauthorized' }, 401);
  }

  const list = await env.WAITLIST.list({ prefix: 'email:' });
  const emails = list.keys.map(k => ({
    email: k.name.replace('email:', ''),
    signedUpAt: k.name
  }));

  // Fetch timestamps
  const result = await Promise.all(
    list.keys.map(async k => ({
      email: k.name.replace('email:', ''),
      signedUpAt: await env.WAITLIST.get(k.name)
    }))
  );

  return json({ count: result.length, emails: result });
}

async function notify(env, email, ts) {
  await fetch('https://api.resend.com/emails', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.RESEND_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      from: 'Vibe Knowledge <noreply@vibeknowledge.dev>',
      to: [env.NOTIFY_EMAIL],
      subject: `New waitlist signup: ${email}`,
      text: `New signup at ${ts}\n\nEmail: ${email}`
    })
  });
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      'Content-Type': 'application/json',
      'Access-Control-Allow-Origin': '*'
    }
  });
}
