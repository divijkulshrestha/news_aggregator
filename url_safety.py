"""Shared SSRF guard for RSS feed URLs.

Used both at persistence time (backend/app.py, when a feed is added/updated)
and at fetch time (etl/ingest_and_process.py, right before every request) so
that a hostname resolving safely at save-time but to an internal address at
fetch-time (DNS rebinding) is still blocked.
"""
import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}


class UnsafeFeedUrlError(ValueError):
    """Raised when a feed URL fails scheme or IP-range validation."""


def _is_private_address(ip_str: str) -> bool:
    ip = ipaddress.ip_address(ip_str)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_feed_url(url: str) -> None:
    """Raise UnsafeFeedUrlError if the URL is not a safe public http(s) URL.

    Validates scheme and resolves the hostname, rejecting any address that
    lands in a private, loopback, link-local, multicast, reserved, or
    unspecified range.
    """
    parsed = urlparse(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeFeedUrlError(f"URL scheme must be http or https, got: {parsed.scheme!r}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeFeedUrlError("URL must include a hostname")

    try:
        addrinfo = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise UnsafeFeedUrlError(f"Could not resolve hostname: {hostname!r}") from e

    for family, _, _, _, sockaddr in addrinfo:
        ip_str = sockaddr[0]
        if _is_private_address(ip_str):
            raise UnsafeFeedUrlError(
                f"Feed URL resolves to a disallowed address ({ip_str}); "
                "internal/private/loopback addresses are not permitted"
            )
