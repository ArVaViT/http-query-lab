# http-query-lab

Empirical tests of the new **HTTP QUERY method ([RFC 10008](https://www.rfc-editor.org/rfc/rfc10008), June 2026)**
against real clients, servers, frameworks, and production infrastructure — not
what the spec says, but what actually happens on the wire in July 2026.

QUERY is a request method with GET semantics (safe, idempotent, cacheable) and a
POST-shaped body. This repo answers: *who on a real request path already speaks it?*

## Results (2026-07-03)

### Clients — can it SEND a QUERY request?

| Client | Result |
|---|---|
| curl (`-X QUERY`) | ✅ works |
| Chromium `fetch()` — same origin | ✅ **works** (contrary to most blog posts claiming "browsers can't send QUERY") |
| Chromium `fetch()` — cross-origin | ✅ works, but QUERY is not CORS-safelisted → always triggers preflight; server must list it in `Access-Control-Allow-Methods` |
| Chromium `XMLHttpRequest` | ✅ works |
| Chromium `fetch(…, {method: 'query'})` lowercase | ❌ sent as literal `query` (fetch only case-normalizes the 6 classic methods) → uvicorn rejects with 400 |
| Node `fetch` / undici | ✅ works |
| Python `requests` / `httpx` | ✅ works (`.request("QUERY", …)`) |
| .NET `HttpClient` | ✅ works, incl. **HTTP/2** (`RequestVersionExact`); .NET 10 even ships `HttpMethod.Query` |

### Servers & frameworks — can it RECEIVE one?

| Server | Result |
|---|---|
| Python `uvicorn` + FastAPI (`@app.api_route(methods=["QUERY"])`) | ✅ routes fine |
| Python stdlib `http.server` | ✅ dispatches to `do_QUERY`; clean `501` if absent |
| Node `http` (llhttp) | ✅ parses QUERY — it's in `http.METHODS` on Node 22 & 26 |
| Express 5 | ✅ `app.all()` catches it; a generated `app.query()` verb helper exists |
| Fastify 5 | ❌ refuses to register a QUERY route ("QUERY method is not supported") and 404s incoming QUERY; needs `addHttpMethod('QUERY', {hasBody: true})` |
| Flask/werkzeug (httpbin.org) | ⚠️ parses the method but returns 405 (route method lists don't include it) — graceful degradation |

### Production infrastructure

| Hop | Result |
|---|---|
| Vercel edge → Python serverless fn | ✅ passes QUERY end-to-end |
| Vercel edge → Node serverless fn | ✅ passes |
| Vercel edge → static asset | ❌ 405 (expected) |
| Supabase Edge Functions (Kong gateway + Deno), HTTP/1.1 and HTTP/2 | ✅ passes |
| **Vercel default bot mitigation** | ❌ **flags QUERY bursts as an attack.** A burst of 12 GETs from the same client: 12×200. An identical burst of 12 QUERYs: 403 `X-Vercel-Challenge-Token` / `X-Vercel-Mitigated: challenge` kicks in mid-burst. The mitigation is scoped per project **and per client TLS fingerprint** (flagged curl while node/.NET from the same IP kept working), and once flagged the client gets challenged on **every** method, including plain GET. Zero WAF rules configured — this is default behavior. |

### Caching — the whole point of QUERY

| Cache | Result |
|---|---|
| Chromium HTTP cache | ❌ **ignores `Cache-Control` on QUERY responses** — two identical QUERYs hit the server twice, while the GET control is served from cache. Browsers still treat QUERY like POST. |
| Vercel CDN (`s-maxage`) | ❌ untestable past the bot challenge; GET on the same endpoint goes MISS→HIT |

## Layout

- `local/` — lab servers and client scripts (FastAPI echo + CORS pair, Node raw-http, Express/Fastify probe, browser cache probe, the GET-vs-QUERY A/B burst script)
- `vercel/` — the deployed Vercel project (Python + Node echo functions, cacheable endpoint)
- `supabase/functions/query-echo/` — the Deno echo function

## Reproduce

```bash
# local
python local/server.py 8600          # FastAPI QUERY echo
node   local/node-server.js          # raw llhttp parse test
node   local/frameworks.mjs          # Express vs Fastify
curl -X QUERY http://127.0.0.1:8600/echo -d '{"q":"hi"}'

# prod
cd vercel && vercel deploy --prod
node local/abtest.mjs                # the bot-mitigation A/B
```
