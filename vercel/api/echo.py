"""Vercel Python function: echo the HTTP method and body (QUERY-aware)."""
import json
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def _echo(self) -> None:
        length = int(self.headers.get("content-length") or 0)
        body = self.rfile.read(length).decode("utf-8", "replace") if length else ""
        payload = json.dumps(
            {
                "runtime": "python",
                "method": self.command,
                "body": body,
                "via": self.headers.get("x-vercel-id", ""),
            }
        ).encode()
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "QUERY, GET, POST, OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self) -> None:
        self._echo()

    def do_POST(self) -> None:
        self._echo()

    def do_QUERY(self) -> None:
        self._echo()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("access-control-allow-origin", "*")
        self.send_header("access-control-allow-methods", "QUERY, GET, POST, OPTIONS")
        self.send_header("access-control-allow-headers", "content-type")
        self.end_headers()
