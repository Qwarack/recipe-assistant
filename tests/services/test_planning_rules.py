from datetime import UTC, date, datetime

from app.database.models.recipe import RecipeRecord
from app.services.planning_rules import (
    DifficultyRule,
    PlanningContext,
    PreparationTimeRule,
    RecencyRule,
    TagVarietyRule,
)
from app.services.recipe_candidate_service import RecipeCandidate


def candidate(**overrides) -> RecipeCandidate:
    values = {
        "identifier": "recipe",
        "title": "Recipe",
        "file_path": "recipe.md",
        "tags": ["italian"],
        "meal_types": ["dinner"],
        "difficulty": "unknown",
    }
    values.update(overrides)
    return RecipeCandidate(RecipeRecord(**values))


def test_recency_rule_scores_older_recipe_higher() -> None:
    context = PlanningContext(target_date=date(2026, 7, 20))
    recent = candidate(last_planned_at=datetime(2026, 7, 19, tzinfo=UTC))
    older = candidate(last_planned_at=datetime(2026, 1, 1, tzinfo=UTC))

    assert RecencyRule().score(candidate=older, context=context).score > (
        RecencyRule().score(candidate=recent, context=context).score
    )


def test_preparation_time_rule_prefers_fast_recipe_on_weekday() -> None:
    context = PlanningContext(target_date=date(2026, 7, 20))
    fast = candidate(preparation_time_minutes=20)
    slow = candidate(preparation_time_minutes=90)

    assert PreparationTimeRule().score(candidate=fast, context=context).score > (
        PreparationTimeRule().score(candidate=slow, context=context).score
    )


def test_tag_variety_rule_rewards_new_tags() -> None:
    context = PlanningContext(
        target_date=date(2026, 7, 20),
        used_tags={"pasta"},
        previous_tags={"pasta"},
    )

    assert (
        TagVarietyRule()
        .score(candidate=candidate(tags=["curry"]), context=context)
        .score
        > TagVarietyRule()
        .score(candidate=candidate(tags=["pasta"]), context=context)
        .score
    )


def test_difficulty_rule_matches_weekday_and_weekend() -> None:
    easy = candidate(difficulty="easy")
    hard = candidate(difficulty="hard")

    assert (
        DifficultyRule()
        .score(
            candidate=easy,
            context=PlanningContext(target_date=date(2026, 7, 20)),
        )
        .score
        > 0
    )
    assert (
        DifficultyRule()
        .score(
            candidate=hard,
            context=PlanningContext(target_date=date(2026, 7, 18)),
        )
        .score
        > 0
    )
