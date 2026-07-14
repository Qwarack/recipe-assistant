from app.utils.title_normalizer import normalize_title


def test_normalizes_case_and_whitespace() -> None:
    result = normalize_title("  Pasta   Carbonara  ")

    assert result == "pasta carbonara"


def test_removes_punctuation() -> None:
    result = normalize_title("Pasta Carbonara!")

    assert result == "pasta carbonara"


def test_preserves_meaningful_hyphens() -> None:
    result = normalize_title("One-pot pasta")

    assert result == "one-pot pasta"


def test_handles_unicode_consistently() -> None:
    result = normalize_title("Crème Brûlée")

    assert result == "crème brûlée"
