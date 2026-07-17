from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base

if TYPE_CHECKING:
    from app.database.models.meal_plan_entry import (
        MealPlanEntryRecord,
    )


class RecipeRecord(Base):
    __tablename__ = "recipes"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    identifier: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        index=True,
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )

    file_path: Mapped[str] = mapped_column(
        Text,
        unique=True,
        nullable=False,
    )

    source_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
        nullable=True,
    )

    tags: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    meal_types: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["dinner"],
    )

    preparation_time_minutes: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        index=True,
    )

    difficulty: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="unknown",
        index=True,
    )

    default_servings: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=2,
    )

    vegetarian: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
    )

    vegan: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        index=True,
    )

    last_planned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
    )

    suitable_for_leftovers: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    leftover_servings: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )

    leftover_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
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

    meal_plan_entries: Mapped[list["MealPlanEntryRecord"]] = relationship(
        back_populates="recipe",
        passive_deletes=True,
    )
