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

## 6. Why do edges block QUERY? (hypothesis-tested)

**H1 — edges block QUERY because it isn't in their method tables yet, not for security.**
Test (`local/method_age.mjs`): compare verbs by age with a garbage control, FOOBAR:
PROPFIND (1999) / SEARCH (2008) / QUERY (2026) / FOOBAR (never registered).

```
CloudFront   PROPFIND=403  SEARCH=403  QUERY=403  FOOBAR=403   (identical -> hard allowlist)
Akamai/cisco PROPFIND=501  SEARCH=400  QUERY=400  FOOBAR=400   (DISTINGUISHES)
Akamai/apple PROPFIND=403(origin)      QUERY=400  FOOBAR=400   (forwards known, kills unknown)
Cloudflare   PROPFIND=200  SEARCH=200  QUERY=200  FOOBAR=501   (forwards registered, rejects garbage)
Google/Netlify/Bunny  all 405 (no distinction)
Fastly       PROPFIND=405  SEARCH=502  QUERY=502  FOOBAR=502   (origin-dependent)
```

The FOOBAR control is the clincher: on the "method-table" edges, **QUERY is treated like the
garbage verb FOOBAR, not like the old-but-known PROPFIND.** Akamai is the clearest case: it
returns `501 Not Implemented` for PROPFIND (a verb it knows) but `400 Bad Request` for
QUERY/SEARCH/FOOBAR (tokens it doesn't). So QUERY is blocked because the edge's method table
predates June 2026, not because of any security policy. RFC 10008 says nothing about how
unrecognizing intermediaries should behave, and does not flag WAF/edge rejection at all
(read from the RFC text, §4 + §5) — the transition gap is real and unaddressed.

**Status code is itself diagnostic of the mechanism:**
`400` = can't parse the method (unknown token) · `501` = known method, not implemented ·
`405` = valid method, not allowed here · `403` = forbidden by policy / hard allowlist.

**H2 — QUERY caching has a real correctness hazard, it isn't only "unimplemented."**
RFC 10008 §4: "Caches that normalize QUERY content ... can return an incorrect response if
normalization results in a false positive." Demonstrated (`local/cache_hazard.py`): a cache
that normalizes whitespace in the body serves the answer for `{"sig":"a b"}` to a request for
`{"sig":"ab"}` when the origin treats the bytes as significant. Exact-body-hash keys (our PoC)
are safe but can't dedupe semantically-equal queries; "smart" normalization is efficient but
can serve the wrong response. This is a genuine reason browsers/CDNs punt on QUERY caching.

## 7. Rate dependence: slowing down does NOT help (Vercel)

`local/rate_dependence.mjs`, self-gated (clean IP before each window):

```
QUERY @ 30s interval -> challenge #1
QUERY @ 10s interval -> challenge #2
QUERY @  3s interval -> challenge #2
QUERY @ 0.4s (burst) -> challenge #3
```

QUERY draws the challenge within 1-2 requests from a clean IP at every rate down to
30-second spacing. So Vercel's mitigation is essentially method-driven, not just
burst-rate; any QUERY traffic is affected, not only floods. Behaviour is noisy /
probabilistic (occasional 200s slip through, e.g. `[200,200,403,...,200,200,403]`),
consistent with an adaptive fingerprint mitigation rather than a static allowlist.

## 8. Usable fix: run QUERY today, even behind blocking edges

`local/query_adapter_demo.py` — a transparent client fallback + server middleware:

- Client tries native QUERY; on a 400/403/405 from an intermediary, it retries as
  `POST` + `X-HTTP-Method-Override: QUERY`.
- Server middleware treats `POST` + that header as a QUERY.

```
Direct to origin:              native QUERY -> 200, handled_as QUERY (wire POST=QUERY)
Through a QUERY-blocking edge:  QUERY 405 -> falls back to POST+override -> 200, handled_as QUERY
```

The edge only ever sees POST (which every CDN forwards), while the app still handles a
QUERY. ~60 lines. This defeats the entire method-allowlist class of edge blocks today,
at the cost of losing native QUERY cacheability at the edge (the request is a POST on
the wire) — a fine trade until the edge method tables catch up.

## 9. Measured corrections (real tests beat doc-research)

**Client method normalization (measured on the wire, `local/norm_matrix.py` + `norm_clients.mjs`):**
sending the string `query` to each client, what actually hits the wire:

| Sends `query` verbatim (lowercase) | Uppercases to `QUERY` |
|---|---|
| fetch/undici, curl -X, Python urllib | Python requests, httpx, axios, got, Node http.request |

So there are **two** wire outcomes, not three. `fetch`/`undici` is the real bug magnet
(lowercase `query` != IANA `QUERY`). Doc-research had claimed httpx is "verbatim" and axios
"risks lowercase" — both WRONG by measurement: httpx and axios both uppercase to `QUERY`.

**Open-source proxies all FORWARD QUERY (real nginx/Varnish/HAProxy in WSL, `local/proxy_test.sh`):**

```
nginx    QUERY -> 200  origin-saw:QUERY
varnish  QUERY -> 200  origin-saw:QUERY   (forwarded via pipe; uncached, NOT blocked)
haproxy  QUERY -> 200  origin-saw:QUERY
```

Corrects the "Varnish breaks QUERY" framing: Varnish default-VCL *pipes* an unknown method
to the backend, so QUERY reaches the origin (just without caching) — it is not blocked. The
real blockers are the **proprietary managed edges** (CloudFront/Akamai/Google/Netlify/Bunny/
Vercel), not configurable open-source proxies. Refined thesis: *managed CDN blocks, open-source
infra forwards.*

**Server frameworks route AND read QUERY bodies** (`local/receive_side.*`): Express, Fastify
(after `addHttpMethod`), and FastAPI all route a QUERY request and read its body — the
"body-gated on POST/PUT" worry did not materialize. The origin side is ready; the edge is the gap.
