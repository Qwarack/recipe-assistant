import re
import unicodedata
from collections.abc import Iterable

WHITESPACE_PATTERN = re.compile(r"\s+")

MEAL_TYPE_ALIASES = {
    "breakfast": "breakfast",
    "ontbijt": "breakfast",
    "lunch": "lunch",
    "dinner": "dinner",
    "avondeten": "dinner",
    "avondmaaltijd": "dinner",
    "supper": "dinner",
    "snack": "snack",
    "snacks": "snack",
    "dessert": "dessert",
    "nagerecht": "dessert",
    "toetje": "dessert",
}


def normalize_metadata_value(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = normalized.casefold()
    normalized = normalized.strip()
    normalized = WHITESPACE_PATTERN.sub(" ", normalized)

    return normalized


def normalize_tags(values: Iterable[str]) -> list[str]:
    normalized_tags = {
        normalized
        for value in values
        if (normalized := normalize_metadata_value(value))
    }

    return sorted(normalized_tags)


def normalize_meal_types(
    values: Iterable[str],
) -> list[str]:
    normalized_meal_types: set[str] = set()

    for value in values:
        normalized = normalize_metadata_value(value)

        if not normalized:
            continue

        canonical = MEAL_TYPE_ALIASES.get(normalized)

        if canonical is not None:
            normalized_meal_types.add(canonical)

    return sorted(normalized_meal_types)
