from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.database.models.meal_plan import MealPlanRecord
from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
)


class MealPlanRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_start_date(
        self,
        start_date: date,
    ) -> MealPlanRecord | None:
        statement = (
            select(MealPlanRecord)
            .options(
                selectinload(MealPlanRecord.entries).selectinload(
                    MealPlanEntryRecord.recipe
                )
            )
            .where(MealPlanRecord.start_date == start_date)
        )

        return self.session.scalar(statement)

    def get_for_date(
        self,
        target_date: date,
    ) -> MealPlanRecord | None:
        earliest_start_date = target_date - timedelta(days=6)

        statement = (
            select(MealPlanRecord)
            .options(
                selectinload(MealPlanRecord.entries).selectinload(
                    MealPlanEntryRecord.recipe
                )
            )
            .where(
                MealPlanRecord.start_date >= earliest_start_date,
                MealPlanRecord.start_date <= target_date,
            )
            .order_by(MealPlanRecord.start_date.desc())
            .limit(1)
        )

        return self.session.scalar(statement)

    def get_latest(self) -> MealPlanRecord | None:
        statement = (
            select(MealPlanRecord)
            .options(
                selectinload(MealPlanRecord.entries).selectinload(
                    MealPlanEntryRecord.recipe
                )
            )
            .order_by(MealPlanRecord.start_date.desc())
            .limit(1)
        )

        return self.session.scalar(statement)

    def add(
        self,
        meal_plan: MealPlanRecord,
    ) -> MealPlanRecord:
        self.session.add(meal_plan)
        self.session.flush()

        return meal_plan

    def get_or_create(
        self,
        *,
        start_date: date,
        name: str | None = None,
    ) -> MealPlanRecord:
        existing = self.get_by_start_date(start_date)

        if existing is not None:
            return existing

        meal_plan = MealPlanRecord(
            start_date=start_date,
            name=name,
        )

        return self.add(meal_plan)

    def get_entry_by_id(
        self,
        entry_id: int,
    ) -> MealPlanEntryRecord | None:
        return self.session.get(
            MealPlanEntryRecord,
            entry_id,
        )

    def get_entry_by_slot(
        self,
        *,
        meal_plan_id: int,
        planned_date: date,
        meal_type: str,
        exclude_entry_id: int | None = None,
    ) -> MealPlanEntryRecord | None:
        statement = select(MealPlanEntryRecord).where(
            MealPlanEntryRecord.meal_plan_id == meal_plan_id,
            MealPlanEntryRecord.planned_date == planned_date,
            MealPlanEntryRecord.meal_type == meal_type,
        )

        if exclude_entry_id is not None:
            statement = statement.where(
                MealPlanEntryRecord.id != exclude_entry_id,
            )

        return self.session.scalar(statement)

    def delete_entry(
        self,
        entry: MealPlanEntryRecord,
    ) -> None:
        self.session.delete(entry)
