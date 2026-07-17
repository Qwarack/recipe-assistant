from datetime import date, datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Date, DateTime, Index, Integer, String, func, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.meal_plan_entry import (
        MealPlanEntryRecord,
    )


class MealPlanStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class MealPlanRecord(Base):
    __tablename__ = "meal_plans"
    __table_args__ = (
        Index(
            "uq_active_meal_plan_start_date",
            "start_date",
            unique=True,
            sqlite_where=text("status = 'active'"),
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

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=MealPlanStatus.ACTIVE.value,
        index=True,
    )

    generation_seed: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    generation_config: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )

    created_by: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    activated_by: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
    )

    generation_source: Mapped[str | None] = mapped_column(
        String(50),
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
