"""QUERY is safe+idempotent, so it SHOULD be auto-retriable. But retry allowlists are
hardcoded. Does urllib3's default Retry retry QUERY? (default allowed_methods excludes it)."""
import http.server
import socketserver
import threading
import time

import urllib3

HITS = {"n": 0}


class Flaky(http.server.BaseHTTPRequestHandler):
    def _do(self):
        HITS["n"] += 1
        # fail the first 2 attempts, succeed on the 3rd
        code = 200 if HITS["n"] >= 3 else 503
        self.send_response(code)
        self.send_header("content-length", "0")
        self.end_headers()

    def do_GET(self):
        self._do()

    def do_QUERY(self):
        self._do()

    def log_message(self, *a):
        pass


class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


threading.Thread(target=T(("127.0.0.1", 8700), Flaky).serve_forever, daemon=True).start()
time.sleep(1)
URL = "http://127.0.0.1:8700/"


def attempt(method, allowed):
    HITS["n"] = 0
    pool = urllib3.PoolManager()
    retry = urllib3.Retry(total=5, status_forcelist=[503],
                          allowed_methods=allowed, backoff_factor=0)
    try:
        r = pool.request(method, URL, retries=retry, body=b'{"q":1}' if method != "GET" else None)
        return f"final {r.status} after {HITS['n']} server hits (retried: {'YES' if HITS['n'] > 1 else 'NO'})"
    except Exception as e:  # noqa
        return f"FAILED after {HITS['n']} hits: {type(e).__name__} (retried: {'YES' if HITS['n'] > 1 else 'NO'})"


print("urllib3 DEFAULT allowed_methods:", set(urllib3.Retry.DEFAULT_ALLOWED_METHODS))
print("  QUERY in default allowlist?", "QUERY" in urllib3.Retry.DEFAULT_ALLOWED_METHODS)
print()
print("GET   (default allowlist)      ->", attempt("GET", urllib3.Retry.DEFAULT_ALLOWED_METHODS))
print("QUERY (default allowlist)      ->", attempt("QUERY", urllib3.Retry.DEFAULT_ALLOWED_METHODS))
print("QUERY (allowlist WITH QUERY)   ->", attempt("QUERY", frozenset({"QUERY", "GET"})))
