from datetime import timedelta

from app.database.models.meal_plan import (
    MealPlanRecord,
)
from app.models.meal_plan import (
    MealPlanDetail,
    MealPlanEntryDetail,
)


def map_meal_plan_detail(
    meal_plan: MealPlanRecord,
) -> MealPlanDetail:
    entries = [
        MealPlanEntryDetail(
            id=entry.id,
            planned_date=entry.planned_date,
            meal_type=entry.meal_type,
            servings=entry.servings,
            notes=entry.notes,
            recipe_identifier=entry.recipe.identifier,
            recipe_title=entry.recipe.title,
        )
        for entry in meal_plan.entries
    ]

    return MealPlanDetail(
        id=meal_plan.id,
        start_date=meal_plan.start_date,
        end_date=meal_plan.start_date + timedelta(days=6),
        name=meal_plan.name,
        entries=entries,
    )
