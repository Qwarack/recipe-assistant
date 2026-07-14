from decimal import Decimal

import pytest
from app.services.ingredient_parser import parse_ingredient_line


@pytest.mark.parametrize(
    ("line", "quantity", "unit", "name"),
    [
        ("400 g spaghetti", Decimal("400"), "g", "spaghetti"),
        ("2 kg aardappelen", Decimal("2"), "kg", "aardappelen"),
        ("1.5 l bouillon", Decimal("1.5"), "l", "bouillon"),
        ("1,5 liter melk", Decimal("1.5"), "l", "melk"),
        ("3 stuks eieren", Decimal("3"), "stuks", "eieren"),
    ],
)
def test_parse_simple_ingredient_lines(
    line: str,
    quantity: Decimal,
    unit: str,
    name: str,
) -> None:
    ingredient = parse_ingredient_line(line)

    assert ingredient.original_text == line
    assert ingredient.quantity == quantity
    assert ingredient.unit == unit
    assert ingredient.name == name


def test_parse_ingredient_without_quantity() -> None:
    ingredient = parse_ingredient_line("zout naar smaak")

    assert ingredient.original_text == "zout naar smaak"
    assert ingredient.quantity is None
    assert ingredient.unit is None
    assert ingredient.name == "zout naar smaak"


def test_unknown_unit_is_preserved() -> None:
    ingredient = parse_ingredient_line("2 bosjes peterselie")

    assert ingredient.quantity == Decimal("2")
    assert ingredient.unit == "bosjes"
    assert ingredient.name == "peterselie"


def test_ingredient_whitespace_is_trimmed() -> None:
    ingredient = parse_ingredient_line("   400 g spaghetti   ")

    assert ingredient.original_text == "400 g spaghetti"
    assert ingredient.name == "spaghetti"
