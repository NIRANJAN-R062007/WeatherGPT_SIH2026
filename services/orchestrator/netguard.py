"""Outbound-URL guard (SSRF defence) for user-supplied callback URLs.

`validate_public_https_url` accepts a URL only if it is https, has no embedded
credentials, is not absurdly long, and its host resolves exclusively to public
addresses. Call it when the URL is stored AND again right before each request
(DNS can change between the two — rebinding).

`allow_private=True` is a local-dev escape hatch: http and non-public hosts are
permitted and no DNS lookup is done. Length and credential checks still apply.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlsplit

MAX_URL_LENGTH = 2048


class UnsafeURLError(ValueError):
    pass


def _is_public(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return not (
        addr.is_private or addr.is_loopback or addr.is_link_local
        or addr.is_multicast or addr.is_reserved or addr.is_unspecified
        or not addr.is_global
    )


def _resolve(host: str, port: int) -> list[str]:
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return [info[4][0] for info in infos]


def url_host(url: str) -> str:
    """Hostname only, for logging (never the path/query, which may hold tokens)."""
    try:
        return urlsplit(url).hostname or "?"
    except ValueError:
        return "?"


def validate_public_https_url(url: str, allow_private: bool = False) -> str:
    """Returns `url` if safe, else raises UnsafeURLError."""
    if not isinstance(url, str) or not url:
        raise UnsafeURLError("url is required")
    if len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError(f"url longer than {MAX_URL_LENGTH} characters")
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError as exc:
        raise UnsafeURLError("malformed url") from exc
    allowed_schemes = ("https", "http") if allow_private else ("https",)
    if parts.scheme not in allowed_schemes:
        raise UnsafeURLError("url must use https")
    if parts.username is not None or parts.password is not None:
        raise UnsafeURLError("url must not contain credentials")
    if not host:
        raise UnsafeURLError("url has no host")
    if allow_private:
        return url

    try:
        literal = ipaddress.ip_address(host)
        addrs = [literal]
    except ValueError:
        try:
            resolved = _resolve(host, port or 443)
        except (socket.gaierror, UnicodeError, OSError) as exc:
            raise UnsafeURLError("host does not resolve") from exc
        try:
            addrs = [ipaddress.ip_address(a.split("%", 1)[0]) for a in resolved]
        except ValueError as exc:
            raise UnsafeURLError("host resolved to an invalid address") from exc
    if not addrs:
        raise UnsafeURLError("host does not resolve")
    if not all(_is_public(a) for a in addrs):
        raise UnsafeURLError("url host is not a public address")
    return url
