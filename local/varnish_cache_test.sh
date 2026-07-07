#!/bin/bash
# Can a REAL cache (Varnish) cache QUERY, and if forced to, does it key on the BODY
# or just the URL? URL-only keying => two different-body QUERYs collide => the RFC 10008
# section 4 cache-poisoning hazard, live.
set +e

# Origin: echoes the received body + a monotonically increasing token, cacheable.
cat >/tmp/origin.py <<'PY'
import socket, threading
N=[0]
def handle(c):
    try:
        c.settimeout(3); d=b""
        while b"\r\n\r\n" not in d:
            x=c.recv(1024)
            if not x: break
            d+=x
        head=d.split(b"\r\n\r\n",1)[0]; m=d.split(b" ",1)[0].decode("latin1")
        cl=0
        for ln in head.split(b"\r\n"):
            if ln.lower().startswith(b"content-length:"): cl=int(ln.split(b":",1)[1].strip() or 0)
        body=d.split(b"\r\n\r\n",1)[1] if b"\r\n\r\n" in d else b""
        while len(body)<cl:
            x=c.recv(4096)
            if not x: break
            body+=x
        N[0]+=1
        p=("ORIGIN token#%d for body=%s"%(N[0], body.decode('latin1'))).encode()
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nCache-Control: public, max-age=60\r\nConnection: close\r\n\r\n%s"%(len(p),p))
    except Exception: pass
    finally: c.close()
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",9000)); s.listen(50)
while True:
    conn,_=s.accept(); threading.Thread(target=handle,args=(conn,),daemon=True).start()
PY
pkill -f origin.py 2>/dev/null; python3 /tmp/origin.py & sleep 1

# Varnish VCL: FORCE QUERY into the cache (default would pipe). Body is NOT in vcl_hash.
cat >/tmp/cache.vcl <<'VCL'
vcl 4.1;
backend default { .host="127.0.0.1"; .port="9000"; }
sub vcl_recv {
    if (req.method == "QUERY") {
        return (hash);   # force cacheable lookup instead of the default pipe
    }
}
sub vcl_backend_response {
    if (bereq.method == "QUERY") {
        set beresp.ttl = 60s;          # make the QUERY response cacheable
        set beresp.uncacheable = false;
    }
}
VCL
pkill varnishd 2>/dev/null; sleep 1
varnishd -a 127.0.0.1:8082 -f /tmp/cache.vcl -s malloc,50m 2>/dev/null; sleep 2

hit() { # method url body
  curl -s -D /tmp/h -o /tmp/b --max-time 6 -X "$1" "$2" --data "$3" -H 'content-type: application/json'
  local xc=$(grep -i '^x-varnish\|^age:' /tmp/h | tr -d '\r' | paste -sd' ')
  echo "   $1 body=$3 -> $(cat /tmp/b)   [$xc]"
}

echo "=== sanity: direct to origin (bypass Varnish) — body SHOULD be visible ==="
hit QUERY "http://127.0.0.1:9000/search" '{"a":1}'
echo "=== Varnish forced to cache QUERY (key = URL, body NOT hashed) ==="
hit QUERY "http://127.0.0.1:8082/search" '{"a":1}'
hit QUERY "http://127.0.0.1:8082/search" '{"a":1}'
echo "   ^ 2nd identical QUERY: same token => served from cache (correct dedupe)"
hit QUERY "http://127.0.0.1:8082/search" '{"a":999}'
echo "   ^ DIFFERENT body, SAME url: if token is still #1 => CACHE POISONING (RFC 10008 s4)"

pkill varnishd 2>/dev/null; pkill -f origin.py 2>/dev/null
echo DONE
