"""Fail-closed outbound policy for tenant-configurable notification targets."""
from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from urllib.parse import urlparse, urlunsplit

from .config import settings


Resolver = Callable[[str, int], Awaitable[list[str]]]


@dataclass(frozen=True)
class PinnedHttpsTarget:
    request_url: str
    host_header: str
    sni_hostname: str
    peer_ip: str


def require_public_ip_address(raw_address: object) -> str:
    """Return a normalized public peer address or reject the connection.

    DNS validation alone is vulnerable to rebinding between the lookup and the
    socket connection.  Outbound callers must also verify the address of the
    socket that was actually connected before sending credentials or content.
    """

    value = str(raw_address or "").split("%", 1)[0]
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError("outbound connection peer cannot be verified") from exc
    if not address.is_global:
        raise ValueError("outbound connection resolved to a non-public peer")
    return str(address)


def require_public_httpx_peer(response: object) -> str:
    """Verify the peer exposed by an httpx/httpcore response."""

    extensions = getattr(response, "extensions", {}) or {}
    network_stream = extensions.get("network_stream")
    if network_stream is None:
        raise ValueError("outbound connection peer cannot be verified")
    try:
        peer = network_stream.get_extra_info("server_addr")
        raw_address = peer[0] if isinstance(peer, (tuple, list)) and peer else peer
    except (AttributeError, TypeError) as exc:
        raise ValueError("outbound connection peer cannot be verified") from exc
    return require_public_ip_address(raw_address)


def require_expected_httpx_peer(response: object, expected_ip: str) -> str:
    """Require the connected peer to equal the DNS answer selected for pinning."""

    actual = require_public_httpx_peer(response)
    try:
        expected = str(ipaddress.ip_address(str(expected_ip).split("%", 1)[0]))
    except ValueError as exc:
        raise ValueError("outbound expected peer is invalid") from exc
    if actual != expected:
        raise ValueError("outbound connection peer did not match the pinned address")
    return actual


def require_public_socket_peer(peer_socket: object) -> str:
    """Verify a connected SMTP/socket peer after TLS establishment."""

    try:
        peer = peer_socket.getpeername()
        raw_address = peer[0] if isinstance(peer, (tuple, list)) and peer else peer
    except (AttributeError, OSError, TypeError) as exc:
        raise ValueError("outbound connection peer cannot be verified") from exc
    return require_public_ip_address(raw_address)


class OutboundNetworkPolicy:
    _PROVIDER_HOSTS = {
        "feishu": {"open.feishu.cn", "open.larksuite.com"},
        "dingtalk": {"oapi.dingtalk.com"},
        "wechat_work": {"qyapi.weixin.qq.com"},
        "pushplus": {"www.pushplus.plus"},
    }
    _PROVIDER_PATHS = {
        "feishu": "/open-apis/bot/",
        "dingtalk": "/robot/send",
        "wechat_work": "/cgi-bin/webhook/send",
        "pushplus": "/send",
    }

    def __init__(self, webhook_hosts: str = "", smtp_hosts: str = "", resolver: Resolver | None = None):
        self.webhook_hosts = self._parse_hosts(webhook_hosts)
        self.smtp_hosts = self._parse_hosts(smtp_hosts)
        self.resolver = resolver or self._resolve

    async def validate_webhook(self, channel_type: str, raw_url: str) -> str:
        value = str(raw_url or "").strip()
        if not value or len(value) > 2048 or any(ord(char) < 32 for char in value):
            raise ValueError("notification URL is invalid")
        parsed = urlparse(value)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or (parsed.port not in (None, 443))
        ):
            raise ValueError("notification URL must use safe HTTPS")
        host = parsed.hostname.rstrip(".").lower()
        if self._is_local_hostname(host):
            raise ValueError("notification host is forbidden")

        channel_type = str(channel_type or "webhook").strip().lower()
        if channel_type == "webhook":
            if not self.webhook_hosts:
                raise ValueError("generic webhook allowlist is not configured")
            allowed = self.webhook_hosts
        elif channel_type in self._PROVIDER_HOSTS:
            allowed = self._PROVIDER_HOSTS[channel_type]
            if not parsed.path.startswith(self._PROVIDER_PATHS[channel_type]):
                raise ValueError("notification URL path does not match provider")
        else:
            raise ValueError("unsupported notification channel")
        if not self._host_allowed(host, allowed):
            raise ValueError("notification host is not allowlisted")
        await self._require_public_resolution(host, 443)
        return value

    async def pin_webhook(self, channel_type: str, raw_url: str) -> PinnedHttpsTarget:
        """Apply provider/allowlist policy and pin the final connection address."""

        safe_url = await self.validate_webhook(channel_type, raw_url)
        return await self.pin_public_https(safe_url)

    async def validate_public_https(self, raw_url: str) -> str:
        """Validate an arbitrary public HTTPS target without following redirects.

        This is intended for capabilities such as operator-requested image import
        where an allowlist is not practical.  Callers must still disable proxy
        inheritance and redirects, and must enforce response size/content limits.
        """

        value = str(raw_url or "").strip()
        if (
            not value
            or len(value) > 2048
            or "\\" in value
            or any(ord(char) <= 32 for char in value)
        ):
            raise ValueError("outbound URL is invalid")
        parsed = urlparse(value)
        if (
            parsed.scheme.lower() != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.fragment
            or (parsed.port not in (None, 443))
        ):
            raise ValueError("outbound URL must use safe HTTPS")
        try:
            host = parsed.hostname.encode("idna").decode("ascii").rstrip(".").lower()
        except UnicodeError as exc:
            raise ValueError("outbound host is invalid") from exc
        if self._is_local_hostname(host):
            raise ValueError("outbound host is forbidden")
        await self._require_public_resolution(host, 443)
        return value

    async def pin_public_https(self, raw_url: str) -> PinnedHttpsTarget:
        """Resolve once to a public IP and return an HTTPS request target pinned to it.

        Callers send the original hostname as both the HTTP Host header and TLS
        SNI extension, while the TCP connection is made to the validated IP.
        This closes the DNS lookup-to-connect rebinding window before secrets or
        request bodies are transmitted.
        """

        safe_url = await self.validate_public_https(raw_url)
        parsed = urlparse(safe_url)
        host = parsed.hostname.encode("idna").decode("ascii").rstrip(".").lower()
        addresses = await self._public_addresses(host, 443)
        peer_ip = addresses[0]
        request_host = f"[{peer_ip}]" if ":" in peer_ip else peer_ip
        request_url = urlunsplit(("https", request_host, parsed.path or "/", parsed.query, ""))
        return PinnedHttpsTarget(
            request_url=request_url,
            host_header=host,
            sni_hostname=host,
            peer_ip=peer_ip,
        )

    async def validate_smtp(self, raw_host: str, port: int) -> tuple[str, int]:
        host = str(raw_host or "").strip().rstrip(".").lower()
        try:
            port = int(port)
        except (TypeError, ValueError) as exc:
            raise ValueError("SMTP port is invalid") from exc
        if not host or self._is_local_hostname(host) or port not in (465, 587):
            raise ValueError("SMTP target is unsafe")
        if not self.smtp_hosts or not self._host_allowed(host, self.smtp_hosts):
            raise ValueError("SMTP host is not allowlisted")
        await self._require_public_resolution(host, port)
        return host, port

    async def _require_public_resolution(self, host: str, port: int) -> None:
        await self._public_addresses(host, port)

    async def _public_addresses(self, host: str, port: int) -> list[str]:
        addresses = await self.resolver(host, port)
        if not addresses:
            raise ValueError("notification host cannot be resolved")
        normalized: set[str] = set()
        for raw in addresses:
            try:
                address = ipaddress.ip_address(raw)
            except ValueError as exc:
                raise ValueError("notification host returned an invalid address") from exc
            if not address.is_global:
                raise ValueError("notification host resolves to a non-public address")
            normalized.add(str(address))
        return sorted(normalized)

    @staticmethod
    async def _resolve(host: str, port: int) -> list[str]:
        infos = await asyncio.to_thread(socket.getaddrinfo, host, port, 0, socket.SOCK_STREAM)
        return sorted({str(info[4][0]) for info in infos})

    @staticmethod
    def _parse_hosts(value: str) -> set[str]:
        return {
            item.strip().lower().removeprefix("*.").rstrip(".")
            for item in str(value or "").split(",")
            if item.strip()
        }

    @staticmethod
    def _host_allowed(host: str, allowed: set[str]) -> bool:
        return any(host == item or host.endswith(f".{item}") for item in allowed)

    @staticmethod
    def _is_local_hostname(host: str) -> bool:
        return host == "localhost" or host.endswith((".localhost", ".local", ".internal", ".home", ".lan"))


notification_outbound_policy = OutboundNetworkPolicy(
    settings.notification_webhook_allowed_hosts,
    settings.notification_smtp_allowed_hosts,
)

# Public URL imports use the same DNS/public-address enforcement but deliberately
# do not share notification allowlists.
public_https_outbound_policy = OutboundNetworkPolicy()


__all__ = [
    "OutboundNetworkPolicy",
    "PinnedHttpsTarget",
    "notification_outbound_policy",
    "public_https_outbound_policy",
    "require_expected_httpx_peer",
    "require_public_httpx_peer",
    "require_public_ip_address",
    "require_public_socket_peer",
]
