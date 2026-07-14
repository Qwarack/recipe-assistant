import re
from decimal import Decimal, InvalidOperation

from app.models.recipe import Ingredient

INGREDIENT_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        (?P<quantity>\d+(?:[.,]\d+)?)
        \s*
        (?P<unit>[a-zA-ZÀ-ÿ]+)?
        \s+
    )?
    (?P<name>.+?)
    \s*$
    """,
    re.VERBOSE,
)


UNIT_ALIASES = {
    "gram": "g",
    "grams": "g",
    "gr": "g",
    "kilogram": "kg",
    "kilograms": "kg",
    "kilo": "kg",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "milliliter": "ml",
    "milliliters": "ml",
    "ml": "ml",
    "eetlepel": "el",
    "eetlepels": "el",
    "tablespoon": "el",
    "tablespoons": "el",
    "theelepel": "tl",
    "theelepels": "tl",
    "teaspoon": "tl",
    "teaspoons": "tl",
    "stuk": "stuks",
    "stuks": "stuks",
    "piece": "stuks",
    "pieces": "stuks",
}


def parse_ingredient_line(line: str) -> Ingredient:
    original_text = line.strip()

    match = INGREDIENT_PATTERN.match(original_text)

    if match is None:
        return Ingredient(
            original_text=original_text,
            name=original_text,
        )

    quantity = _parse_quantity(match.group("quantity"))
    unit = _normalize_unit(match.group("unit"))
    name = match.group("name").strip()

    return Ingredient(
        original_text=original_text,
        name=name,
        quantity=quantity,
        unit=unit,
    )


def _parse_quantity(value: str | None) -> Decimal | None:
    if value is None:
        return None

    normalized = value.replace(",", ".")

    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _normalize_unit(value: str | None) -> str | None:
    if value is None:
        return None

    normalized = value.strip().lower()

    return UNIT_ALIASES.get(normalized, normalized)
