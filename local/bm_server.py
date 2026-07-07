"""Local origin for the browser matrix (no CDN, no bot filter in the path)."""
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse

app = FastAPI()
HITS = {"cq": 0, "cg": 0}


@app.get("/")
async def index() -> HTMLResponse:
    return HTMLResponse("<!doctype html><title>bm</title><body>ok</body>")


@app.api_route("/echo", methods=["QUERY", "GET", "POST"])
async def echo(request: Request) -> JSONResponse:
    body = (await request.body()).decode("utf-8", "replace")
    return JSONResponse({"method": request.method, "body": body},
                        headers={"access-control-allow-origin": "*"})


@app.api_route("/cq", methods=["QUERY"])
async def cq() -> JSONResponse:
    HITS["cq"] += 1
    return JSONResponse({"n": HITS["cq"]}, headers={"Cache-Control": "public, max-age=300"})


@app.get("/cg")
async def cg() -> JSONResponse:
    HITS["cg"] += 1
    return JSONResponse({"n": HITS["cg"]}, headers={"Cache-Control": "public, max-age=300"})


@app.post("/reset")
async def reset() -> Response:
    HITS["cq"] = 0
    HITS["cg"] = 0
    return Response(status_code=204)


@app.get("/hits")
async def hits() -> JSONResponse:
    return JSONResponse(dict(HITS))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8650, log_level="critical")
