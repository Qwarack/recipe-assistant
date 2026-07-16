from app.bot.text_utils import split_text


def test_split_text_keeps_short_lines_together() -> None:
    chunks = split_text(
        [
            "eerste regel",
            "tweede regel",
        ],
        max_length=100,
    )

    assert chunks == ["eerste regel\ntweede regel"]


def test_split_text_creates_multiple_chunks() -> None:
    chunks = split_text(
        [
            "12345",
            "67890",
            "abcde",
        ],
        max_length=11,
    )

    assert chunks == [
        "12345\n67890",
        "abcde",
    ]


def test_split_text_never_exceeds_max_length() -> None:
    chunks = split_text(
        [
            "a" * 25,
        ],
        max_length=10,
    )

    assert chunks == [
        "a" * 10,
        "a" * 10,
        "a" * 5,
    ]

    assert all(len(chunk) <= 10 for chunk in chunks)


def test_split_text_returns_empty_list_for_no_lines() -> None:
    assert split_text([]) == []
