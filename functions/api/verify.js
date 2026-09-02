const TS_WINDOW = 60 * 1000;

function hmacSign(secret, msg) {
  const enc = new TextEncoder();
  const key = enc.encode(secret);
  const data = enc.encode(msg);
  return crypto.subtle.importKey("raw", key, { name: "HMAC", hash: "SHA-256" }, false, ["sign"])
    .then(k => crypto.subtle.sign("HMAC", k, data))
    .then(buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join(""));
}

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", "Access-Control-Allow-Origin": "*" }
  });
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Access-Control-Allow-Headers": "*" } });
  }

  try {
    const uid = url.searchParams.get("uid");
    const ts = url.searchParams.get("ts");
    const sign = url.searchParams.get("sign");

    if (!uid || !ts || !sign) return json({ ok: false, code: "MISSING_PARAMS" }, 403);
    if (!env.HMAC_SECRET) return json({ ok: false, code: "NO_SECRET" }, 500);
    if (!env.WHITELIST) return json({ ok: false, code: "NO_KV" }, 500);

    const now = Date.now();
    const clientTs = parseInt(ts, 10);
    if (isNaN(clientTs) || Math.abs(now - clientTs) > TS_WINDOW) return json({ ok: false, code: "TS_EXPIRED" }, 403);

    const expected = await hmacSign(env.HMAC_SECRET, uid + ts);
    if (expected !== sign) return json({ ok: false, code: "BAD_SIGN" }, 403);

    const raw = await env.WHITELIST.get(uid);
    if (!raw) return json({ ok: false, code: "NOT_WHITELISTED" }, 403);

    let info;
    try { info = JSON.parse(raw); } catch { info = { name: "unknown" }; }

    if (info.expire && info.expire !== "forever") {
      const exp = new Date(info.expire).getTime();
      if (isNaN(exp) || now > exp) return json({ ok: false, code: "EXPIRED", name: info.name }, 403);
    }

    return json({ ok: true, name: info.name || "user", uid });
  } catch (e) {
    return json({ ok: false, code: "INTERNAL", message: e.message }, 500);
  }
}
