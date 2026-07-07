# Follow-up research: how the modern edge treats HTTP QUERY (and its whole verb-class)

Second-wave experiments (2026-07-06/07) that go past the original post. Every number
here is measured; scripts are in `local/`. Where a clean test needs bursting an edge,
that was only done against our OWN origins (Vercel/Supabase); third-party CDNs were
probed at low single-request rate (pass-through mapping only, non-abusive).

## 1. Vercel challenges a verb CLASS, not QUERY specifically

Self-gated boundary map (`local/boundary_map.mjs`): before each method, poll GET until
the IP is provably clean (2× 200), then burst — so no cross-method contamination.

| Methods | Vercel edge | Supabase edge (control) |
|---|---|---|
| GET, POST, PUT, DELETE, PATCH, HEAD, OPTIONS | all clean | clean |
| QUERY, PROPFIND, SEARCH, REPORT, PURGE, MKCOL | **all challenged at request #3** | clean |

Every "uncommon / non-browser" verb trips `X-Vercel-Mitigated: challenge` at #3; every
standard verb passes. Supabase (Kong+Deno) passes all of them, so this is Vercel's edge,
not a parser or runtime issue. The challenge flag persists **~13 minutes** and applies to
every method (a challenged client gets 403 on GET too). Local parser control
(`local/parser_methods.py`): llhttp/h11 accept all these methods and reach the app, so
every edge 403/400/405 is an edge decision, not a parse rejection.

## 2. Cross-CDN taxonomy — three mechanisms across 10 edges

`local/cross_cdn*.mjs` + a 5-agent documentation review.

| Edge | QUERY at edge | Mechanism (documented) |
|---|---|---|
| **AWS CloudFront** | 403 "Invalid method" | **Hard method-allowlist.** Fixed 7-verb superset (GET/HEAD/OPTIONS/PUT/PATCH/POST/DELETE). QUERY/PROPFIND can **never** be allowed, by design. |
| **Akamai** | 400 (server=AkamaiGHost) | Edge rejects. **Akamai co-authored RFC 10008** and blocks QUERY at its own edge (confirmed on IBM, Cisco, Apple, microsoft.com). |
| **Google (GFE/ESF)** | 405 | Method not allowed at the frontend. |
| **Netlify** | 405 | Allowlist (static = GET/HEAD; other verbs need a function declaring them). |
| **Bunny CDN** | 405 | Method not allowed at edge. |
| **Vercel** | 403 challenge (on a burst) | **Bot-challenge.** Not an allowlist — a fingerprint/rate mitigation. Method-as-trigger is **undocumented**; single low-rate requests can pass. |
| **Cloudflare** | forwarded | No default edge block. Opt-in WAF "Anomaly:Method" rules exist but are OFF by default (discord.com even 200s QUERY). |
| **Fastly** | forwarded | Preserves `req.method`, routes novel verbs to the origin (origin then returns 5xx/405). |
| **Fly.io** | forwarded | Proxy forwards to origin. |

Takeaway: **most major edges block novel HTTP methods, but by three different mechanisms**
(hard allowlist / bot-challenge / forward-to-origin), and only the forwarders let QUERY
reach your code. If you adopt QUERY, your CDN is the deciding variable, and CloudFront /
Akamai will stop it before your server ever sees it.

## 3. Browsers: all three engines send QUERY, none cache it

`local/browser_matrix2.py` (Playwright, persistent on-disk cache so the GET control is valid):

| Engine | Sends QUERY (fetch + XHR) | GET cached (control) | QUERY cached |
|---|---|---|---|
| Chromium | yes | yes | **no** |
| Firefox | yes | yes | **no** |
| WebKit (Safari) | yes | yes | **no** |

Extends whatwg/fetch#1938 (which measured only Chrome + Firefox) to WebKit, with a valid
cached-GET control in every engine.

## 4. A working QUERY cache (the thing nothing ships yet)

`local/query_cache_proxy.py` — a ~40-line reverse-proxy cache that keys on
`(method, path, sha256(body))` per RFC 10008 §2.7:

```
QUERY {a:1} -> MISS->origin (hit 1)
QUERY {a:1} -> cache HIT          (identical body)
QUERY {a:2} -> MISS->origin (hit 2)   (different body = miss; body IS in the key)
QUERY {a:1} -> cache HIT
QUERY {a:1} -> MISS->origin (hit 3)   (after max-age expiry)
5 QUERY requests, origin hit 3 times.
```

The "cacheable" promise of QUERY is trivially implementable. Browsers and CDNs just
haven't, because their cache keys are (method, URL) and can't yet incorporate a body.

## 5. Rate dependence (in progress)

Open question: is the Vercel challenge purely burst-rate, or method-driven at any speed?
Preliminary: QUERY spaced at 30s still draws challenges (noisy, some slip through), which
argues against "slow traffic is safe." Full rate sweep + stability repeats pending
(`local/rate_dependence.mjs`). Not concluding until replicated.
