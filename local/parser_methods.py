"""Control: which HTTP methods does the parser ACCEPT (reach the app) vs reject?
So we can interpret a Vercel 403 as bot-filter, not a parse-level rejection.
Sends exact method bytes via raw socket to uvicorn under both parsers."""
import socket
import subprocess
import sys
import time

APP_CODE = '''
async def app(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": scope["method"].encode()})
'''
with open("raw_app.py", "w") as f:
    f.write(APP_CODE)

METHODS = [b"GET", b"POST", b"PUT", b"DELETE", b"PATCH", b"HEAD", b"OPTIONS",
           b"QUERY", b"PROPFIND", b"SEARCH", b"REPORT", b"PURGE", b"MKCOL",
           b"FROBNICATE"]


def probe(port, method):
    try:
        s = socket.create_connection(("127.0.0.1", port), timeout=4)
        s.sendall(method + b" /x HTTP/1.1\r\nHost: t\r\nContent-Length: 0\r\n\r\n")
        data = s.recv(300)
        s.close()
        status = data.split(b"\r\n")[0].decode(errors="replace")
        return status
    except Exception as e:  # noqa
        return f"ERR {type(e).__name__}"


py = sys.executable
for parser, port in (("httptools", 8641), ("h11", 8642)):
    proc = subprocess.Popen(
        [py, "-m", "uvicorn", "raw_app:app", "--http", parser, "--port", str(port), "--log-level", "critical"]
    )
    time.sleep(3)
    print(f"\n=== uvicorn --http {parser} ===")
    for m in METHODS:
        print(f"  {m.decode():12} -> {probe(port, m)}")
    proc.terminate()
    proc.wait()
