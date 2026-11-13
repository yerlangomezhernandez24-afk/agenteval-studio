"""Real loopback HTTP test double, never evidence of real model inference."""

import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Thread

MODEL = {
    "name": "synthetic-test:tiny",
    "digest": "a" * 64,
    "size": 1024,
    "modified_at": "2026-11-06T00:00:00+00:00",
    "details": {"family": "test"},
}
RAW = json.dumps(
    {
        "category": "network",
        "priority": "high",
        "requires_human": True,
        "summary": "Synthetic HTTP double: VPN soporte",
    }
)


class Double:
    def __init__(self):
        self.requests = []
        self.models = [MODEL]
        self.outputs = [RAW, "{malformed", ""]
        self.delay = 0
        self.entered = Event()
        self.release = Event()
        self.status = 200
        self.headers = {}
        self.raw = None
        self.response_overrides = {}


@contextmanager
def serve_double():
    state = Double()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond()

        def do_POST(self):
            self.respond()

        def respond(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            payload = json.loads(body) if body else None
            state.requests.append((self.command, self.path, payload))
            if self.path == "/api/tags":
                data = {"models": state.models}
            elif self.path == "/api/version":
                data = {"version": "http-double-only"}
            elif self.path == "/api/generate":
                state.entered.set()
                if state.delay:
                    state.release.wait(state.delay)
                raw = state.outputs.pop(0) if len(state.outputs) > 1 else state.outputs[0]
                data = {
                    "model": MODEL["name"],
                    "done": True,
                    "response": raw,
                    "eval_count": 8,
                    "eval_duration": 1000,
                    "total_duration": 2000,
                    **state.response_overrides,
                }
            else:
                data = {"error": "forbidden endpoint"}
            encoded = state.raw if state.raw is not None else json.dumps(data).encode()
            self.send_response(state.status)
            for key, value in {
                "Content-Type": "application/json",
                "Content-Length": str(len(encoded)),
                **state.headers,
            }.items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(encoded)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        yield state, server.server_port
    finally:
        state.release.set()
        server.shutdown()
        server.server_close()
        worker.join(2)
