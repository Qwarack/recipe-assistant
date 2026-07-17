from datetime import date, timedelta

from app.database.models.meal_plan import MealPlanRecord
from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
)
from app.database.repositories.meal_plan_repository import (
    MealPlanRepository,
)
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class MealPlanService:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self.session = session
        self.meal_plan_repository = MealPlanRepository(session)
        self.recipe_repository = RecipeRepository(session)

    def add_recipe(
        self,
        *,
        start_date: date,
        planned_date: date,
        recipe_identifier: str,
        meal_type: str = "dinner",
        servings: int = 2,
        notes: str | None = None,
        plan_name: str | None = None,
    ) -> MealPlanEntryRecord:
        self._validate_planned_date(
            start_date=start_date,
            planned_date=planned_date,
        )

        if servings < 1:
            raise ValueError("Servings must be at least 1")

        recipe = self.recipe_repository.get_by_identifier(recipe_identifier)

        if recipe is None:
            raise ValueError(f"Recipe not found: {recipe_identifier}")

        meal_plan = self.meal_plan_repository.get_or_create(
            start_date=start_date,
            name=plan_name,
        )

        entry = MealPlanEntryRecord(
            meal_plan=meal_plan,
            recipe=recipe,
            planned_date=planned_date,
            meal_type=meal_type,
            servings=servings,
            notes=notes,
        )

        self.session.add(entry)

        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()

            raise ValueError("This meal slot is already planned") from exc

        return entry

    def _validate_planned_date(
        self,
        *,
        start_date: date,
        planned_date: date,
    ) -> None:
        end_date = start_date + timedelta(days=6)

        if not start_date <= planned_date <= end_date:
            raise ValueError(
                "Planned date must fall within the seven-day meal plan period"
            )

    def get_plan(
        self,
        start_date: date,
    ) -> MealPlanRecord | None:
        return self.meal_plan_repository.get_by_start_date(start_date)

    def get_current_or_latest_plan(
        self,
        target_date: date,
    ) -> MealPlanRecord | None:
        current_plan = self.meal_plan_repository.get_for_date(target_date)

        if current_plan is not None:
            return current_plan

        return self.meal_plan_repository.get_latest()
