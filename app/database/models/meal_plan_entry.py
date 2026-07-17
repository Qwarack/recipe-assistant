from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.meal_plan import MealPlanRecord
    from app.database.models.recipe import RecipeRecord


class MealPlanEntrySource(StrEnum):
    MANUAL = "manual"
    GENERATED = "generated"
    LEFTOVERS = "leftovers"


class MealPlanEntryRecord(Base):
    __tablename__ = "meal_plan_entries"
    __table_args__ = (
        UniqueConstraint(
            "meal_plan_id",
            "planned_date",
            "meal_type",
            name="uq_meal_plan_entry_slot",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    meal_plan_id: Mapped[int] = mapped_column(
        ForeignKey(
            "meal_plans.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    recipe_id: Mapped[int] = mapped_column(
        ForeignKey(
            "recipes.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    planned_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    meal_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="dinner",
    )

    servings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )

    notes: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
    )

    source: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MealPlanEntrySource.MANUAL.value,
        index=True,
    )

    source_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey(
            "meal_plan_entries.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    meal_plan: Mapped["MealPlanRecord"] = relationship(
        back_populates="entries",
    )

    recipe: Mapped["RecipeRecord"] = relationship(
        back_populates="meal_plan_entries",
    )
