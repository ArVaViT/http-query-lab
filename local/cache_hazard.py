"""TEST for H2: RFC 10008 section 4 warns that a cache normalizing QUERY content
differently than the origin can serve a WRONG response (false-positive hit).
Demonstrate the safety/efficiency trade-off with two cache strategies against an
origin whose result DEPENDS on exact bytes."""
import hashlib
import json
import re

# Origin: treats the body as JSON and returns a result that depends on VALUE.
# Crucially, it is whitespace-insensitive (parses JSON) BUT key-order-sensitive in
# a way a naive normalizer could get wrong. We keep it simple: result = a + b.
def origin(body: bytes):
    d = json.loads(body)
    return {"sum": d["a"] + d["b"]}


# --- Strategy 1: exact-bytes key (safe, per our PoC) ---
def key_exact(body: bytes):
    return hashlib.sha256(body).hexdigest()


# --- Strategy 2: "smart" normalizer that strips ALL whitespace (efficient, risky) ---
def key_normalized(body: bytes):
    return hashlib.sha256(re.sub(rb"\s+", b"", body)).hexdigest()


def run(strategy, name):
    cache = {}
    log = []

    def req(body):
        k = strategy(body)
        if k in cache:
            return "HIT ", cache[k]
        res = origin(body)
        cache[k] = res
        return "MISS", res

    print(f"\n=== {name} ===")
    cases = [
        b'{"a": 1, "b": 2}',          # sum 3
        b'{"a": 1,  "b": 2}',         # same meaning, extra space -> should be same answer
        b'{"a": 10, "b": 2}',         # sum 12, different value
    ]
    for c in cases:
        tag, res = req(c)
        print(f"  {tag}  body={c!r:28} -> {res}")


# Both strategies are correct here because origin IS whitespace-insensitive.
run(key_exact, "Strategy 1: exact-bytes key (SAFE but inefficient)")
run(key_normalized, "Strategy 2: whitespace-normalized key (efficient)")

# Now the DANGER: an origin that is NOT whitespace-insensitive (e.g. treats the raw
# body as an opaque token / signature / different content-type). Then the normalizer
# collapses two DIFFERENT requests to one key and serves a wrong cached answer.
print("\n=== H2 HAZARD: origin where bytes matter (e.g. signed/opaque body) ===")

def origin_bytes_matter(body: bytes):
    # result is a function of the EXACT bytes (imagine an HMAC or a base64 blob)
    return {"digest": hashlib.md5(body).hexdigest()[:8]}

cache = {}
def req_norm(body):
    k = key_normalized(body)
    if k in cache:
        return "HIT ", cache[k]
    res = origin_bytes_matter(body)
    cache[k] = res
    return "MISS", res

b1 = b'{"sig": "a b"}'
b2 = b'{"sig": "ab"}'   # different meaning to the origin, SAME after whitespace-strip
print(f"  origin digest(b1)={origin_bytes_matter(b1)['digest']}  digest(b2)={origin_bytes_matter(b2)['digest']}  (genuinely different)")
print(f"  {req_norm(b1)[0]}  b1={b1!r} -> {cache[key_normalized(b1)]}")
tag, res = req_norm(b2)
print(f"  {tag}  b2={b2!r} -> {res}   <-- served b1's answer for b2! WRONG (RFC 10008 s4 false positive)")
