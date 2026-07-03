"""Does a browser's HTTP cache honor Cache-Control on QUERY responses?"""
import json

from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()
HITS = {"cq": 0, "cg": 0}
RESULT: dict = {}

PAGE = """<!doctype html>
<html><body><script>
async function run() {
  // two identical QUERY requests; server counts real hits
  for (let i = 0; i < 2; i++) {
    await fetch('/cq', {method: 'QUERY', body: '{"q":"same"}', headers: {'content-type':'application/json'}});
    await new Promise(r => setTimeout(r, 300));
  }
  // control: two identical GETs (should hit cache the 2nd time)
  for (let i = 0; i < 2; i++) {
    await fetch('/cg');
    await new Promise(r => setTimeout(r, 300));
  }
  await fetch('/done', {method: 'POST'});
}
run();
</script></body></html>"""


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse(PAGE)


@app.api_route("/cq", methods=["QUERY"])
async def cached_query(request: Request) -> JSONResponse:
    HITS["cq"] += 1
    return JSONResponse(
        {"n": HITS["cq"]},
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.get("/cg")
async def cached_get() -> JSONResponse:
    HITS["cg"] += 1
    return JSONResponse(
        {"n": HITS["cg"]},
        headers={"Cache-Control": "public, max-age=300"},
    )


@app.post("/done")
async def done() -> Response:
    RESULT.update(HITS)
    return Response(status_code=204)


@app.get("/hits")
async def hits() -> JSONResponse:
    return JSONResponse({"hits": HITS, "done": bool(RESULT)})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8604, log_level="warning")
