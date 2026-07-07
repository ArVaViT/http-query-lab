#!/bin/bash
# Real proxy behavior toward QUERY: nginx / Varnish / HAProxy in front of an echo
# that reports the method the ORIGIN actually received.
set +e

cat >/tmp/echo.py <<'PY'
import socket, threading
def handle(c):
    try:
        c.settimeout(3); d=b""
        while b"\r\n\r\n" not in d:
            x=c.recv(1024)
            if not x: break
            d+=x
        m=d.split(b" ",1)[0].decode("latin1") if d else "?"
        cl=0
        for ln in d.split(b"\r\n\r\n",1)[0].split(b"\r\n"):
            if ln.lower().startswith(b"content-length:"): cl=int(ln.split(b":",1)[1].strip() or 0)
        have=len(d.split(b"\r\n\r\n",1)[1]) if b"\r\n\r\n" in d else 0
        while have<cl:
            x=c.recv(4096)
            if not x: break
            have+=len(x)
        p=("origin-saw:"+m).encode()
        c.sendall(b"HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n\r\n%s"%(len(p),p))
    except Exception: pass
    finally: c.close()
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",9000)); s.listen(50)
while True:
    conn,_=s.accept(); threading.Thread(target=handle,args=(conn,),daemon=True).start()
PY
pkill -f echo.py 2>/dev/null; python3 /tmp/echo.py & sleep 1

# nginx (default forwarder)
cat >/etc/nginx/sites-available/default <<'NG'
server { listen 8081; location / { proxy_pass http://127.0.0.1:9000; proxy_http_version 1.1; } }
NG
nginx -s stop 2>/dev/null; sleep 1; nginx 2>/dev/null; sleep 1

# varnish (default builtin VCL -> tests pipe/pass behavior for unknown methods)
cat >/tmp/default.vcl <<'VCL'
vcl 4.1;
backend default { .host="127.0.0.1"; .port="9000"; }
VCL
pkill varnishd 2>/dev/null; sleep 1; varnishd -a 127.0.0.1:8082 -f /tmp/default.vcl -s malloc,50m 2>/dev/null; sleep 2

# haproxy
cat >/tmp/haproxy.cfg <<'HA'
defaults
  mode http
  timeout connect 5s
  timeout client 5s
  timeout server 5s
frontend f
  bind 127.0.0.1:8083
  default_backend b
backend b
  server s1 127.0.0.1:9000
HA
pkill haproxy 2>/dev/null; sleep 1; haproxy -f /tmp/haproxy.cfg -D 2>/dev/null; sleep 1

probe() {
  local name=$1 hostport=$2
  echo "=== $name ($hostport) ==="
  for m in GET QUERY PROPFIND; do
    code=$(curl -s -o /tmp/body -w "%{http_code}" --max-time 6 -X $m "http://$hostport/" --data 'x')
    echo "  $m -> HTTP $code  $(head -c 60 /tmp/body)"
  done
}
probe "direct echo" "127.0.0.1:9000"
probe "nginx" "127.0.0.1:8081"
probe "varnish" "127.0.0.1:8082"
probe "haproxy" "127.0.0.1:8083"

pkill varnishd 2>/dev/null; pkill haproxy 2>/dev/null; nginx -s stop 2>/dev/null; pkill -f echo.py 2>/dev/null
echo DONE
