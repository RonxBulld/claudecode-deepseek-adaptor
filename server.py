"""
ccadaptor — Fix Anthropic ↔ DeepSeek API incompatibilities.

A transparent proxy that normalises Claude Code's Anthropic-format requests
for DeepSeek's /anthropic endpoint.  Fixups include:

  1. thinking.type: "adaptive" → "enabled"
  2. thinking: strip display field
  3. thinking: strip budget_tokens
  4. strip temperature/top_p/top_k when thinking is active
  5. strip reasoning_effort when thinking is disabled
  6. output_config: keep only effort

Everything else — API key, headers, streaming responses — is passed through.

Zero dependencies: uses only Python standard library.

Usage:
    python server.py

Then configure Claude Code:
    ANTHROPIC_BASE_URL=http://127.0.0.1:8089
"""

import json
import os
import sys
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fixups import apply_all as apply_fixups

DEBUG = os.environ.get("CCADAPTOR_DEBUG", "0") == "1"

UPSTREAM_URL = os.environ.get(
    "UPSTREAM_URL", "https://api.deepseek.com/anthropic"
)
PROXY_PORT = int(os.environ.get("PROXY_PORT", "8089"))
PROXY_HOST = os.environ.get("PROXY_HOST", "127.0.0.1")

HOP_BY_HOP = {
    "host", "content-length", "content-encoding",
    "transfer-encoding", "connection", "keep-alive", "proxy-connection",
    "upgrade", "te", "trailer",
}


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class ProxyHandler(BaseHTTPRequestHandler):

    def _forward(self):
        """Read request, apply fixups, forward to upstream, stream back."""
        # ── Read request body ─────────────────────────────────────────
        body_bytes = b""
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length > 0:
            body_bytes = self.rfile.read(content_length)

        # ── Build upstream headers ────────────────────────────────────
        upstream_headers = {}
        for key, value in self.headers.items():
            if key.lower() not in HOP_BY_HOP:
                upstream_headers[key] = value

        # ── Apply fixups to JSON bodies ───────────────────────────────
        if body_bytes:
            try:
                body = json.loads(body_bytes)
                if DEBUG:
                    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                    print(f"\n[{ts}] REQUEST {self.command} {self.path}", file=sys.stderr)
                    print(f"  model={body.get('model')!r}", file=sys.stderr)
                    print(f"  thinking={body.get('thinking')!r}", file=sys.stderr)
                    print(f"  reasoning_effort={body.get('reasoning_effort')!r}", file=sys.stderr)
                fixed = apply_fixups(body)
                if DEBUG and fixed is not body:
                    print(f"  → fixups applied (thinking={fixed.get('thinking')!r}, reasoning_effort={fixed.get('reasoning_effort')!r})", file=sys.stderr)
                body = fixed
                body_bytes = json.dumps(body).encode("utf-8")
            except (json.JSONDecodeError, TypeError):
                pass

        # ── Forward to upstream ───────────────────────────────────────
        target_url = f"{UPSTREAM_URL}{self.path}"
        req = Request(
            url=target_url,
            data=body_bytes if body_bytes else None,
            headers=upstream_headers,
            method=self.command,
        )

        try:
            resp = urlopen(req, timeout=300)
        except HTTPError as e:
            err_body = e.read()
            if DEBUG:
                print(f"  → HTTP {e.code}: {err_body.decode('utf-8', errors='replace')[:500]}", file=sys.stderr)
            self.send_response(e.code)
            self.end_headers()
            self.wfile.write(err_body)
            return
        except URLError as e:
            self.send_response(502)
            self.end_headers()
            self.wfile.write(f"Upstream error: {e.reason}".encode())
            return

        # ── Stream response back ──────────────────────────────────────
        self.send_response(resp.status)
        content_type = resp.headers.get("Content-Type", "application/json")
        self.send_header("Content-Type", content_type)
        self.end_headers()

        # Stream in chunks so SSE works
        while True:
            chunk = resp.read(4096)
            if not chunk:
                break
            self.wfile.write(chunk)
            self.wfile.flush()

    # Handle all HTTP methods the same way
    do_GET = _forward
    do_POST = _forward
    do_PUT = _forward
    do_DELETE = _forward
    do_PATCH = _forward
    do_OPTIONS = _forward
    do_HEAD = _forward

    def log_message(self, format, *args):
        """Suppress default access logging."""
        pass


def main():
    server = ThreadingHTTPServer((PROXY_HOST, PROXY_PORT), ProxyHandler)

    print(f"\n🚀 ccadaptor on http://{PROXY_HOST}:{PROXY_PORT}")
    print(f"   Upstream: {UPSTREAM_URL}")
    print(f"   Fixups:")
    print(f"     1. thinking: adaptive → enabled")
    print(f"     2. thinking: strip display field")
    print(f"     3. resolve thinking=disabled conflicts (model-agnostic)")
    print(f"     4. output_config: keep only effort")
    print(f"   Pass-through (per DeepSeek docs):")
    print(f"     - budget_tokens (ignored)")
    print(f"     - temperature, top_p (fully supported)")
    print(f"     - top_k (ignored)")
    print(f"   Debug: CCADAPTOR_DEBUG=1 for request logging")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
