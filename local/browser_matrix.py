"""Browser matrix: does each engine (Chromium, Firefox, WebKit) SEND QUERY and
CACHE it? Runs against a LOCAL origin (no CDN/bot-filter interference)."""
import json
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8650"

JS = """
async () => {
  const out = {};
  // 1. fetch same-origin QUERY
  try {
    const r = await fetch('/echo', {method:'QUERY', body:'{"q":"b"}', headers:{'content-type':'application/json'}});
    const j = await r.json();
    out.fetch_query = (r.status === 200 && j.method === 'QUERY') ? 'sends QUERY' : `status ${r.status} method ${j.method}`;
  } catch (e) { out.fetch_query = 'ERROR ' + e.message; }
  // 2. XHR QUERY
  try {
    out.xhr_query = await new Promise((res) => {
      const x = new XMLHttpRequest();
      x.open('QUERY', '/echo');
      x.onload = () => { try { res(JSON.parse(x.responseText).method === 'QUERY' ? 'sends QUERY' : 'other'); } catch { res('parse-fail'); } };
      x.onerror = () => res('xhr error');
      x.send('{"q":"x"}');
    });
  } catch (e) { out.xhr_query = 'ERROR ' + e.message; }
  // 3. cache: reset, then 2 identical QUERY and 2 identical GET
  await fetch('/reset', {method:'POST'});
  for (let i=0;i<2;i++){ await fetch('/cq', {method:'QUERY', body:'{"q":"c"}', headers:{'content-type':'application/json'}}); await new Promise(r=>setTimeout(r,250)); }
  for (let i=0;i<2;i++){ await fetch('/cg'); await new Promise(r=>setTimeout(r,250)); }
  const hits = await (await fetch('/hits')).json();
  out.query_server_hits = hits.cq;   // 2 = NOT cached, 1 = cached
  out.get_server_hits = hits.cg;     // control
  out.query_cached = hits.cq === 1;
  out.get_cached = hits.cg === 1;
  return out;
}
"""

srv = subprocess.Popen([sys.executable, "bm_server.py"])
time.sleep(4)
results = {}
try:
    with sync_playwright() as p:
        for name, launcher in [("chromium", p.chromium), ("firefox", p.firefox), ("webkit", p.webkit)]:
            try:
                b = launcher.launch(headless=True)
                page = b.new_page()
                page.goto(BASE + "/", wait_until="domcontentloaded")
                results[name] = page.evaluate(JS)
                b.close()
            except Exception as e:  # noqa
                results[name] = {"ENGINE_ERROR": str(e)}
finally:
    srv.terminate()
    srv.wait()

print(json.dumps(results, indent=2))
print("\n=== SUMMARY ===")
for eng, r in results.items():
    if "ENGINE_ERROR" in r:
        print(f"  {eng:9} ERROR: {r['ENGINE_ERROR'][:80]}")
        continue
    print(f"  {eng:9} fetch={r.get('fetch_query')}, xhr={r.get('xhr_query')}, "
          f"QUERY cached={r.get('query_cached')} (hits {r.get('query_server_hits')}), "
          f"GET cached={r.get('get_cached')} (hits {r.get('get_server_hits')})")
