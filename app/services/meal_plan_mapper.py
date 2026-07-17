from datetime import timedelta

from app.database.models.meal_plan import (
    MealPlanRecord,
    MealPlanStatus,
)
from app.database.models.meal_plan_entry import (
    MealPlanEntrySource,
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
            preparation_time_minutes=entry.recipe.preparation_time_minutes,
            source=entry.source or MealPlanEntrySource.MANUAL.value,
            source_entry_id=entry.source_entry_id,
        )
        for entry in meal_plan.entries
    ]

    return MealPlanDetail(
        id=meal_plan.id,
        start_date=meal_plan.start_date,
        end_date=meal_plan.start_date + timedelta(days=6),
        name=meal_plan.name,
        status=meal_plan.status or MealPlanStatus.ACTIVE.value,
        generation_seed=meal_plan.generation_seed,
        generated_at=meal_plan.generated_at,
        entries=entries,
    )
