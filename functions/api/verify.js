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

async function verifyUid(uid, ts, sign, env) {
  if (!uid || !ts || !sign) return { ok: false, code: "MISSING_PARAMS" };
  const now = Date.now();
  const clientTs = parseInt(ts, 10);
  if (isNaN(clientTs) || Math.abs(now - clientTs) > TS_WINDOW) return { ok: false, code: "TS_EXPIRED" };
  const expected = await hmacSign(env.HMAC_SECRET, uid + ts);
  if (expected !== sign) return { ok: false, code: "BAD_SIGN" };
  const raw = await env.WHITELIST.get(uid);
  if (!raw) return { ok: false, code: "NOT_WHITELISTED" };
  let info;
  try { info = JSON.parse(raw); } catch { info = { name: "unknown" }; }
  if (info.expire && info.expire !== "forever") {
    const exp = new Date(info.expire).getTime();
    if (isNaN(exp) || now > exp) return { ok: false, code: "EXPIRED", name: info.name };
  }
  return { ok: true, name: info.name || "user", uid };
}

export async function onRequest(context) {
  const { request, env } = context;
  const url = new URL(request.url);

  if (request.method === "OPTIONS") {
    return new Response(null, { headers: { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET,POST,OPTIONS", "Access-Control-Allow-Headers": "*" } });
  }

  const uid = url.searchParams.get("uid");
  const ts = url.searchParams.get("ts");
  const sign = url.searchParams.get("sign");
  const result = await verifyUid(uid, ts, sign, env);
  return json(result, result.ok ? 200 : 403);
}
