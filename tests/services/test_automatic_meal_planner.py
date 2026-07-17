from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.meal_plan import MealPlanStatus
from app.database.models.meal_plan_entry import MealPlanEntrySource
from app.database.models.recipe import RecipeRecord
from app.database.repositories.meal_plan_repository import MealPlanRepository
from app.models.meal_plan_generation import MealPlanGenerationRequest
from app.services.automatic_meal_planner import AutomaticMealPlanner
from app.services.meal_plan_generation_errors import (
    InvalidMealPlanGenerationConfigError,
    MealPlanAlreadyActiveError,
    MealPlanCannotActivateError,
    MealPlanDraftNotFoundError,
    MealPlanEntryCannotRerollError,
)
from app.services.meal_plan_service import MealPlanService


def add_recipes(session, count: int = 8) -> None:
    session.add_all(
        [
            RecipeRecord(
                identifier=f"recipe-{index}",
                title=f"Recipe {index}",
                file_path=f"recipe-{index}.md",
                tags=[],
                meal_types=["dinner"],
                preparation_time_minutes=30,
                difficulty="unknown",
                vegetarian=index % 2 == 0,
            )
            for index in range(count)
        ]
    )
    session.commit()


def make_planner(session) -> AutomaticMealPlanner:
    return AutomaticMealPlanner(
        session=session,
        today_provider=lambda: date(2026, 7, 23),
        now_provider=lambda: datetime(2026, 7, 20, 12, tzinfo=UTC),
    )


def identifiers(result) -> list[str]:
    return [entry.recipe_identifier for entry in result.plan.entries]


def test_generate_creates_complete_deterministic_draft(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        planner = make_planner(session)
        request = MealPlanGenerationRequest(
            start_date=date(2026, 7, 22),
            random_seed=12345,
            avoid_recent_days=0,
        )

        first = planner.generate(request)
        second = planner.generate(request)

        assert first.plan.status == MealPlanStatus.DRAFT.value
        assert first.plan.start_date == date(2026, 7, 22)
        assert first.plan.end_date == date(2026, 7, 28)
        assert len(first.plan.entries) == 7
        assert len(set(identifiers(first))) == 7
        assert identifiers(first) == identifiers(second)
        assert first.unfilled_slots == []
        assert len(first.selection_explanations) == 7


def test_different_seed_can_select_different_valid_plan(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        planner = make_planner(session)

        first = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                avoid_recent_days=0,
            )
        )
        second = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=2,
                avoid_recent_days=0,
            )
        )

        assert identifiers(first) != identifiers(second)
        assert len(second.plan.entries) == 7


def test_generate_uses_recent_wednesday_and_custom_days(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        result = make_planner(session).generate(
            MealPlanGenerationRequest(
                days_to_plan=[2, 3, 4],
                random_seed=1,
                avoid_recent_days=0,
            )
        )

        assert result.plan.start_date == date(2026, 7, 22)
        assert [entry.planned_date.weekday() for entry in result.plan.entries] == [
            2,
            3,
            4,
        ]

        empty = make_planner(session).generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                days_to_plan=[],
                random_seed=1,
                avoid_recent_days=0,
            )
        )
        assert empty.plan.entries == []
        assert empty.unfilled_slots == []


def test_generate_preserves_manual_entry(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        MealPlanService(session).add_recipe(
            start_date=date(2026, 7, 22),
            planned_date=date(2026, 7, 22),
            recipe_identifier="recipe-0",
        )

        result = make_planner(session).generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                avoid_recent_days=0,
            )
        )

        assert len(result.plan.entries) == 7
        assert result.plan.entries[0].recipe_identifier == "recipe-0"
        assert result.plan.entries[0].source == MealPlanEntrySource.MANUAL.value


def test_generate_without_preservation_leaves_active_plan_untouched(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        manual_entry = MealPlanService(session).add_recipe(
            start_date=date(2026, 7, 22),
            planned_date=date(2026, 7, 22),
            recipe_identifier="recipe-0",
        )
        active_plan_id = manual_entry.meal_plan_id

        result = make_planner(session).generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                preserve_existing_entries=False,
                random_seed=1,
                avoid_recent_days=0,
            )
        )
        active = MealPlanRepository(session).get_by_id(active_plan_id)

        assert active is not None
        assert active.status == MealPlanStatus.ACTIVE.value
        assert active.entries[0].recipe.identifier == "recipe-0"
        assert all(entry.source == "generated" for entry in result.plan.entries)


def test_generate_reports_unfilled_slots_without_crashing(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        session.add(
            RecipeRecord(
                identifier="meat",
                title="Meat",
                file_path="meat.md",
                meal_types=["dinner"],
                vegetarian=False,
            )
        )
        session.commit()

        result = make_planner(session).generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                vegetarian_days=list(range(7)),
                random_seed=1,
                avoid_recent_days=0,
            )
        )

        assert result.plan.entries == []
        assert len(result.unfilled_slots) == 7


def test_leftovers_flag_is_explicitly_rejected_until_supported(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with (
        session_factory() as session,
        pytest.raises(InvalidMealPlanGenerationConfigError),
    ):
        make_planner(session).generate(MealPlanGenerationRequest(enable_leftovers=True))


def test_draft_activation_archives_previous_active_plan(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        manual_entry = MealPlanService(session).add_recipe(
            start_date=date(2026, 7, 22),
            planned_date=date(2026, 7, 22),
            recipe_identifier="recipe-0",
        )
        old_plan_id = manual_entry.meal_plan_id
        planner = make_planner(session)
        draft = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                avoid_recent_days=0,
            )
        )

        activated = planner.activate(plan_id=draft.plan.id, activated_by="123")
        old_plan = MealPlanRepository(session).get_by_id(old_plan_id)

        assert activated.status == MealPlanStatus.ACTIVE.value
        assert activated.activated_by == "123"
        assert old_plan is not None
        assert old_plan.status == MealPlanStatus.ARCHIVED.value
        assert all(
            entry.recipe.last_planned_at is not None for entry in activated.entries
        )


def test_incomplete_draft_cannot_be_activated_by_default(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        planner = make_planner(session)
        draft = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
            )
        )

        with pytest.raises(MealPlanCannotActivateError):
            planner.activate(plan_id=draft.plan.id)


def test_incomplete_draft_can_be_activated_when_explicitly_allowed(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        planner = make_planner(session)
        draft = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                allow_unfilled_slots=True,
            )
        )

        activated = planner.activate(plan_id=draft.plan.id)

        assert activated.status == MealPlanStatus.ACTIVE.value
        assert activated.entries == []


def test_regenerate_creates_new_draft_and_preserves_config(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        planner = make_planner(session)
        first = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                servings=4,
                random_seed=1,
                avoid_recent_days=0,
            )
        )

        second = planner.regenerate(plan_id=first.plan.id, random_seed=2)
        stored = MealPlanRepository(session).get_by_id(second.plan.id)

        assert second.plan.id != first.plan.id
        assert second.generation_seed == 2
        assert stored is not None
        assert stored.generation_config is not None
        assert stored.generation_config["servings"] == 4


def test_cancel_only_allows_drafts(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        planner = make_planner(session)
        draft = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                avoid_recent_days=0,
            )
        )
        planner.cancel(plan_id=draft.plan.id)

        assert MealPlanRepository(session).get_by_id(draft.plan.id) is None
        with pytest.raises(MealPlanDraftNotFoundError):
            planner.cancel(plan_id=draft.plan.id)

        active = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=2,
                avoid_recent_days=0,
            )
        )
        planner.activate(plan_id=active.plan.id)
        with pytest.raises(MealPlanAlreadyActiveError):
            planner.cancel(plan_id=active.plan.id)


def test_reroll_replaces_only_selected_generated_entry(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session)
        planner = make_planner(session)
        draft = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                avoid_recent_days=0,
            )
        )
        target = draft.plan.entries[0]
        other_entries = {
            entry.id: entry.recipe_identifier for entry in draft.plan.entries[1:]
        }

        rerolled = planner.reroll_entry(
            plan_id=draft.plan.id,
            entry_id=target.id,
            random_seed=3,
        )
        updated = next(
            entry for entry in rerolled.plan.entries if entry.id == target.id
        )

        assert updated.recipe_identifier != target.recipe_identifier
        assert {
            entry.id: entry.recipe_identifier
            for entry in rerolled.plan.entries
            if entry.id != target.id
        } == other_entries


def test_reroll_reports_when_no_alternative_exists(tmp_path: Path) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    with session_factory() as session:
        add_recipes(session, count=7)
        planner = make_planner(session)
        draft = planner.generate(
            MealPlanGenerationRequest(
                start_date=date(2026, 7, 22),
                random_seed=1,
                avoid_recent_days=0,
            )
        )

        with pytest.raises(MealPlanEntryCannotRerollError):
            planner.reroll_entry(
                plan_id=draft.plan.id,
                entry_id=draft.plan.entries[0].id,
                random_seed=2,
            )
