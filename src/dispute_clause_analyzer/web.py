"""Runs the connector online: the same tools over HTTPS, for claude.ai and the Claude apps.

Start with `clause-analyser-web` and these settings (the Dockerfile and render.yaml set them):
- CLAUSE_ANALYSER_MODE=online   leaves out the tools that save to the user's Downloads folder (see server.py)
- PUBLIC_HOST                   the public address, e.g. clause-analyser.onrender.com; other addresses are refused
- RATE_LIMIT_PER_MINUTE         requests one person may send a minute (default 60)
- PORT                          set by the hosting service
Clause text is used only to answer the request: it is never stored or logged.
"""
from __future__ import annotations

import os
import time
from collections import deque
from typing import Callable

from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp, Receive, Scope, Send

from dispute_clause_analyzer import server as tools

MCP_PATH = "/mcp"
HEALTH_PATH = "/health"
DEFAULT_RATE_LIMIT = 60
WINDOW_SECONDS = 60.0
MAX_SESSIONS = 1000
DEFAULT_PORT = 8000
LOCAL_HOSTS = ("localhost:*", "127.0.0.1:*")


@tools.server.custom_route(HEALTH_PATH, methods=["GET"])
async def health(_: Request) -> Response:
    """For the hosting service's health check."""
    return JSONResponse({"status": "ok"})


def _client_ip(scope: Scope) -> str:
    """The visitor's address; behind the hosting service's proxy it is the first X-Forwarded-For entry."""
    for name, value in scope.get("headers", []):
        if name == b"x-forwarded-for":
            return value.decode("latin-1").split(",")[0].strip()
    client = scope.get("client")
    return client[0] if client else "unknown"


class RateLimit:
    """Lets each visitor send at most `per_minute` requests a minute, so one person cannot overload the server."""

    def __init__(self, app: ASGIApp, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.app = app
        self.per_minute = per_minute
        self.clock = clock
        self.recent: dict[str, deque[float]] = {}

    def _allowed(self, ip: str) -> bool:
        now = self.clock()
        hits = self.recent.setdefault(ip, deque())
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= self.per_minute:
            return False
        hits.append(now)
        return True

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["path"] != HEALTH_PATH and not self._allowed(_client_ip(scope)):
            busy = JSONResponse({"error": "Too many requests. Please wait a minute and try again."},
                                status_code=429, headers={"Retry-After": str(int(WINDOW_SECONDS))})
            await busy(scope, receive, send)
            return
        await self.app(scope, receive, send)


def _public_host() -> str:
    host = os.environ.get("PUBLIC_HOST", "").strip()
    if not host:
        raise RuntimeError("Set PUBLIC_HOST to the connector's public address, e.g. clause-analyser.onrender.com.")
    return host


def create_app() -> ASGIApp:
    """The web app the hosting service runs: the MCP endpoint at /mcp, a health page, and the rate limit."""
    if not tools.HOSTED:
        raise RuntimeError("Set CLAUSE_ANALYSER_MODE=online to run the connector online.")
    host = _public_host()
    security = TransportSecuritySettings(
        allowed_hosts=[host, *LOCAL_HOSTS],
        allowed_origins=[f"https://{host}", "http://localhost:*", "http://127.0.0.1:*"],
    )
    app = tools.server.streamable_http_app(
        streamable_http_path=MCP_PATH, transport_security=security, max_sessions=MAX_SESSIONS, host="0.0.0.0",
    )
    return RateLimit(app, int(os.environ.get("RATE_LIMIT_PER_MINUTE", DEFAULT_RATE_LIMIT)))


def main() -> None:
    import uvicorn

    uvicorn.run(create_app(), host="0.0.0.0", port=int(os.environ.get("PORT", DEFAULT_PORT)),
                proxy_headers=True, forwarded_allow_ips="*")


if __name__ == "__main__":
    main()
