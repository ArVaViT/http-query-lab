"""Rigorous confirmation: is it the QUERY METHOD or just burst VOLUME that
trips Vercel's default bot mitigation? Test from fresh client fingerprints,
each doing exactly one method, QUERY-first (no GET priming)."""
import time

import httpx

URL = "https://http-query-lab.vercel.app/api/echo"


def burst(method: str, n: int, gap: float) -> list:
    codes = []
    # brand-new client (fresh connection pool / TLS) per burst
    with httpx.Client(timeout=20) as c:
        for _ in range(n):
            try:
                if method == "GET":
                    r = c.get(URL)
                else:
                    r = c.request(
                        method, URL, content=b'{"q":"confirm"}',
                        headers={"content-type": "application/json"},
                    )
                codes.append(r.status_code)
            except Exception as e:  # noqa: BLE001
                codes.append(f"ERR:{type(e).__name__}")
            time.sleep(gap)
    return codes


# 1. QUERY-first from a clean fingerprint — no GET burst before it.
print("QUERY-first x12 (fresh client, no priming):", burst("QUERY", 12, 0.4))
time.sleep(20)
# 2. Independent fresh client, GET-only, same cadence — volume control.
print("GET-only  x12 (fresh client):            ", burst("GET", 12, 0.4))
