import re

from app.models.ingredient_parse_result import (
    IngredientParseResult,
    IngredientParseWarning,
)
from app.models.recipe import Ingredient
from app.services.quantity_parser import parse_quantity

INGREDIENT_PATTERN = re.compile(
    r"""
    ^\s*
    (?:
        (?P<quantity>
            \d+\s+\d+/\d+
            |
            \d+/\d+
            |
            \d+(?:[.,]\d+)?
            |
            \d*[¼½¾⅓⅔⅛⅜⅝⅞]
        )
        \s+
    )?
    (?P<remainder>.+?)
    \s*$
    """,
    re.VERBOSE,
)

UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "gr": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "kilo": "kg",
    "l": "l",
    "liter": "l",
    "liters": "l",
    "litre": "l",
    "litres": "l",
    "ml": "ml",
    "milliliter": "ml",
    "milliliters": "ml",
    "el": "el",
    "eetlepel": "el",
    "eetlepels": "el",
    "tablespoon": "el",
    "tablespoons": "el",
    "tl": "tl",
    "theelepel": "tl",
    "theelepels": "tl",
    "teaspoon": "tl",
    "teaspoons": "tl",
    "stuk": "stuks",
    "stuks": "stuks",
    "piece": "stuks",
    "pieces": "stuks",
    "teen": "stuks",
    "tenen": "stuks",
    "blik": "blik",
    "blikken": "blik",
    "blikje": "blik",
    "blikjes": "blik",
    "bos": "bos",
    "bossen": "bos",
    "bosje": "bos",
    "bosjes": "bos",
}

OPTIONAL_MARKERS = {
    "optioneel",
    "optioneel toegevoegd",
    "eventueel",
    "naar wens",
}


def _split_unit_and_name(value: str) -> tuple[str | None, str]:
    first_word, separator, remaining_text = value.partition(" ")

    normalized_unit = _normalize_known_unit(first_word)

    if normalized_unit is None or not separator:
        return None, value

    return normalized_unit, remaining_text.strip()


def _normalize_known_unit(value: str) -> str | None:
    normalized = value.strip().lower()
    return UNIT_ALIASES.get(normalized)


def _split_name_and_preparation(
    value: str,
) -> tuple[str, str | None]:
    name, separator, preparation = value.partition(",")

    normalized_name = name.strip()

    if not separator:
        return normalized_name, None

    normalized_preparation = preparation.strip()

    return (
        normalized_name,
        normalized_preparation or None,
    )


def _extract_optional_marker(
    preparation: str | None,
) -> tuple[str | None, bool]:
    if preparation is None:
        return None, False

    normalized = preparation.strip().lower()

    if normalized in OPTIONAL_MARKERS:
        return None, True

    for marker in OPTIONAL_MARKERS:
        suffix = f", {marker}"

        if normalized.endswith(suffix):
            cleaned = preparation[: -len(suffix)].strip()
            return cleaned or None, True

    return preparation, False


def parse_ingredient_line(line: str) -> Ingredient:
    return parse_ingredient_line_with_warnings(line).ingredient


def parse_ingredient_line_with_warnings(
    line: str,
) -> IngredientParseResult:
    original_text = line.strip()

    match = INGREDIENT_PATTERN.match(original_text)

    if match is None:
        ingredient = Ingredient(
            original_text=original_text,
            name=original_text,
        )

        return IngredientParseResult(
            ingredient=ingredient,
            warnings=[
                IngredientParseWarning(
                    code="ingredient_pattern_not_matched",
                    message="Ingredient line could not be structurally parsed",
                )
            ],
        )

    quantity_text = match.group("quantity")
    quantity = parse_quantity(quantity_text)
    remainder = match.group("remainder").strip()

    unit, name_and_preparation = _split_unit_and_name(remainder)
    name, preparation = _split_name_and_preparation(name_and_preparation)
    preparation, optional = _extract_optional_marker(preparation)

    ingredient = Ingredient(
        original_text=original_text,
        name=name,
        quantity=quantity,
        unit=unit,
        preparation=preparation,
        optional=optional,
    )

    warnings: list[IngredientParseWarning] = []

    if quantity_text is not None and quantity is None:
        warnings.append(
            IngredientParseWarning(
                code="quantity_not_parsed",
                message="Ingredient quantity could not be parsed",
            )
        )

    return IngredientParseResult(
        ingredient=ingredient,
        warnings=warnings,
    )
