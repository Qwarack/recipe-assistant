import ipaddress
import socket
from urllib.parse import urlparse


class UnsafeUrlError(ValueError):
    pass


def validate_public_http_url(url: str) -> str:
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise UnsafeUrlError("Only HTTP and HTTPS URLs are allowed")

    if not parsed.hostname:
        raise UnsafeUrlError("URL must contain a hostname")

    hostname = parsed.hostname.lower()

    if hostname == "localhost" or hostname.endswith(".localhost"):
        raise UnsafeUrlError("Localhost URLs are not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        validate_public_hostname(hostname)
    else:
        validate_public_ip(ip)

    return url


def validate_public_hostname(hostname: str) -> None:
    try:
        address_info = socket.getaddrinfo(
            hostname,
            None,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise UnsafeUrlError("Hostname could not be resolved") from exc

    resolved_ips = {ipaddress.ip_address(item[4][0]) for item in address_info}

    if not resolved_ips:
        raise UnsafeUrlError("Hostname did not resolve to an IP address")

    for ip in resolved_ips:
        validate_public_ip(ip)


def validate_public_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> None:
    if not ip.is_global:
        raise UnsafeUrlError("Private or non-public IP addresses are not allowed")
