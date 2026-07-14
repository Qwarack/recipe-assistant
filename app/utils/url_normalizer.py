from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMETERS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
}


def normalize_url(url: str) -> str:
    parts = urlsplit(url)

    scheme = parts.scheme.lower()
    hostname = (parts.hostname or "").lower()

    port = parts.port
    if port is not None and not (
        scheme == "http" and port == 80 or scheme == "https" and port == 443
    ):
        netloc = f"{hostname}:{port}"
    else:
        netloc = hostname

    path = parts.path or "/"

    if path != "/":
        path = path.rstrip("/")

    query_parameters = [
        (key, value)
        for key, value in parse_qsl(
            parts.query,
            keep_blank_values=True,
        )
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMETERS
    ]

    query_parameters.sort()
    query = urlencode(query_parameters)

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            query,
            "",
        )
    )
