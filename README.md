# http-query-lab

Empirical tests of the new **HTTP QUERY method ([RFC 10008](https://www.rfc-editor.org/rfc/rfc10008), June 2026)**
against real clients, servers, frameworks, and production infrastructure. Not
what the spec says, but what actually happens on the wire in July 2026.

QUERY is a request method with GET semantics (safe, idempotent, cacheable per
RFC 10008 §2 and §2.7) that carries its query in the body instead of the URI.
This repo answers: *who on a real request path already speaks it, and who breaks?*

## Headline: Vercel's default bot mitigation treats QUERY as a bot signal

Twenty requests, one client, 400ms apart, one method at a time:

```
GET   x20  from node/undici : all 200            (clean)
POST  x20  from node/undici : all 200            (clean, and POST carries a body)
QUERY x20  from node/undici : 200,200,200,403... (challenge at request #4)
QUERY x20  from curl        : 200,...,403...      (challenge at request #5)
```

The 403 is `X-Vercel-Mitigated: challenge` from the edge, before the request
reaches the function. Same client, same body, same rate: GET and POST run clean
to 20, switching only the method to QUERY trips a bot challenge in ~4 requests,
and it reproduces from a second independent client fingerprint. So it is not the
TLS fingerprint, not the body, not the burst volume. It is the method. Once
flagged, the client is challenged on every method (GET included) for >10 minutes.
No custom WAF rules were configured (firewall config was empty); this is default
bot protection. Repro: `local/decisive.mjs`.

## The runtimes are ready (finding #7, also unpublished)

QUERY passes end-to-end everywhere the edge lets it through:

| Hop | Result |
|---|---|
| Vercel edge -> Python serverless fn (HTTP/1.1 via curl) | pass |
| Vercel edge -> Node serverless fn | pass |
| Vercel edge -> static asset | 405 (correct) |
| Supabase Edge (Kong + Deno), HTTP/1.1 | pass |
| Supabase Edge (Kong + Deno), HTTP/2 | pass |

## Clients and frameworks

| Layer | QUERY today | Source |
|---|---|---|
| curl `-X QUERY` | works | this repo |
| Chromium `fetch()` / `XMLHttpRequest`, same-origin | works | this repo + [whatwg/fetch#1938](https://github.com/whatwg/fetch/issues/1938) |
| Chromium `fetch()`, cross-origin | works, needs CORS preflight (QUERY not safelisted) | RFC 10008 §4 |
| Node undici, Python requests/httpx, .NET HttpClient (incl. HTTP/2) | all send it | this repo |
| Node `http` / llhttp | in `http.METHODS` since v21.7.2 (llhttp 9.2.0) | [nodejs/node#51562](https://github.com/nodejs/node/issues/51562) |
| Express 5 | routes it; `app.query()` auto-generated from `http.METHODS` | [expressjs/express#5615](https://github.com/expressjs/express/issues/5615) |
| Fastify 5 | refuses until `addHttpMethod('QUERY',{hasBody:true})` | [fastify#5504](https://github.com/fastify/fastify/discussions/5504) |
| Python `http.server` | define `do_QUERY`; missing handler -> clean 501 | this repo |
| .NET 10 | `HttpMethod.Query` on client and server | Microsoft Learn |

## Two footguns

**Lowercase `query` is rejected by the default uvicorn parser (llhttp), not h11.**
`fetch` only uppercases the six classic methods, so `method:'query'` goes on the
wire literally as lowercase. Then:

```
uvicorn --http httptools :  QUERY -> 200,  query -> 400,  get -> 400,  FROBNICATE -> 400
uvicorn --http h11       :  QUERY -> 200,  query -> 200,  get -> 200,  FROBNICATE -> 200
```

llhttp matches its method table case-sensitively, so any lowercase/unknown verb
is an invalid token (not QUERY-specific: lowercase `get` 400s too). h11 accepts
everything and lets the app answer. Repro: `local/parser_test.py`. The fetch
normalization gap itself is tracked in [whatwg/fetch#1938](https://github.com/whatwg/fetch/issues/1938).

**Browsers don't cache a QUERY response yet**, even with `Cache-Control:
public, max-age=300`. Two identical QUERYs against a local origin (no CDN) both
hit the origin; the GET control is served from cache on the second request.
Existing caches key on method+URL and can't honor RFC 10008 §2.7's body-inclusive
cache key. Matches jeswr's Chrome+Firefox measurement in whatwg/fetch#1938.
Repro: `local/cache_test.py`.

## Attribution

The core observations behind the two footguns (fetch can send QUERY; lowercase
normalization gap; browsers don't cache QUERY) are documented in
[whatwg/fetch#1938](https://github.com/whatwg/fetch/issues/1938) (jeswr,
2026-06-30). This repo independently reproduces them and adds the server-side
consequences (uvicorn 400, the cross-client matrix). Findings #1 (edge bot
challenge) and #7 (edge pass-through) are, as of July 2026, not published anywhere else.

## Layout

- `local/` — lab servers and client scripts (FastAPI echo, CORS pair, raw-http, Express/Fastify probe, browser cache probe, the parser test, the decisive GET/POST/QUERY isolation burst)
- `vercel/` — the deployed Vercel project (Python + Node echo functions, cacheable endpoint)
- `supabase/functions/query-echo/` — the Deno echo function
- `assets/cover.png` — post cover

## Reproduce

```bash
python local/parser_test.py          # h11 vs httptools on lowercase/unknown methods
node   local/decisive.mjs            # the GET/POST/QUERY bot-mitigation isolation
python local/server.py 8600 && curl -X QUERY http://127.0.0.1:8600/echo -d '{"q":"hi"}'
```
