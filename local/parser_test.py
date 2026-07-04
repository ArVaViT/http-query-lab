"""Decisive: WHICH parser rejects a lowercase method, and is it QUERY-specific?
Starts the same ASGI app under uvicorn --http h11 and --http httptools, then
sends exact method bytes via raw socket (QUERY, query, GET, get, FROBNICATE)."""
import socket
import subprocess
import sys
import time

APP = "raw_app:app"
APP_CODE = '''
async def app(scope, receive, send):
    assert scope["type"] == "http"
    await send({"type": "http.response.start", "status": 200,
                "headers": [(b"content-type", b"text/plain")]})
    await send({"type": "http.response.body",
                "body": scope["method"].encode()})
'''

with open("raw_app.py", "w") as f:
    f.write(APP_CODE)


def raw_request(port: int, method_bytes: bytes) -> str:
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=5)
        s.sendall(method_bytes + b" /x HTTP/1.1\r\nHost: t\r\nContent-Length: 0\r\n\r\n")
        data = s.recv(400)
        s.close()
        first = data.split(b"\r\n")[0].decode(errors="replace")
        # body (echoed method) if 200
        body = data.split(b"\r\n\r\n", 1)[1].decode(errors="replace") if b"\r\n\r\n" in data else ""
        return f"{first}  body={body!r}"
    except Exception as e:  # noqa: BLE001
        return f"ERR {type(e).__name__}: {e}"


python = sys.executable
for parser, port in (("h11", 8630), ("httptools", 8631)):
    proc = subprocess.Popen(
        [python, "-m", "uvicorn", APP, "--http", parser, "--port", str(port), "--log-level", "critical"],
    )
    time.sleep(3)
    print(f"\n=== uvicorn --http {parser} (:{port}) ===")
    for m in (b"QUERY", b"query", b"GET", b"get", b"FROBNICATE"):
        print(f"  {m.decode():11} -> {raw_request(port, m)}")
    proc.terminate()
    proc.wait()
