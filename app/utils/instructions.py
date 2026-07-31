import re

_BULLET_PREFIX = re.compile(r"^\s*[-*•]\s+")
_NUMBER_PREFIX = re.compile(r"^\s*(?:\(\d{1,3}\)|\d{1,3}\s*[.):-])\s+")
_STEP_PREFIX = re.compile(
    r"^\s*(?:stap|step)\s+\d{1,3}(?:\s*[.):-])?\s+",
    flags=re.IGNORECASE,
)


def normalize_instruction_text(value: str) -> str:
    normalized = value.strip()

    while normalized:
        without_prefix = normalized
        for pattern in (_BULLET_PREFIX, _STEP_PREFIX, _NUMBER_PREFIX):
            without_prefix = pattern.sub("", without_prefix, count=1).strip()
        if without_prefix == normalized:
            break
        normalized = without_prefix

    return normalized
