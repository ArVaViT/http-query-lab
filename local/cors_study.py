"""GAP: cross-origin QUERY reality. QUERY is not CORS-safelisted, so it ALWAYS
preflights. Test whether a server's Access-Control-Allow-Methods actually gates it,
across Chromium/Firefox/WebKit. Page origin :8710 -> API origin :8711."""
import http.server
import json
import socketserver
import threading
import time

PAGE_ORIGIN = "http://127.0.0.1:8710"

# path -> (acam, allow_credentials)
CFG = {
    "/allow-query": ("GET, POST, QUERY", False),
    "/deny":        ("GET, POST", False),          # QUERY not listed -> should block
    "/star":        ("*", False),                   # wildcard, non-credentialed
    "/star-cred":   ("*", True),                    # wildcard + credentials -> invalid -> block
    "/query-cred":  ("GET, POST, QUERY", True),     # explicit + credentials -> allow
}


class API(http.server.BaseHTTPRequestHandler):
    def _cors(self):
        acam, cred = CFG.get(self.path, ("GET, POST", False))
        self.send_header("Access-Control-Allow-Origin", PAGE_ORIGIN if cred else "*")
        self.send_header("Access-Control-Allow-Methods", acam)
        self.send_header("Access-Control-Allow-Headers", "content-type")
        if cred:
            self.send_header("Access-Control-Allow-Credentials", "true")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_QUERY(self):
        length = int(self.headers.get("content-length") or 0)
        self.rfile.read(length)
        body = json.dumps({"ok": True, "method": self.command}).encode()
        self.send_response(200)
        self._cors()
        self.send_header("content-type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class PAGE(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>cors</title>ok")

    def log_message(self, *a):
        pass


class T(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


threading.Thread(target=T(("127.0.0.1", 8711), API).serve_forever, daemon=True).start()
threading.Thread(target=T(("127.0.0.1", 8710), PAGE).serve_forever, daemon=True).start()
time.sleep(1)

JS = """
async () => {
  const api = 'http://127.0.0.1:8711';
  async function tryQ(path, creds) {
    try {
      const r = await fetch(api + path, {method:'QUERY', body:'{"q":1}',
        headers:{'content-type':'application/json'}, credentials: creds ? 'include' : 'omit'});
      const j = await r.json();
      return 'OK ' + r.status + ' (' + j.method + ')';
    } catch (e) { return 'BLOCKED (' + e.name + ')'; }
  }
  return {
    'ACAM lists QUERY':        await tryQ('/allow-query', false),
    'ACAM GET,POST (no QUERY)': await tryQ('/deny', false),
    'ACAM * (no creds)':       await tryQ('/star', false),
    'ACAM * + credentials':    await tryQ('/star-cred', true),
    'ACAM QUERY + credentials':await tryQ('/query-cred', true),
  };
}
"""

from playwright.sync_api import sync_playwright

results = {}
with sync_playwright() as p:
    for name, launcher in [("chromium", p.chromium), ("firefox", p.firefox), ("webkit", p.webkit)]:
        try:
            b = launcher.launch(headless=True)
            pg = b.new_page()
            pg.goto(PAGE_ORIGIN + "/", wait_until="domcontentloaded")
            results[name] = pg.evaluate(JS)
            b.close()
        except Exception as e:  # noqa
            results[name] = {"ERR": str(e)[:80]}

cases = list(next(iter(results.values())).keys())
print(f"{'case':28} | " + " | ".join(f"{e:>22}" for e in results))
print("-" * 100)
for c in cases:
    print(f"{c:28} | " + " | ".join(f"{results[eng].get(c,'?'):>22}" for eng in results))
