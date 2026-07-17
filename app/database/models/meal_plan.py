from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.meal_plan_entry import (
        MealPlanEntryRecord,
    )


class MealPlanRecord(Base):
    __tablename__ = "meal_plans"
    __table_args__ = (
        UniqueConstraint(
            "start_date",
            name="uq_meal_plans_start_date",
        ),
    )

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    start_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    name: Mapped[str | None] = mapped_column(
        String(255),
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

    entries: Mapped[list["MealPlanEntryRecord"]] = relationship(
        back_populates="meal_plan",
        cascade="all, delete-orphan",
        order_by="MealPlanEntryRecord.planned_date",
    )
