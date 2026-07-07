"""Browser matrix v2: persistent context (real on-disk cache) so the GET control
actually caches, giving a VALID WebKit result. Resolves the v1 WebKit inconclusive."""
import json
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8650"

JS = """
async () => {
  const out = {};
  await fetch('/reset', {method:'POST'});
  // warm + measure: 3 identical QUERY and 3 identical GET, spaced, count server hits
  for (let i=0;i<3;i++){ await fetch('/cq', {method:'QUERY', body:'{"q":"c"}', headers:{'content-type':'application/json'}}); await new Promise(r=>setTimeout(r,300)); }
  for (let i=0;i<3;i++){ await fetch('/cg'); await new Promise(r=>setTimeout(r,300)); }
  const hits = await (await fetch('/hits')).json();
  out.query_server_hits = hits.cq;  // 3 = never cached
  out.get_server_hits = hits.cg;    // <3 = cached (control WORKS)
  out.query_cached = hits.cq < 3;
  out.get_cached = hits.cg < 3;
  out.control_valid = hits.cg < 3;  // only trust query result if GET actually cached
  return out;
}
"""

srv = subprocess.Popen([sys.executable, "bm_server.py"])
time.sleep(4)
results = {}
try:
    with sync_playwright() as p:
        for name, launcher in [("chromium", p.chromium), ("firefox", p.firefox), ("webkit", p.webkit)]:
            udd = tempfile.mkdtemp(prefix=f"pw-{name}-")
            try:
                ctx = launcher.launch_persistent_context(udd, headless=True)
                page = ctx.pages[0] if ctx.pages else ctx.new_page()
                page.goto(BASE + "/", wait_until="domcontentloaded")
                results[name] = page.evaluate(JS)
                ctx.close()
            except Exception as e:  # noqa
                results[name] = {"ENGINE_ERROR": str(e)[:120]}
finally:
    srv.terminate(); srv.wait()

print(json.dumps(results, indent=2))
print("\n=== SUMMARY (persistent cache) ===")
for eng, r in results.items():
    if "ENGINE_ERROR" in r:
        print(f"  {eng:9} ERROR: {r['ENGINE_ERROR']}"); continue
    valid = "VALID" if r.get("control_valid") else "INVALID (GET didn't cache)"
    print(f"  {eng:9} GET hits={r['get_server_hits']} QUERY hits={r['query_server_hits']} "
          f"-> QUERY cached={r['query_cached']} | control {valid}")
