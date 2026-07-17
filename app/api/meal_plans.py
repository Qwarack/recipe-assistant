from collections.abc import Generator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.database.engine import create_session_factory
from app.models.meal_plan import MealPlanDetail
from app.services.meal_plan_mapper import (
    map_meal_plan_detail,
)
from app.services.meal_plan_service import (
    MealPlanService,
)

router = APIRouter(
    prefix="/meal-plans",
    tags=["meal-plans"],
)


def create_meal_plan_service() -> Generator[
    MealPlanService,
    None,
    None,
]:
    settings = get_settings()

    session_factory = create_session_factory(settings.database_path)

    with session_factory() as session:
        yield MealPlanService(session)


@router.get(
    "/{start_date}",
    response_model=MealPlanDetail,
)
def get_meal_plan(
    start_date: date,
    service: Annotated[
        MealPlanService,
        Depends(create_meal_plan_service),
    ],
) -> MealPlanDetail:
    meal_plan = service.get_plan(start_date)

    if meal_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meal plan not found",
        )

    return map_meal_plan_detail(meal_plan)
