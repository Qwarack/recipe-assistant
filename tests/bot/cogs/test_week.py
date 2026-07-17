from datetime import date

from app.bot.cogs.week import (
    get_planning_start_date,
)


def test_planning_start_date_on_wednesday() -> None:
    result = get_planning_start_date(date(2026, 7, 15))

    assert result == date(2026, 7, 15)


def test_planning_start_date_on_saturday() -> None:
    result = get_planning_start_date(date(2026, 7, 18))

    assert result == date(2026, 7, 15)


def test_planning_start_date_on_monday() -> None:
    result = get_planning_start_date(date(2026, 7, 20))

    assert result == date(2026, 7, 15)
