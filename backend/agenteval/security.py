"""Exact loopback origins and a per-process CSRF capability; no cookies or CORS."""

from secrets import compare_digest, token_urlsafe

from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class WebPolicy:
    def __init__(self, port: int, dev_ui: bool) -> None:
        if not 1024 <= port <= 65535:
            raise ValueError("Use an unprivileged TCP port")
        self.authority = f"127.0.0.1:{port}"
        self.origins = {f"http://{self.authority}"}
        if dev_ui:
            self.origins.add("http://127.0.0.1:5173")
        self.token = token_urlsafe(32)

    def reject(self, request: Request) -> Response | None:
        def denied(code: str, status: int = 403) -> Response:
            return JSONResponse(
                {"detail": "Request rejected by local web policy", "code": code}, status_code=status
            )

        for header in (
            "host",
            "origin",
            "sec-fetch-site",
            "sec-fetch-mode",
            "sec-fetch-dest",
            "x-csrf-token",
        ):
            if len(request.headers.getlist(header)) > 1:
                return denied("ambiguous_headers", 400)
        if request.headers.get("host") != self.authority:
            return denied("invalid_host", 400)
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return denied("loopback_only")
        origin = request.headers.get("origin")
        if origin is not None and origin not in self.origins:
            return denied("invalid_origin")
        site = request.headers.get("sec-fetch-site")
        if site is not None and site not in {"same-origin", "none"}:
            return denied("cross_site")
        if request.headers.get("cookie") is not None or request.headers.get("authorization"):
            return denied("ambient_credentials_not_supported")
        if request.headers.get("forwarded") or request.headers.get("x-forwarded-host"):
            return denied("forwarded_authority_not_supported")
        path = request.url.path.removeprefix("/api")
        if path in {
            "/session",
            "/health",
            "/suite",
            "/runs",
            "/variants",
            "/comparisons",
            "/comparisons/export",
        } or path.startswith(("/runs/", "/ollama/")):
            if request.headers.get("sec-fetch-mode") in {"navigate", "no-cors"}:
                return denied("api_fetch_only")
            if request.headers.get("sec-fetch-dest", "empty") != "empty":
                return denied("api_fetch_only")
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            provided = request.headers.get("x-csrf-token", "")
            if not compare_digest(provided.encode("utf-8"), self.token.encode("ascii")):
                return denied("csrf_required")
        return None


def response_headers(response: Response) -> Response:
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; "
        "form-action 'self'"
    )
    return response
