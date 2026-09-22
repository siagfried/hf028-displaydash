#!/usr/bin/env python3
"""Local, non-sensitive HomeProxy subscription fixture for migration drills."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


GIB = 1024 ** 3


class SubscriptionFixture(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    DATA = {
        "/alpha": ("Lab-Alpha", 2 * GIB, 8 * GIB, 40 * GIB, 1798761600),
        "/bravo": ("Lab-Bravo", 5 * GIB, 11 * GIB, 60 * GIB, 1804032000),
    }

    def do_GET(self):
        if self.path == "/broken":
            self.send_error(503, "intentional migration-test failure")
            return
        item = self.DATA.get(self.path)
        if not item:
            self.send_error(404)
            return
        name, upload, download, total, expire = item
        body = b"proxies: []\n"
        self.send_response(200)
        self.send_header(
            "Subscription-Userinfo",
            f"upload={upload}; download={download}; total={total}; expire={expire}",
        )
        self.send_header("Content-Disposition", f"attachment; filename={name}")
        self.send_header("Content-Type", "text/yaml")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        print("fixture: " + (fmt % args), flush=True)


if __name__ == "__main__":
    ThreadingHTTPServer(("192.168.56.1", 18081), SubscriptionFixture).serve_forever()
