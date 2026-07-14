import re
import unicodedata

NON_WORD_PATTERN = re.compile(r"[^\w\s-]")
WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_title(title: str) -> str:
    normalized = unicodedata.normalize("NFKC", title)
    normalized = normalized.casefold()
    normalized = NON_WORD_PATTERN.sub("", normalized)
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)

    return normalized.strip()
