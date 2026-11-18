"""Alert webhooks: validated when saved, delivered with timeouts and no redirects.

A webhook URL is operator-supplied, so it is an SSRF vector: only http(s) is accepted, and
unless WEBHOOK_ALLOW_PRIVATE_HOSTS is on, every address the host resolves to must be public
(loopback, link-local, private and metadata ranges are refused). The check runs again at
delivery time, because DNS can change after the URL was saved.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlsplit

import anyio
import httpx

from tokenprofiler.core import metrics
from tokenprofiler.core.config import Settings
from tokenprofiler.core.errors import UnprocessableError
from tokenprofiler.core.logging import get_logger

log = get_logger("tokenprofiler.webhooks")


def _public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    return ip.is_global and not ip.is_multicast


async def validate_webhook_url(url: str, settings: Settings) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise UnprocessableError("Use an http(s) URL.", code="invalid_webhook")
    if settings.webhook_allow_private_hosts:
        return
    host = parts.hostname
    port = parts.port or (443 if parts.scheme == "https" else 80)
    try:
        infos = await anyio.to_thread.run_sync(
            socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM
        )
    except OSError as exc:
        raise UnprocessableError("That host does not resolve.", code="invalid_webhook") from exc
    if not infos or not all(_public(str(info[4][0])) for info in infos):
        raise UnprocessableError(
            "The webhook must point at a public address.", code="invalid_webhook"
        )


async def deliver(
    client: httpx.AsyncClient, settings: Settings, url: str, payload: dict[str, Any]
) -> str | None:
    """POST the payload. Returns None on success, otherwise a short reason."""
    try:
        await validate_webhook_url(url, settings)
        response = await client.post(url, json=payload)
        if response.status_code >= 400:
            metrics.WEBHOOKS.labels("http_error").inc()
            return f"HTTP {response.status_code}"
    except UnprocessableError as exc:
        metrics.WEBHOOKS.labels("blocked").inc()
        return exc.message[:200]
    except httpx.HTTPError as exc:
        metrics.WEBHOOKS.labels("failed").inc()
        log.warning("webhook_failed", error=type(exc).__name__)
        return type(exc).__name__
    metrics.WEBHOOKS.labels("ok").inc()
    return None
