"""Bounded direct loopback HTTP. No proxies, redirects, downloads or cloud routes."""

import http.client
import io
import json
import select
import socket
from datetime import datetime
from threading import Event, Lock, Timer
from time import monotonic
from typing import Any

from pydantic import ValidationError

from agenteval.io import parse_json
from agenteval.local_models import GenerationOptions, ModelInfo, Provenance, TransportCode


class OllamaFailure(Exception):
    def __init__(self, code: TransportCode):
        self.code = code
        super().__init__(code)


class OllamaClient:
    def __init__(self) -> None:
        self._host = "127.0.0.1"
        self._port = 11434
        self.provenance: Provenance = "local_ollama"
        self._lock = Lock()
        self._active: dict[http.client.HTTPConnection, socket.socket | None] = {}

    @classmethod
    def for_test_server(cls, port: int) -> "OllamaClient":
        if type(port) is not int or not 1024 <= port <= 65535 or port == 11434:
            raise ValueError("Dedicated unprivileged test port required")
        client = cls()
        client._port = port
        client.provenance = "http_test_double"
        return client

    @staticmethod
    def _abort(
        connection: http.client.HTTPConnection, connected: socket.socket | None = None
    ) -> None:
        try:
            target = connected or connection.sock
            if target is not None:
                target.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        # The owning worker closes the connection in finally. Closing it here
        # would race HTTPConnection.request's access to its socket attribute.

    def cancel(self) -> None:
        with self._lock:
            for connection, connected in tuple(self._active.items()):
                self._abort(connection, connected)

    def _request(
        self,
        path: str,
        payload: dict[str, Any] | None = None,
        *,
        cancel: Event | None = None,
        timeout: float = 3,
    ) -> dict[str, Any]:
        if self._host != "127.0.0.1" or not (
            self._port == 11434
            if self.provenance == "local_ollama"
            else 1024 <= self._port <= 65535 and self._port != 11434
        ):
            raise OllamaFailure("invalid_response")
        if path not in {"/api/tags", "/api/version", "/api/generate"}:
            raise OllamaFailure("invalid_response")
        if (path == "/api/generate") != (payload is not None) or not 0 < timeout <= 30:
            raise OllamaFailure("invalid_response")
        if cancel is not None and cancel.is_set():
            raise OllamaFailure("cancelled")
        connection = http.client.HTTPConnection(self._host, self._port, timeout=min(2, timeout))
        timed_out = Event()
        deadline = monotonic() + timeout

        def expire() -> None:
            timed_out.set()
            self._abort(connection, self._active.get(connection))

        timer = Timer(timeout, expire)
        timer.daemon = True
        with self._lock:
            self._active[connection] = None
        timer.start()

        class BoundedReader(io.RawIOBase):
            def __init__(self, connected: socket.socket) -> None:
                self.connected = connected.dup()

            def close(self) -> None:
                self.connected.close()
                super().close()

            def readable(self) -> bool:
                return True

            def readinto(self, buffer: Any) -> int:
                while True:
                    if cancel is not None and cancel.is_set():
                        raise OllamaFailure("cancelled")
                    remaining = deadline - monotonic()
                    if remaining <= 0 or timed_out.is_set():
                        raise OllamaFailure("timeout")
                    ready, _, _ = select.select([self.connected], [], [], min(0.1, remaining))
                    if ready:
                        return self.connected.recv_into(buffer)

        class BoundedResponse(http.client.HTTPResponse):
            def __init__(self, sock: socket.socket, **kwargs: Any) -> None:
                super().__init__(sock, **kwargs)
                if self.fp is not None:
                    self.fp.close()
                self.fp = io.BufferedReader(BoundedReader(sock))

        connection.response_class = BoundedResponse
        response: http.client.HTTPResponse | None = None
        try:
            connection.connect()
            with self._lock:
                self._active[connection] = connection.sock
            connection.auto_open = 0
            if timed_out.is_set():
                raise OllamaFailure("timeout")
            if cancel is not None and cancel.is_set():
                raise OllamaFailure("cancelled")
            if connection.sock is not None:
                connection.sock.settimeout(max(0.001, deadline - monotonic()))
            body = json.dumps(payload).encode() if payload is not None else None
            if body is not None and len(body) > 16_000:
                raise OllamaFailure("limit_exceeded")
            connection.request(
                "POST" if payload is not None else "GET",
                path,
                body=body,
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status != 200:
                raise OllamaFailure("http_error")  # never follow redirects or echo body
            headers = response.getheaders()
            if len(headers) > 32 or sum(len(k) + len(v) for k, v in headers) > 8192:
                raise OllamaFailure("limit_exceeded")
            for name in ("content-length", "content-type", "transfer-encoding"):
                if sum(k.lower() == name for k, _ in headers) > 1:
                    raise OllamaFailure("invalid_response")
            if response.getheader("Content-Encoding", "identity") != "identity":
                raise OllamaFailure("invalid_response")
            if response.getheader("Set-Cookie") or response.getheader("Location"):
                raise OllamaFailure("invalid_response")
            if response.getheader("Content-Type", "").split(";")[0].strip() != "application/json":
                raise OllamaFailure("invalid_response")
            length = response.getheader("Content-Length")
            transfer = response.getheader("Transfer-Encoding")
            if transfer and (transfer.lower() != "chunked" or length is not None):
                raise OllamaFailure("invalid_response")
            if length is not None and (not length.isdecimal() or int(length) > 65_536):
                raise OllamaFailure("limit_exceeded")
            raw = response.read(65_537)
            if len(raw) > 65_536:
                raise OllamaFailure("limit_exceeded")
            if length is not None and len(raw) != int(length):
                raise OllamaFailure("invalid_response")
            if cancel is not None and cancel.is_set():
                raise OllamaFailure("cancelled")
            if timed_out.is_set():
                raise OllamaFailure("timeout")
            result = parse_json(raw.decode("utf-8"))
            if not isinstance(result, dict) or "error" in result:
                raise OllamaFailure("invalid_response")
            # JSON escapes may contain lone surrogates, invalid in later UTF-8
            # API serialization and snapshot hashes. Reject them at the boundary.
            json.dumps(result, ensure_ascii=False).encode("utf-8")
            return result
        except OllamaFailure:
            raise
        except (OSError, http.client.HTTPException) as exc:
            code: TransportCode = "connection_error"
            if cancel is not None and cancel.is_set():
                code = "cancelled"
            elif timed_out.is_set() or isinstance(exc, TimeoutError):
                code = "timeout"
            elif isinstance(exc, http.client.HTTPException):
                code = "invalid_response"
            raise OllamaFailure(code) from None
        except (ValueError, TypeError, RecursionError):
            raise OllamaFailure("invalid_response") from None
        finally:
            timer.cancel()
            if response is not None:
                response.close()
            connection.close()
            with self._lock:
                self._active.pop(connection, None)

    def models(self, cancel: Event | None = None) -> list[ModelInfo]:
        data = self._request("/api/tags", cancel=cancel)
        items = data.get("models")
        if not isinstance(items, list) or len(items) > 100:
            raise OllamaFailure("invalid_response")
        result = []
        try:
            for item in items:
                if not isinstance(item, dict):
                    raise ValueError("Invalid model record")
                # A remote model is not an installed local model, even if tags lists it.
                name = item.get("name")
                if not isinstance(name, str) or len(name) > 128:
                    raise ValueError("Invalid model name")
                if item.get("remote_host") or item.get("remote_model") or "cloud" in name.lower():
                    continue
                details = item.get("details", {})
                if not isinstance(details, dict):
                    raise ValueError("Invalid details")
                info = ModelInfo(
                    name=name,
                    digest=item["digest"],
                    size=item["size"],
                    modified_at=item["modified_at"],
                    family=details.get("family", ""),
                    parameter_size=details.get("parameter_size", ""),
                    quantization_level=details.get("quantization_level", ""),
                )
                if datetime.fromisoformat(info.modified_at).utcoffset() is None:
                    raise ValueError("Timestamp missing timezone")
                result.append(info)
            if len({item.name for item in result}) != len(result):
                raise ValueError("Duplicate model names")
        except (ValueError, TypeError, KeyError, ValidationError):
            raise OllamaFailure("invalid_response") from None
        return result

    def version(self) -> str | None:
        try:
            value = self._request("/api/version").get("version")
            return value if isinstance(value, str) and 0 < len(value) <= 80 else None
        except OllamaFailure:
            return None

    def generate(
        self,
        model: ModelInfo,
        prompt: str,
        input_text: str,
        options: GenerationOptions,
        cancel: Event,
    ) -> dict[str, Any]:
        current = {item.name: item for item in self.models(cancel)}
        if model.name not in current or current[model.name].digest != model.digest:
            raise OllamaFailure("invalid_response")
        result = self._request(
            "/api/generate",
            {
                "model": model.name,
                "system": prompt,
                "prompt": input_text,
                "stream": False,
                "format": "json",
                "keep_alive": 0,
                "options": options.model_dump(),
            },
            cancel=cancel,
            timeout=30,
        )
        raw = result.get("response")
        if (
            result.get("model") != model.name
            or result.get("done") is not True
            or not isinstance(raw, str)
        ):
            raise OllamaFailure("invalid_response")
        if len(raw.encode("utf-8")) > 16_000:
            raise OllamaFailure("limit_exceeded")
        for name in ("eval_count", "eval_duration", "total_duration"):
            value = result.get(name)
            maximum = options.num_predict if name == "eval_count" else 120_000_000_000
            if value is not None and (type(value) is not int or not 0 <= value <= maximum):
                raise OllamaFailure("invalid_response")
        return {
            key: result.get(key)
            for key in ("response", "eval_count", "eval_duration", "total_duration")
        }
