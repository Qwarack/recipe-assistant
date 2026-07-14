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


def test_known_container_unit_is_extracted() -> None:
    ingredient = parse_ingredient_line("2 bosjes peterselie")

    assert ingredient.quantity == Decimal("2")
    assert ingredient.unit == "bos"
    assert ingredient.name == "peterselie"


def test_ingredient_whitespace_is_trimmed() -> None:
    ingredient = parse_ingredient_line("   400 g spaghetti   ")

    assert ingredient.original_text == "400 g spaghetti"
    assert ingredient.name == "spaghetti"


def test_descriptive_word_is_not_treated_as_unit() -> None:
    ingredient = parse_ingredient_line("2 rode uien")

    assert ingredient.quantity == Decimal("2")
    assert ingredient.unit is None
    assert ingredient.name == "rode uien"


def test_known_unit_is_extracted() -> None:
    ingredient = parse_ingredient_line("2 kg aardappelen")

    assert ingredient.quantity == Decimal("2")
    assert ingredient.unit == "kg"
    assert ingredient.name == "aardappelen"


def test_quantity_with_single_word_name() -> None:
    ingredient = parse_ingredient_line("3 eieren")

    assert ingredient.quantity == Decimal("3")
    assert ingredient.unit is None
    assert ingredient.name == "eieren"


@pytest.mark.parametrize(
    ("line", "expected_unit"),
    [
        ("1 eetlepel olie", "el"),
        ("2 eetlepels olie", "el"),
        ("1 tablespoon oil", "el"),
        ("3 theelepels zout", "tl"),
        ("250 gram bloem", "g"),
        ("1 liter melk", "l"),
    ],
)
def test_unit_aliases_are_normalized(
    line: str,
    expected_unit: str,
) -> None:
    ingredient = parse_ingredient_line(line)

    assert ingredient.unit == expected_unit


@pytest.mark.parametrize(
    ("line", "quantity", "unit", "name"),
    [
        ("1/2 tl zout", Decimal("0.5"), "tl", "zout"),
        ("1 1/2 el olie", Decimal("1.5"), "el", "olie"),
        ("½ citroen", Decimal("0.5"), None, "citroen"),
        ("2½ liter melk", Decimal("2.5"), "l", "melk"),
    ],
)
def test_fractional_ingredient_quantities(
    line: str,
    quantity: Decimal,
    unit: str | None,
    name: str,
) -> None:
    ingredient = parse_ingredient_line(line)

    assert ingredient.quantity == quantity
    assert ingredient.unit == unit
    assert ingredient.name == name


@pytest.mark.parametrize(
    ("line", "name", "preparation"),
    [
        (
            "2 rode uien, fijngesneden",
            "rode uien",
            "fijngesneden",
        ),
        (
            "400 g tomaten, uitgelekt",
            "tomaten",
            "uitgelekt",
        ),
        (
            "1 teen knoflook, geperst",
            "knoflook",
            "geperst",
        ),
        (
            "2 tomaten, ontveld, grof gehakt",
            "tomaten",
            "ontveld, grof gehakt",
        ),
    ],
)
def test_ingredient_preparation_is_extracted(
    line: str,
    name: str,
    preparation: str,
) -> None:
    ingredient = parse_ingredient_line(line)

    assert ingredient.name == name
    assert ingredient.preparation == preparation


def test_ingredient_without_preparation_has_none() -> None:
    ingredient = parse_ingredient_line("400 g spaghetti")

    assert ingredient.preparation is None
