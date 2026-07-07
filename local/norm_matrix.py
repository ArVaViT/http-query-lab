"""Empirical HTTP method normalization matrix: send input 'query' and 'QUERY' from
every client to a raw echo that reports the EXACT wire method token. Measures what
each library actually puts on the wire (settles the axios dispute by measurement)."""
import socket
import subprocess
import sys
import threading
import time

PORT = 8695


def echo_conn(conn):
    try:
        conn.settimeout(3)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = conn.recv(1024)
            if not chunk:
                break
            data += chunk
        head = data.split(b"\r\n\r\n", 1)[0]
        first = head.split(b"\r\n", 1)[0]
        method = first.split(b" ", 1)[0].decode("latin1") if first else "?"
        # drain body per content-length
        clen = 0
        for line in head.split(b"\r\n"):
            if line.lower().startswith(b"content-length:"):
                clen = int(line.split(b":", 1)[1].strip() or 0)
        body_have = len(data.split(b"\r\n\r\n", 1)[1]) if b"\r\n\r\n" in data else 0
        while body_have < clen:
            c = conn.recv(min(4096, clen - body_have))
            if not c:
                break
            body_have += len(c)
        payload = method.encode()
        conn.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s" % (len(payload), payload))
    except Exception:  # noqa
        pass
    finally:
        conn.close()


def serve():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("127.0.0.1", PORT))
    s.listen(50)
    while True:
        conn, _ = s.accept()
        threading.Thread(target=echo_conn, args=(conn,), daemon=True).start()


threading.Thread(target=serve, daemon=True).start()
time.sleep(1)

URL = f"http://127.0.0.1:{PORT}/"
BODY = b'{"q":1}'
results = {}

# ---- Python clients ----
import urllib.request
import requests
import httpx

for m in ("query", "QUERY"):
    try:
        results.setdefault("python requests", {})[m] = requests.request(m, URL, data=BODY).text.strip()
    except Exception as e:  # noqa
        results.setdefault("python requests", {})[m] = "ERR:" + str(e)[:30]
    try:
        results.setdefault("python httpx", {})[m] = httpx.request(m, URL, content=BODY).text.strip()
    except Exception as e:  # noqa
        results.setdefault("python httpx", {})[m] = "ERR:" + str(e)[:30]
    try:
        req = urllib.request.Request(URL, data=BODY, method=m)
        results.setdefault("python urllib", {})[m] = urllib.request.urlopen(req).read().decode().strip()
    except Exception as e:  # noqa
        results.setdefault("python urllib", {})[m] = "ERR:" + str(e)[:30]

# ---- curl ----
for m in ("query", "QUERY"):
    r = subprocess.run(["curl", "-s", "-X", m, URL, "--data", "x"], capture_output=True, text=True)
    results.setdefault("curl -X", {})[m] = r.stdout.strip() or ("ERR:" + r.stderr.strip()[:30])

# ---- Node clients ----
try:
    import json
    r = subprocess.run(["node", "norm_clients.mjs"], capture_output=True, text=True, cwd=sys.path[0] or ".")
    node = json.loads(r.stdout.strip() or "{}")
    results.update(node)
except Exception as e:  # noqa
    results["node (all)"] = "ERR:" + str(e)[:60]

print(f"{'client':22} | input 'query' -> wire | input 'QUERY' -> wire")
print("-" * 66)
for c, v in results.items():
    if isinstance(v, dict):
        print(f"{c:22} | {str(v.get('query')):20} | {v.get('QUERY')}")
    else:
        print(f"{c:22} | {v}")
