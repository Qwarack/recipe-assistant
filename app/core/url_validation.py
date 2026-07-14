import ipaddress
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
        return url

    if not ip.is_global:
        raise UnsafeUrlError("Private or non-public IP addresses are not allowed")

    return url
