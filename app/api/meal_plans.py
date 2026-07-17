from collections.abc import Generator
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.core.config import get_settings
from app.models.meal_plan import MealPlanDetail
from app.models.meal_plan_requests import (
    AddMealPlanEntryRequest,
    UpdateMealPlanEntryRequest,
)
from app.services.meal_plan_errors import (
    MealPlanEntryNotFoundError,
    MealPlanError,
    MealPlanNotFoundError,
    MealPlanSlotOccupiedError,
    RecipeNotFoundError,
)
from app.services.meal_plan_mapper import map_meal_plan_detail
from app.services.meal_plan_service import MealPlanService

router = APIRouter(
    prefix="/meal-plans",
    tags=["meal-plans"],
)


def create_meal_plan_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> Generator[MealPlanService, None, None]:
    yield MealPlanService(session)


def get_local_today() -> date:
    settings = get_settings()
    return datetime.now(ZoneInfo(settings.app_timezone)).date()


def _raise_http_error(exc: Exception) -> None:
    if isinstance(
        exc,
        RecipeNotFoundError | MealPlanNotFoundError | MealPlanEntryNotFoundError,
    ):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(exc, MealPlanSlotOccupiedError):
        status_code = status.HTTP_409_CONFLICT
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


MealPlanServiceDependency = Annotated[
    MealPlanService,
    Depends(create_meal_plan_service),
]


@router.get("/current", response_model=MealPlanDetail)
def get_current_meal_plan(
    service: MealPlanServiceDependency,
) -> MealPlanDetail:
    meal_plan = service.get_current_or_latest_plan(get_local_today())
    if meal_plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No meal plans found",
        )
    return map_meal_plan_detail(meal_plan)


@router.get("/{start_date}", response_model=MealPlanDetail)
def get_meal_plan(
    start_date: date,
    service: MealPlanServiceDependency,
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
    service: MealPlanServiceDependency,
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
    except MealPlanError as exc:
        _raise_http_error(exc)

    meal_plan = service.get_plan(start_date)
    if meal_plan is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Meal plan could not be loaded after creation",
        )
    return map_meal_plan_detail(meal_plan)


@router.patch(
    "/{start_date}/entries/{entry_id}",
    response_model=MealPlanDetail,
)
def update_meal_plan_entry(
    start_date: date,
    entry_id: int,
    request: UpdateMealPlanEntryRequest,
    service: MealPlanServiceDependency,
) -> MealPlanDetail:
    if not request.model_fields_set:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one field must be provided",
        )
    try:
        meal_plan = service.update_entry(
            start_date=start_date,
            entry_id=entry_id,
            planned_date=request.planned_date,
            meal_type=request.meal_type,
            servings=request.servings,
            notes=request.notes,
            update_notes="notes" in request.model_fields_set,
        )
    except MealPlanError as exc:
        _raise_http_error(exc)
    return map_meal_plan_detail(meal_plan)


@router.delete(
    "/{start_date}/entries/{entry_id}",
    response_model=MealPlanDetail,
)
def remove_meal_plan_entry(
    start_date: date,
    entry_id: int,
    service: MealPlanServiceDependency,
) -> MealPlanDetail:
    try:
        meal_plan = service.remove_entry(
            start_date=start_date,
            entry_id=entry_id,
        )
    except MealPlanError as exc:
        _raise_http_error(exc)
    return map_meal_plan_detail(meal_plan)
