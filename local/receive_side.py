"""GAP #3: does FastAPI (and raw Starlette/ASGI) route QUERY AND read its body?"""
import subprocess
import sys
import threading
import time
import urllib.request

APP = '''
from fastapi import FastAPI, Request
app = FastAPI()

@app.api_route("/q", methods=["QUERY", "POST"])
async def q(request: Request):
    body = await request.body()
    return {"method": request.method, "body_len": len(body), "body": body.decode()}
'''
with open("recv_app.py", "w") as f:
    f.write(APP)

proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "recv_app:app", "--port", "8692", "--log-level", "critical"])
time.sleep(4)

BODY = b'{"filter":"x","n":42}'
req = urllib.request.Request("http://127.0.0.1:8692/q", data=BODY, method="QUERY",
                            headers={"content-type": "application/json"})
try:
    with urllib.request.urlopen(req) as r:
        import json
        res = json.load(r)
        print("FastAPI ->", res)
        print("BODY_READ:", "YES" if res["body_len"] == len(BODY) else f"NO ({res['body_len']})",
              "| ROUTED:", "YES" if res["method"] == "QUERY" else "NO")
except Exception as e:  # noqa
    print("FastAPI FAIL:", e)
finally:
    proc.terminate()
    proc.wait()
