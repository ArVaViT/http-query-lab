"""Proof-of-concept: a QUERY-aware shared cache (what no browser/CDN ships yet).
Per RFC 10008 section 2.7, the cache key MUST incorporate the request content.
We implement exactly that: key = (method, path, sha256(body)). Demonstrates a real
cache HIT on a repeated identical QUERY, a MISS on a different body (body-in-key),
and max-age expiry. ~40 lines of actual cache logic."""
import hashlib
import http.server
import re
import socketserver
import threading
import time
import urllib.request

ORIGIN_HITS = {"n": 0}


# ---------- origin: counts hits, returns a cacheable response ----------
class Origin(http.server.BaseHTTPRequestHandler):
    def _serve(self):
        length = int(self.headers.get("content-length") or 0)
        self.rfile.read(length)
        ORIGIN_HITS["n"] += 1
        body = f'{{"served_by":"origin","hit":{ORIGIN_HITS["n"]}}}'.encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "public, max-age=2")
        self.send_header("content-length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self._serve()

    def do_QUERY(self):
        self._serve()

    def log_message(self, *a):
        pass


# ---------- QUERY-aware caching proxy ----------
CACHE = {}  # key -> (expires_at, body)
CACHE_LOCK = threading.Lock()
ORIGIN = "http://127.0.0.1:8670"


def max_age(cc: str) -> int:
    m = re.search(r"max-age=(\d+)", cc or "")
    return int(m.group(1)) if m else 0


class Proxy(http.server.BaseHTTPRequestHandler):
    def _handle(self):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)
        # RFC 10008 section 2.7: cache key MUST incorporate the request content.
        key = (self.command, self.path, hashlib.sha256(body).hexdigest())
        now = time.time()
        with CACHE_LOCK:
            hit = CACHE.get(key)
            if hit and hit[0] > now:
                payload, served = hit[1], "proxy-cache-HIT"
                self._respond(payload, served)
                return
        # miss -> forward to origin
        req = urllib.request.Request(ORIGIN + self.path, data=body, method=self.command)
        with urllib.request.urlopen(req) as r:
            payload = r.read()
            ttl = max_age(r.headers.get("cache-control", ""))
        if ttl > 0:
            with CACHE_LOCK:
                CACHE[key] = (now + ttl, payload)
        self._respond(payload, "proxy-MISS->origin")

    def _respond(self, payload, served):
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("x-cache", served)
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _handle
    do_QUERY = _handle

    def log_message(self, *a):
        pass


class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def query(path, body):
    req = urllib.request.Request("http://127.0.0.1:8671" + path, data=body, method="QUERY")
    with urllib.request.urlopen(req) as r:
        return r.headers.get("x-cache"), r.read().decode()


origin = T(("127.0.0.1", 8670), Origin)
proxy = T(("127.0.0.1", 8671), Proxy)
threading.Thread(target=origin.serve_forever, daemon=True).start()
threading.Thread(target=proxy.serve_forever, daemon=True).start()
time.sleep(1)

print("=== QUERY through a QUERY-aware cache ===")
print("1. QUERY body={a:1} ->", query("/search", b'{"a":1}'))
print("2. QUERY body={a:1} ->", query("/search", b'{"a":1}'), "  <- identical, should HIT")
print("3. QUERY body={a:2} ->", query("/search", b'{"a":2}'), "  <- different body, should MISS (body-in-key)")
print("4. QUERY body={a:1} ->", query("/search", b'{"a":1}'), "  <- still within max-age, HIT")
print("   waiting 2.2s for max-age=2 to expire...")
time.sleep(2.2)
print("5. QUERY body={a:1} ->", query("/search", b'{"a":1}'), "  <- expired, should MISS")
print(f"\nOrigin was hit {ORIGIN_HITS['n']} times for 5 QUERY requests (2 identical served from cache).")
origin.shutdown()
proxy.shutdown()
