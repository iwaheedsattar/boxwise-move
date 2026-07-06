from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .planner import build_plan, export_markdown, plan_to_dict


ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"


class BoxwiseHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send_file(STATIC / "index.html", "text/html; charset=utf-8")
            return
        if path == "/sample":
            self._send_file(ROOT.parent / "examples" / "starter-items.csv", "text/plain; charset=utf-8")
            return
        if path.startswith("/static/"):
            target = STATIC / path.removeprefix("/static/")
            content_type = "text/css" if target.suffix == ".css" else "application/javascript"
            self._send_file(target, content_type)
            return
        self.send_error(404)

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        length = int(self.headers.get("content-length", "0"))
        payload = json.loads(self.rfile.read(length) or b"{}")
        if path == "/api/plan":
            plan = build_plan(
                payload.get("items", ""),
                payload.get("moveDate") or None,
                payload.get("homeSize", "2 bedroom"),
            )
            self._send_json(plan_to_dict(plan))
            return
        if path == "/api/export":
            plan = build_plan(
                payload.get("items", ""),
                payload.get("moveDate") or None,
                payload.get("homeSize", "2 bedroom"),
            )
            self._send_text(export_markdown(plan), "text/markdown; charset=utf-8")
            return
        self.send_error(404)

    def log_message(self, fmt: str, *args: object) -> None:
        return

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_text(self, payload: str, content_type: str) -> None:
        data = payload.encode("utf-8")
        self.send_response(200)
        self.send_header("content-type", content_type)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Boxwise Move local planner.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8787, type=int)
    args = parser.parse_args()
    server = ThreadingHTTPServer((args.host, args.port), BoxwiseHandler)
    print(f"Boxwise Move is running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Boxwise Move")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

