"""Local lab server for HTTP QUERY experiments (FastAPI/uvicorn/h11)."""
import json

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()

REPORTS: list[dict] = []

PAGE = """<!doctype html>
<html><body>
<script>
async function run() {
  const results = {};
  // 1. same-origin fetch with QUERY
  try {
    const r = await fetch('/echo', {method: 'QUERY', body: JSON.stringify({q: 'from-browser-fetch'}), headers: {'content-type': 'application/json'}});
    results.fetch_same_origin = {status: r.status, body: await r.json()};
  } catch (e) { results.fetch_same_origin = {error: String(e)}; }
  // 2. lowercase 'query' — fetch normalizes known methods only; what happens?
  try {
    const r = await fetch('/echo', {method: 'query', body: '{"q":"lowercase"}', headers: {'content-type': 'application/json'}});
    results.fetch_lowercase = {status: r.status, body: await r.json()};
  } catch (e) { results.fetch_lowercase = {error: String(e)}; }
  // 3. XMLHttpRequest with QUERY
  try {
    results.xhr = await new Promise((resolve) => {
      const x = new XMLHttpRequest();
      x.open('QUERY', '/echo');
      x.setRequestHeader('content-type', 'application/json');
      x.onload = () => resolve({status: x.status, body: x.responseText});
      x.onerror = () => resolve({error: 'xhr network error'});
      x.send('{"q":"from-xhr"}');
    });
  } catch (e) { results.xhr = {error: String(e)}; }
  // 4. cross-origin QUERY to :8602 (CORS server with permissive headers)
  try {
    const r = await fetch('http://127.0.0.1:8602/echo', {method: 'QUERY', body: '{"q":"cross-origin"}', headers: {'content-type': 'application/json'}});
    results.fetch_cross_origin_cors_ok = {status: r.status, body: await r.json()};
  } catch (e) { results.fetch_cross_origin_cors_ok = {error: String(e)}; }
  // 5. cross-origin QUERY to :8603 (NO cors headers) — expect preflight failure
  try {
    const r = await fetch('http://127.0.0.1:8603/echo', {method: 'QUERY', body: '{"q":"no-cors-hdrs"}'});
    results.fetch_cross_origin_no_cors = {status: r.status};
  } catch (e) { results.fetch_cross_origin_no_cors = {error: String(e)}; }
  await fetch('/report', {method: 'POST', body: JSON.stringify(results), headers: {'content-type': 'application/json'}});
  document.title = 'DONE';
}
run();
</script>
</body></html>"""


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


@app.api_route("/echo", methods=["QUERY", "GET", "POST"])
async def echo(request: Request) -> JSONResponse:
    body = (await request.body()).decode("utf-8", "replace")
    return JSONResponse({"method": request.method, "body": body})


@app.post("/report")
async def report(request: Request) -> Response:
    REPORTS.append(await request.json())
    return Response(status_code=204)


@app.get("/last-report")
async def last_report() -> JSONResponse:
    return JSONResponse(REPORTS[-1] if REPORTS else {"none": True})


if __name__ == "__main__":
    import sys

    import uvicorn

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8600
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
