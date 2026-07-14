from decimal import Decimal

import pytest
from app.services.quantity_parser import parse_quantity


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", Decimal("1")),
        ("1.5", Decimal("1.5")),
        ("1,5", Decimal("1.5")),
        ("1/2", Decimal("0.5")),
        ("3/4", Decimal("0.75")),
        ("1 1/2", Decimal("1.5")),
        ("2 3/4", Decimal("2.75")),
        ("½", Decimal("0.5")),
        ("¼", Decimal("0.25")),
        ("2½", Decimal("2.5")),
    ],
)
def test_parse_supported_quantities(
    value: str,
    expected: Decimal,
) -> None:
    assert parse_quantity(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        " ",
        "abc",
        "1/0",
        "one half",
    ],
)
def test_invalid_quantities_return_none(value: str | None) -> None:
    assert parse_quantity(value) is None
