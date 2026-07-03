"""Second-origin server (:8602 permissive CORS, :8603 no CORS) for preflight tests."""
import sys

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()
WITH_CORS = "--cors" in sys.argv


@app.options("/echo")
async def preflight(request: Request) -> Response:
    if not WITH_CORS:
        return Response(status_code=204)  # no CORS headers at all
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "QUERY, GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "content-type",
        },
    )


@app.api_route("/echo", methods=["QUERY", "GET", "POST"])
async def echo(request: Request) -> JSONResponse:
    body = (await request.body()).decode("utf-8", "replace")
    headers = {"Access-Control-Allow-Origin": "*"} if WITH_CORS else {}
    return JSONResponse({"method": request.method, "body": body}, headers=headers)


if __name__ == "__main__":
    import uvicorn

    port = int(sys.argv[1]) if sys.argv[1:] and sys.argv[1].isdigit() else 8602
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
