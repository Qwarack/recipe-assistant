import logging
import random
import secrets
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime, time, timedelta

from app.database.models.meal_plan import MealPlanRecord, MealPlanStatus
from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
    MealPlanEntrySource,
)
from app.database.repositories.meal_plan_repository import MealPlanRepository
from app.database.repositories.recipe_repository import RecipeRepository
from app.models.meal_plan_generation import (
    MealPlanGenerationRequest,
    MealPlanGenerationResponse,
    MealPlanSelectionExplanation,
    UnfilledMealPlanSlot,
)
from app.services.meal_plan_generation_errors import (
    InvalidMealPlanGenerationConfigError,
    MealPlanAlreadyActiveError,
    MealPlanCannotActivateError,
    MealPlanDraftNotFoundError,
    MealPlanEntryCannotRerollError,
)
from app.services.meal_plan_mapper import map_meal_plan_detail
from app.services.planning_rules import (
    DifficultyRule,
    PlanningContext,
    PlanningRule,
    PreparationTimeRule,
    RecencyRule,
    TagVarietyRule,
)
from app.services.recipe_candidate_service import (
    RecipeCandidate,
    RecipeCandidateService,
)
from pydantic import ValidationError
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AutomaticMealPlanner:
    def __init__(
        self,
        *,
        session: Session,
        today_provider: Callable[[], date],
        now_provider: Callable[[], datetime] | None = None,
        rules: Sequence[PlanningRule] | None = None,
    ) -> None:
        self.session = session
        self.today_provider = today_provider
        self.now_provider = now_provider or (lambda: datetime.now(UTC))
        self.meal_plan_repository = MealPlanRepository(session)
        self.recipe_repository = RecipeRepository(session)
        self.candidate_service = RecipeCandidateService(self.recipe_repository)
        self.rules = list(
            rules
            or [
                RecencyRule(),
                PreparationTimeRule(),
                TagVarietyRule(),
                DifficultyRule(),
            ]
        )

    @staticmethod
    def planning_start_date(target_date: date) -> date:
        return target_date - timedelta(days=(target_date.weekday() - 2) % 7)

    def generate(
        self,
        request: MealPlanGenerationRequest,
    ) -> MealPlanGenerationResponse:
        if request.enable_leftovers:
            raise InvalidMealPlanGenerationConfigError(
                "Automatic leftovers planning is not supported yet"
            )
        start_date = request.start_date or self.planning_start_date(
            self.today_provider()
        )
        seed = request.random_seed
        if seed is None:
            seed = secrets.randbits(63)
        effective_request = request.model_copy(
            update={"start_date": start_date, "random_seed": seed}
        )
        rng = random.Random(seed)
        now = self.now_provider()
        plan = MealPlanRecord(
            start_date=start_date,
            name="Automatisch voorstel",
            status=MealPlanStatus.DRAFT.value,
            generation_seed=seed,
            generated_at=now,
            generation_config=effective_request.model_dump(mode="json"),
            created_by=effective_request.created_by,
            generation_source="automatic",
        )
        self.meal_plan_repository.add(plan)

        active_plan = self.meal_plan_repository.get_active_by_start_date(start_date)
        if effective_request.preserve_existing_entries and active_plan is not None:
            self._copy_existing_entries(active_plan, plan)

        explanations: list[MealPlanSelectionExplanation] = []
        unfilled_slots: list[UnfilledMealPlanSlot] = []
        used_identifiers = {entry.recipe.identifier for entry in plan.entries}
        used_tags = {tag for entry in plan.entries for tag in entry.recipe.tags}
        previous_tags: set[str] = set()

        for target_date in self._target_dates(effective_request):
            existing = self._entry_for_slot(
                plan,
                target_date,
                effective_request.meal_type,
            )
            if existing is not None:
                previous_tags = set(existing.recipe.tags)
                continue

            candidates = self.candidate_service.find_candidates(
                meal_type=effective_request.meal_type,
                preferences=effective_request,
                target_date=target_date,
            )
            if not effective_request.allow_repeats:
                candidates = [
                    candidate
                    for candidate in candidates
                    if candidate.identifier not in used_identifiers
                ]

            selected = self._select_candidate(
                candidates=candidates,
                target_date=target_date,
                used_tags=used_tags,
                previous_tags=previous_tags,
                rng=rng,
            )
            if selected is None:
                unfilled_slots.append(
                    UnfilledMealPlanSlot(
                        planned_date=target_date,
                        meal_type=effective_request.meal_type,
                        reason="Geen recepten voldoen aan de ingestelde filters.",
                    )
                )
                logger.info(
                    "No candidates for meal-plan slot",
                    extra={
                        "plan_id": plan.id,
                        "start_date": str(start_date),
                        "planned_date": str(target_date),
                    },
                )
                continue

            candidate, score, reasons = selected
            entry = MealPlanEntryRecord(
                meal_plan=plan,
                recipe=candidate.recipe,
                planned_date=target_date,
                meal_type=effective_request.meal_type,
                servings=effective_request.servings,
                source=MealPlanEntrySource.GENERATED.value,
            )
            self.session.add(entry)
            explanations.append(
                MealPlanSelectionExplanation(
                    planned_date=target_date,
                    meal_type=effective_request.meal_type,
                    recipe_identifier=candidate.identifier,
                    score=score,
                    reasons=reasons,
                )
            )
            used_identifiers.add(candidate.identifier)
            used_tags.update(candidate.tags)
            previous_tags = candidate.tags

        self.session.commit()
        self.session.expire_all()
        stored_plan = self._require_plan(plan.id)
        logger.info(
            "Generated meal-plan draft",
            extra={
                "plan_id": stored_plan.id,
                "start_date": str(start_date),
                "generation_seed": seed,
                "filled_slots": len(explanations),
                "unfilled_slots": len(unfilled_slots),
                "created_by": effective_request.created_by,
            },
        )
        return MealPlanGenerationResponse(
            plan=map_meal_plan_detail(stored_plan),
            unfilled_slots=unfilled_slots,
            selection_explanations=explanations,
            generation_seed=seed,
        )

    def activate(
        self,
        *,
        plan_id: int,
        activated_by: str | None = None,
    ) -> MealPlanRecord:
        plan = self._require_draft(plan_id)
        request = self._request_from_plan(plan)
        missing_slots = self._missing_required_slots(plan, request)
        if missing_slots and not request.allow_unfilled_slots:
            raise MealPlanCannotActivateError("Draft has unfilled required meal slots")
        self._validate_entries(plan)

        current_active = self.meal_plan_repository.get_active_by_start_date(
            plan.start_date
        )
        if current_active is not None and current_active.id != plan.id:
            current_active.status = MealPlanStatus.ARCHIVED.value
            self.session.flush()

        plan.status = MealPlanStatus.ACTIVE.value
        plan.activated_by = activated_by
        for entry in plan.entries:
            self.recipe_repository.mark_planned(
                entry.recipe,
                datetime.combine(entry.planned_date, time.min, UTC),
            )
        self.session.commit()
        self.session.expire_all()
        activated_plan = self._require_plan(plan_id)
        logger.info(
            "Activated meal plan",
            extra={
                "plan_id": plan_id,
                "start_date": str(plan.start_date),
                "activated_by": activated_by,
            },
        )
        return activated_plan

    def regenerate(
        self,
        *,
        plan_id: int,
        random_seed: int | None = None,
    ) -> MealPlanGenerationResponse:
        plan = self._require_draft(plan_id)
        request = self._request_from_plan(plan)
        request = request.model_copy(update={"random_seed": random_seed})
        result = self.generate(request)
        logger.info(
            "Regenerated meal-plan draft",
            extra={
                "plan_id": result.plan.id,
                "previous_plan_id": plan_id,
                "generation_seed": result.generation_seed,
            },
        )
        return result

    def cancel(self, *, plan_id: int) -> None:
        plan = self._require_draft(plan_id)
        self.meal_plan_repository.delete(plan)
        self.session.commit()
        logger.info("Cancelled meal-plan draft", extra={"plan_id": plan_id})

    def reroll_entry(
        self,
        *,
        plan_id: int,
        entry_id: int,
        random_seed: int | None = None,
    ) -> MealPlanGenerationResponse:
        plan = self._require_draft(plan_id)
        entry = next((item for item in plan.entries if item.id == entry_id), None)
        if entry is None or entry.source != MealPlanEntrySource.GENERATED.value:
            raise MealPlanEntryCannotRerollError(
                "Only generated entries in this draft can be rerolled"
            )
        request = self._request_from_plan(plan)
        seed = random_seed if random_seed is not None else secrets.randbits(63)
        excluded = set(request.excluded_recipe_identifiers)
        excluded.add(entry.recipe.identifier)
        reroll_request = request.model_copy(
            update={
                "excluded_recipe_identifiers": sorted(excluded),
                "random_seed": seed,
            }
        )
        candidates = self.candidate_service.find_candidates(
            meal_type=entry.meal_type,
            preferences=reroll_request,
            target_date=entry.planned_date,
        )
        if not request.allow_repeats:
            other_identifiers = {
                item.recipe.identifier for item in plan.entries if item.id != entry.id
            }
            candidates = [
                candidate
                for candidate in candidates
                if candidate.identifier not in other_identifiers
            ]

        earlier_entries = [
            item
            for item in plan.entries
            if item.id != entry.id and item.planned_date <= entry.planned_date
        ]
        used_tags = {
            tag
            for item in plan.entries
            if item.id != entry.id
            for tag in item.recipe.tags
        }
        previous_tags = (
            set(max(earlier_entries, key=lambda item: item.planned_date).recipe.tags)
            if earlier_entries
            else set()
        )
        selected = self._select_candidate(
            candidates=candidates,
            target_date=entry.planned_date,
            used_tags=used_tags,
            previous_tags=previous_tags,
            rng=random.Random(seed),
        )
        if selected is None:
            raise MealPlanEntryCannotRerollError(
                "No alternative recipe satisfies the generation rules"
            )
        candidate, score, reasons = selected
        entry.recipe = candidate.recipe
        plan.generation_seed = seed
        self.session.commit()
        self.session.expire_all()
        stored_plan = self._require_plan(plan_id)
        logger.info(
            "Rerolled generated meal-plan entry",
            extra={"plan_id": plan_id, "entry_id": entry_id, "generation_seed": seed},
        )
        return MealPlanGenerationResponse(
            plan=map_meal_plan_detail(stored_plan),
            unfilled_slots=[
                UnfilledMealPlanSlot(
                    planned_date=target_date,
                    meal_type=request.meal_type,
                    reason="Geen recepten voldoen aan de ingestelde filters.",
                )
                for target_date in self._missing_required_slots(
                    stored_plan,
                    request,
                )
            ],
            selection_explanations=[
                MealPlanSelectionExplanation(
                    planned_date=entry.planned_date,
                    meal_type=entry.meal_type,
                    recipe_identifier=candidate.identifier,
                    score=score,
                    reasons=reasons,
                )
            ],
            generation_seed=seed,
        )

    def _select_candidate(
        self,
        *,
        candidates: list[RecipeCandidate],
        target_date: date,
        used_tags: set[str],
        previous_tags: set[str],
        rng: random.Random,
    ) -> tuple[RecipeCandidate, float, list[str]] | None:
        if not candidates:
            return None
        context = PlanningContext(
            target_date=target_date,
            used_tags=used_tags,
            previous_tags=previous_tags,
        )
        scored: list[tuple[RecipeCandidate, float, list[str]]] = []
        for candidate in candidates:
            results = [
                rule.score(candidate=candidate, context=context) for rule in self.rules
            ]
            scored.append(
                (
                    candidate,
                    sum(result.score for result in results),
                    [result.reason for result in results if result.reason],
                )
            )
        highest_score = max(item[1] for item in scored)
        tied = [item for item in scored if item[1] == highest_score]
        return rng.choice(tied)

    @staticmethod
    def _copy_existing_entries(
        source_plan: MealPlanRecord,
        target_plan: MealPlanRecord,
    ) -> None:
        for entry in source_plan.entries:
            target_plan.entries.append(
                MealPlanEntryRecord(
                    recipe=entry.recipe,
                    planned_date=entry.planned_date,
                    meal_type=entry.meal_type,
                    servings=entry.servings,
                    notes=entry.notes,
                    source=entry.source,
                )
            )

    @staticmethod
    def _entry_for_slot(
        plan: MealPlanRecord,
        planned_date: date,
        meal_type: str,
    ) -> MealPlanEntryRecord | None:
        return next(
            (
                entry
                for entry in plan.entries
                if entry.planned_date == planned_date and entry.meal_type == meal_type
            ),
            None,
        )

    @staticmethod
    def _target_dates(request: MealPlanGenerationRequest) -> list[date]:
        if request.start_date is None:
            raise InvalidMealPlanGenerationConfigError(
                "Generation start date is missing"
            )
        weekdays = set(
            range(7) if request.days_to_plan is None else request.days_to_plan
        )
        return [
            request.start_date + timedelta(days=offset)
            for offset in range(7)
            if (request.start_date + timedelta(days=offset)).weekday() in weekdays
        ]

    def _missing_required_slots(
        self,
        plan: MealPlanRecord,
        request: MealPlanGenerationRequest,
    ) -> list[date]:
        return [
            target_date
            for target_date in self._target_dates(request)
            if self._entry_for_slot(plan, target_date, request.meal_type) is None
        ]

    @staticmethod
    def _validate_entries(plan: MealPlanRecord) -> None:
        end_date = plan.start_date + timedelta(days=6)
        slots: set[tuple[date, str]] = set()
        for entry in plan.entries:
            if not plan.start_date <= entry.planned_date <= end_date:
                raise MealPlanCannotActivateError(
                    "Draft contains an entry outside its date range"
                )
            if entry.servings < 1 or entry.recipe is None:
                raise MealPlanCannotActivateError("Draft contains an invalid entry")
            slot = (entry.planned_date, entry.meal_type)
            if slot in slots:
                raise MealPlanCannotActivateError("Draft contains duplicate meal slots")
            slots.add(slot)

    def _request_from_plan(
        self,
        plan: MealPlanRecord,
    ) -> MealPlanGenerationRequest:
        if plan.generation_config is None:
            raise InvalidMealPlanGenerationConfigError(
                "Draft has no generation configuration"
            )
        try:
            return MealPlanGenerationRequest.model_validate(plan.generation_config)
        except ValidationError as exc:
            raise InvalidMealPlanGenerationConfigError(
                "Stored generation configuration is invalid"
            ) from exc

    def _require_plan(self, plan_id: int) -> MealPlanRecord:
        plan = self.meal_plan_repository.get_by_id(plan_id)
        if plan is None:
            raise MealPlanDraftNotFoundError("Meal-plan draft not found")
        return plan

    def _require_draft(self, plan_id: int) -> MealPlanRecord:
        plan = self._require_plan(plan_id)
        if plan.status == MealPlanStatus.ACTIVE.value:
            raise MealPlanAlreadyActiveError("Meal plan is already active")
        if plan.status != MealPlanStatus.DRAFT.value:
            raise MealPlanDraftNotFoundError("Meal-plan draft not found")
        return plan
