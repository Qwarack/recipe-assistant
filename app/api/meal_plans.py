from collections.abc import Generator
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.config import get_settings
from app.database.engine import create_session_factory
from app.models.meal_plan import MealPlanDetail
from app.models.meal_plan_requests import (
    AddMealPlanEntryRequest,
)
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


@router.post(
    "/{start_date}/entries",
    response_model=MealPlanDetail,
    status_code=status.HTTP_201_CREATED,
)
def add_meal_plan_entry(
    start_date: date,
    request: AddMealPlanEntryRequest,
    service: Annotated[
        MealPlanService,
        Depends(create_meal_plan_service),
    ],
) -> MealPlanDetail:
    try:
        service.add_recipe(
            start_date=start_date,
            planned_date=request.planned_date,
            recipe_identifier=request.recipe_identifier,
            meal_type=request.meal_type,
            servings=request.servings,
            notes=request.notes,
            plan_name=request.plan_name,
        )
    except ValueError as exc:
        message = str(exc)

        if message.startswith("Recipe not found:"):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=message,
            ) from exc

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=message,
        ) from exc

    meal_plan = service.get_plan(start_date)

    if meal_plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meal plan could not be loaded after creation",
        )

    return map_meal_plan_detail(meal_plan)
