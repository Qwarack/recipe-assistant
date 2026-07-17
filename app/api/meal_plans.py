from collections.abc import Generator
from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.core.config import get_settings
from app.models.meal_plan import MealPlanDetail
from app.models.meal_plan_generation import (
    ActivateMealPlanRequest,
    MealPlanGenerationRequest,
    MealPlanGenerationResponse,
    RegenerateMealPlanRequest,
    RerollMealPlanEntryRequest,
)
from app.models.meal_plan_requests import (
    AddMealPlanEntryRequest,
    UpdateMealPlanEntryRequest,
)
from app.services.automatic_meal_planner import AutomaticMealPlanner
from app.services.meal_plan_errors import (
    MealPlanEntryNotFoundError,
    MealPlanError,
    MealPlanNotFoundError,
    MealPlanSlotOccupiedError,
    RecipeNotFoundError,
)
from app.services.meal_plan_generation_errors import (
    InvalidMealPlanGenerationConfigError,
    MealPlanAlreadyActiveError,
    MealPlanCannotActivateError,
    MealPlanDraftNotFoundError,
    MealPlanEntryCannotRerollError,
    MealPlanGenerationError,
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


def create_automatic_meal_planner(
    session: Annotated[Session, Depends(get_database_session)],
) -> Generator[AutomaticMealPlanner, None, None]:
    yield AutomaticMealPlanner(
        session=session,
        today_provider=get_local_today,
    )


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
AutomaticMealPlannerDependency = Annotated[
    AutomaticMealPlanner,
    Depends(create_automatic_meal_planner),
]


def _raise_generation_http_error(exc: MealPlanGenerationError) -> None:
    if isinstance(exc, MealPlanDraftNotFoundError):
        status_code = status.HTTP_404_NOT_FOUND
    elif isinstance(
        exc,
        MealPlanAlreadyActiveError
        | MealPlanCannotActivateError
        | MealPlanEntryCannotRerollError,
    ):
        status_code = status.HTTP_409_CONFLICT
    elif isinstance(exc, InvalidMealPlanGenerationConfigError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    else:
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    raise HTTPException(status_code=status_code, detail=str(exc)) from exc


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


@router.post(
    "/generate",
    response_model=MealPlanGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def generate_meal_plan(
    request: MealPlanGenerationRequest,
    planner: AutomaticMealPlannerDependency,
) -> MealPlanGenerationResponse:
    try:
        return planner.generate(request)
    except MealPlanGenerationError as exc:
        _raise_generation_http_error(exc)


@router.post(
    "/{plan_id}/activate",
    response_model=MealPlanDetail,
)
def activate_meal_plan(
    plan_id: int,
    planner: AutomaticMealPlannerDependency,
    request: ActivateMealPlanRequest | None = None,
) -> MealPlanDetail:
    try:
        plan = planner.activate(
            plan_id=plan_id,
            activated_by=request.activated_by if request else None,
        )
    except MealPlanGenerationError as exc:
        _raise_generation_http_error(exc)
    return map_meal_plan_detail(plan)


@router.post(
    "/{plan_id}/regenerate",
    response_model=MealPlanGenerationResponse,
    status_code=status.HTTP_201_CREATED,
)
def regenerate_meal_plan(
    plan_id: int,
    planner: AutomaticMealPlannerDependency,
    request: RegenerateMealPlanRequest | None = None,
) -> MealPlanGenerationResponse:
    try:
        return planner.regenerate(
            plan_id=plan_id,
            random_seed=request.random_seed if request else None,
        )
    except MealPlanGenerationError as exc:
        _raise_generation_http_error(exc)


@router.post(
    "/{plan_id}/entries/{entry_id}/reroll",
    response_model=MealPlanGenerationResponse,
)
def reroll_meal_plan_entry(
    plan_id: int,
    entry_id: int,
    planner: AutomaticMealPlannerDependency,
    request: RerollMealPlanEntryRequest | None = None,
) -> MealPlanGenerationResponse:
    try:
        return planner.reroll_entry(
            plan_id=plan_id,
            entry_id=entry_id,
            random_seed=request.random_seed if request else None,
        )
    except MealPlanGenerationError as exc:
        _raise_generation_http_error(exc)


@router.delete("/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
def cancel_meal_plan_draft(
    plan_id: int,
    planner: AutomaticMealPlannerDependency,
) -> None:
    try:
        planner.cancel(plan_id=plan_id)
    except MealPlanGenerationError as exc:
        _raise_generation_http_error(exc)


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
