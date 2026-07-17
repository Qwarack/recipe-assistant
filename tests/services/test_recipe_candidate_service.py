from datetime import UTC, date, datetime
from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import RecipeRepository
from app.models.meal_plan_generation import MealPlanGenerationRequest
from app.services.recipe_candidate_service import RecipeCandidateService


def test_candidate_service_applies_hard_filters(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        session.add_all(
            [
                RecipeRecord(
                    identifier="valid",
                    title="Valid",
                    file_path="valid.md",
                    tags=["quick", "italian"],
                    meal_types=["dinner"],
                    preparation_time_minutes=25,
                    vegetarian=True,
                ),
                RecipeRecord(
                    identifier="slow",
                    title="Slow",
                    file_path="slow.md",
                    tags=["quick"],
                    meal_types=["dinner"],
                    preparation_time_minutes=90,
                    vegetarian=True,
                ),
                RecipeRecord(
                    identifier="meat",
                    title="Meat",
                    file_path="meat.md",
                    tags=["quick"],
                    meal_types=["dinner"],
                    preparation_time_minutes=20,
                    vegetarian=False,
                ),
                RecipeRecord(
                    identifier="recent",
                    title="Recent",
                    file_path="recent.md",
                    tags=["quick"],
                    meal_types=["dinner"],
                    preparation_time_minutes=20,
                    vegetarian=True,
                    last_planned_at=datetime(2026, 7, 15, tzinfo=UTC),
                ),
                RecipeRecord(
                    identifier="lunch",
                    title="Lunch",
                    file_path="lunch.md",
                    tags=["quick"],
                    meal_types=["lunch"],
                    vegetarian=True,
                ),
                RecipeRecord(
                    identifier="spicy",
                    title="Spicy",
                    file_path="spicy.md",
                    tags=["quick", "spicy"],
                    meal_types=["dinner"],
                    preparation_time_minutes=20,
                    vegetarian=True,
                ),
            ]
        )
        session.commit()
        service = RecipeCandidateService(RecipeRepository(session))
        request = MealPlanGenerationRequest(
            start_date=date(2026, 7, 16),
            vegetarian_days=[3],
            required_tags=["quick"],
            excluded_tags=["spicy"],
            max_preparation_time_weekday=30,
            avoid_recent_days=21,
        )

        candidates = service.find_candidates(
            meal_type="dinner",
            preferences=request,
            target_date=date(2026, 7, 16),
        )

        assert [candidate.identifier for candidate in candidates] == ["valid"]


def test_candidate_service_honors_exclusions_and_allow_repeats(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        session.add(
            RecipeRecord(
                identifier="recent",
                title="Recent",
                file_path="recent.md",
                tags=["quick"],
                meal_types=["dinner"],
                last_planned_at=datetime(2026, 7, 15, tzinfo=UTC),
            )
        )
        session.commit()
        service = RecipeCandidateService(RecipeRepository(session))

        allowed = service.find_candidates(
            meal_type="dinner",
            preferences=MealPlanGenerationRequest(
                allow_repeats=True,
                excluded_recipe_identifiers=[],
            ),
            target_date=date(2026, 7, 16),
        )
        excluded = service.find_candidates(
            meal_type="dinner",
            preferences=MealPlanGenerationRequest(
                allow_repeats=True,
                excluded_recipe_identifiers=["recent"],
            ),
            target_date=date(2026, 7, 16),
        )

        assert [candidate.identifier for candidate in allowed] == ["recent"]
        assert excluded == []
