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
from app.services.meal_plan_errors import (
    InvalidServingsError,
    MealPlanDateOutsideRangeError,
    MealPlanEntryNotFoundError,
    MealPlanNotFoundError,
    MealPlanSlotOccupiedError,
    RecipeNotFoundError,
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
            raise InvalidServingsError("Servings must be at least 1")

        recipe = self.recipe_repository.get_by_identifier(recipe_identifier)

        if recipe is None:
            raise RecipeNotFoundError(f"Recipe not found: {recipe_identifier}")

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

            raise MealPlanSlotOccupiedError(
                "This meal slot is already planned"
            ) from exc

        return entry

    def _validate_planned_date(
        self,
        *,
        start_date: date,
        planned_date: date,
    ) -> None:
        end_date = start_date + timedelta(days=6)

        if not start_date <= planned_date <= end_date:
            raise MealPlanDateOutsideRangeError(
                "Planned date must fall within the seven-day meal plan period"
            )

    def remove_entry(
        self,
        *,
        start_date: date,
        entry_id: int,
    ) -> MealPlanRecord:
        entry = self._get_entry_for_plan(
            start_date=start_date,
            entry_id=entry_id,
        )
        self.meal_plan_repository.delete_entry(entry)
        self.session.commit()
        self.session.expire_all()

        return self._require_plan(start_date)

    def update_entry(
        self,
        *,
        start_date: date,
        entry_id: int,
        planned_date: date | None = None,
        meal_type: str | None = None,
        servings: int | None = None,
        notes: str | None = None,
        update_notes: bool = False,
    ) -> MealPlanRecord:
        entry = self._get_entry_for_plan(
            start_date=start_date,
            entry_id=entry_id,
        )
        updated_date = planned_date or entry.planned_date
        updated_meal_type = meal_type or entry.meal_type

        self._validate_planned_date(
            start_date=start_date,
            planned_date=updated_date,
        )

        if servings is not None and servings < 1:
            raise InvalidServingsError("Servings must be at least 1")

        occupied_entry = self.meal_plan_repository.get_entry_by_slot(
            meal_plan_id=entry.meal_plan_id,
            planned_date=updated_date,
            meal_type=updated_meal_type,
            exclude_entry_id=entry.id,
        )
        if occupied_entry is not None:
            raise MealPlanSlotOccupiedError("This meal slot is already planned")

        entry.planned_date = updated_date
        entry.meal_type = updated_meal_type
        if servings is not None:
            entry.servings = servings
        if update_notes:
            entry.notes = notes

        try:
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise MealPlanSlotOccupiedError(
                "This meal slot is already planned"
            ) from exc

        self.session.expire_all()
        return self._require_plan(start_date)

    def _get_entry_for_plan(
        self,
        *,
        start_date: date,
        entry_id: int,
    ) -> MealPlanEntryRecord:
        entry = self.meal_plan_repository.get_entry_by_id(entry_id)
        if entry is None or entry.meal_plan.start_date != start_date:
            raise MealPlanEntryNotFoundError("Meal plan entry not found")

        return entry

    def _require_plan(self, start_date: date) -> MealPlanRecord:
        meal_plan = self.meal_plan_repository.get_by_start_date(start_date)
        if meal_plan is None:
            raise MealPlanNotFoundError("Meal plan not found")

        return meal_plan

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
