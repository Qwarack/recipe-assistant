import re

URL_PATTERN = re.compile(
    r"https?://[^\s<>]+",
    flags=re.IGNORECASE,
)


def extract_first_url(message: str) -> str | None:
    match = URL_PATTERN.search(message)

    if match is None:
        return None

    url = match.group(0)

    return url.rstrip(".,;:!?)]}")
