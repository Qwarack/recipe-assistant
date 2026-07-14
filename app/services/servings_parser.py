import re

INTEGER_PATTERN = re.compile(r"\d+")


def parse_servings(value: object) -> int | None:
    if isinstance(value, int):
        return value if value > 0 else None

    if not isinstance(value, str):
        return None

    match = INTEGER_PATTERN.search(value)

    if match is None:
        return None

    servings = int(match.group())

    return servings if servings > 0 else None
