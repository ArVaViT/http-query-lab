"""USABLE ARTIFACT: run HTTP QUERY today, even behind edges that block it.
- Server middleware: accept native QUERY, OR POST + `X-HTTP-Method-Override: QUERY`.
- Smart client: try native QUERY; if an intermediary rejects it (400/403/405),
  transparently retry as POST + override. The edge only ever sees POST (which every
  CDN forwards), while your app still handles it as a QUERY.
Demonstrated against (a) a clean origin and (b) a simulated method-blocking edge."""
import http.server
import json
import socketserver
import threading
import time
import urllib.error
import urllib.request

OVERRIDE = "X-HTTP-Method-Override"


# ---------- ORIGIN: a QUERY endpoint + override-aware middleware ----------
class Origin(http.server.BaseHTTPRequestHandler):
    def _effective_method(self):
        # middleware: POST + override header is treated as the overridden method
        ov = self.headers.get(OVERRIDE)
        if self.command == "POST" and ov:
            return ov.upper()
        return self.command

    def _handle(self):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode() if length else ""
        method = self._effective_method()
        if method == "QUERY":
            payload = json.dumps({"handled_as": "QUERY", "wire_method": self.command, "query": body}).encode()
            self.send_response(200)
        else:
            payload = json.dumps({"error": "only QUERY", "got": method}).encode()
            self.send_response(405)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_QUERY = _handle
    do_POST = _handle

    def log_message(self, *a):
        pass


# ---------- SIMULATED EDGE: blocks QUERY (405), forwards POST ----------
class BlockingEdge(http.server.BaseHTTPRequestHandler):
    def _proxy(self):
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length)
        if self.command not in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            # exactly what CloudFront/Akamai/Netlify do to QUERY: reject at the edge
            self.send_response(405)
            self.end_headers()
            self.wfile.write(b'{"edge":"method not allowed"}')
            return
        req = urllib.request.Request("http://127.0.0.1:8680" + self.path, data=body, method=self.command)
        for h in (OVERRIDE, "content-type"):
            if self.headers.get(h):
                req.add_header(h, self.headers.get(h))
        try:
            with urllib.request.urlopen(req) as r:
                payload, code = r.read(), r.status
        except urllib.error.HTTPError as e:
            payload, code = e.read(), e.code
        self.send_response(code)
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    do_QUERY = _proxy
    do_POST = _proxy
    do_GET = _proxy

    def log_message(self, *a):
        pass


# ---------- SMART CLIENT: native QUERY, fall back to POST+override ----------
def query(url, body: bytes):
    def _send(method, extra=None):
        req = urllib.request.Request(url, data=body, method=method,
                                     headers={"content-type": "application/json", **(extra or {})})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    status, text = _send("QUERY")
    if status in (400, 403, 405):  # intermediary rejected the verb -> fall back
        status, text = _send("POST", {OVERRIDE: "QUERY"})
        return "fell back to POST+override", status, text
    return "native QUERY", status, text


class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


origin = T(("127.0.0.1", 8680), Origin)
edge = T(("127.0.0.1", 8681), BlockingEdge)
threading.Thread(target=origin.serve_forever, daemon=True).start()
threading.Thread(target=edge.serve_forever, daemon=True).start()
time.sleep(1)

BODY = b'{"filter": {"geo": "within 5km", "tags": ["a","b"]}}'
print("=== A) direct to a QUERY-capable origin (no blocking edge) ===")
print("  ", query("http://127.0.0.1:8680/search", BODY))
print("\n=== B) through an edge that BLOCKS QUERY (like CloudFront/Akamai/Netlify) ===")
print("  ", query("http://127.0.0.1:8681/search", BODY))
print("\nThe edge only ever saw POST (which every CDN forwards); the app still handled a QUERY.")
origin.shutdown()
edge.shutdown()
