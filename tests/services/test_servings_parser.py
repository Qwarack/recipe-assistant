import pytest
from app.services.servings_parser import parse_servings


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (4, 4),
        ("4", 4),
        ("4 servings", 4),
        ("Serves 6 people", 6),
        ("voor 8 personen", 8),
        ("Makes 12", 12),
    ],
)
def test_parse_servings(
    value: object,
    expected: int,
) -> None:
    assert parse_servings(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "unknown",
        0,
        -2,
        [],
    ],
)
def test_invalid_servings_return_none(value: object) -> None:
    assert parse_servings(value) is None
