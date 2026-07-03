"""Cacheable endpoint: does the Vercel CDN cache a QUERY response like a GET?"""
import json
import time
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def _respond(self) -> None:
        payload = json.dumps(
            {"method": self.command, "generated_at": time.time()}
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("cache-control", "public, max-age=0, s-maxage=300")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._respond()

    def do_QUERY(self) -> None:
        self._respond()
