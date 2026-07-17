from dataclasses import dataclass
from datetime import date, timedelta

from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import RecipeRepository
from app.models.meal_plan_generation import MealPlanGenerationRequest


@dataclass(frozen=True, slots=True)
class RecipeCandidate:
    recipe: RecipeRecord

    @property
    def identifier(self) -> str:
        return self.recipe.identifier

    @property
    def tags(self) -> set[str]:
        return set(self.recipe.tags)


class RecipeCandidateService:
    def __init__(self, repository: RecipeRepository) -> None:
        self.repository = repository

    def find_candidates(
        self,
        *,
        meal_type: str,
        preferences: MealPlanGenerationRequest,
        target_date: date,
    ) -> list[RecipeCandidate]:
        return [
            RecipeCandidate(recipe)
            for recipe in self.repository.list_for_planning()
            if self._is_eligible(
                recipe=recipe,
                meal_type=meal_type,
                preferences=preferences,
                target_date=target_date,
            )
        ]

    @staticmethod
    def _is_eligible(
        *,
        recipe: RecipeRecord,
        meal_type: str,
        preferences: MealPlanGenerationRequest,
        target_date: date,
    ) -> bool:
        if recipe.identifier in preferences.excluded_recipe_identifiers:
            return False
        if meal_type not in recipe.meal_types:
            return False

        recipe_tags = set(recipe.tags)
        if not set(preferences.required_tags).issubset(recipe_tags):
            return False
        if set(preferences.excluded_tags) & recipe_tags:
            return False
        if (
            target_date.weekday() in preferences.vegetarian_days
            and recipe.vegetarian is not True
        ):
            return False

        maximum_time = (
            preferences.max_preparation_time_weekend
            if target_date.weekday() >= 5
            else preferences.max_preparation_time_weekday
        )
        if (
            maximum_time is not None
            and recipe.preparation_time_minutes is not None
            and recipe.preparation_time_minutes > maximum_time
        ):
            return False

        is_recent = (
            not preferences.allow_repeats
            and preferences.avoid_recent_days > 0
            and recipe.last_planned_at is not None
            and recipe.last_planned_at.date()
            >= target_date - timedelta(days=preferences.avoid_recent_days)
        )
        return not is_recent
