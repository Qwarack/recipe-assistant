from app.utils.recipe_metadata import (
    normalize_meal_types,
    normalize_tags,
)


def test_normalizes_and_deduplicates_tags() -> None:
    result = normalize_tags(
        [
            " Quick ",
            "quick",
            "PASTA",
        ]
    )

    assert result == [
        "pasta",
        "quick",
    ]


def test_normalizes_meal_type_aliases() -> None:
    result = normalize_meal_types(
        [
            "Avondeten",
            "Dinner",
            " lunch ",
        ]
    )

    assert result == [
        "dinner",
        "lunch",
    ]


def test_ignores_unknown_meal_types() -> None:
    result = normalize_meal_types(
        [
            "dinner",
            "gezellig eten",
        ]
    )

    assert result == ["dinner"]
