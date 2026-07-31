import logging
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError

from app.ai.exceptions import AIValidationError
from app.ai.prompts import build_full_recipe_extraction_prompt
from app.ai.protocols import JSONGenerator
from app.ai.schemas import (
    AI_RECIPE_FIELD_NAMES,
    AI_RECIPE_MEAL_TYPES,
    AIIngredient,
    AIRecipeResult,
)
from app.models.recipe import Ingredient, Recipe, SourceType

logger = logging.getLogger(__name__)

_REQUIRED_RECIPE_FIELDS = frozenset({"title", "ingredients", "instructions"})
_STRING_LIST_FIELDS = frozenset(
    {
        "instructions",
        "cuisine",
        "meal_types",
        "dietary",
        "tags",
        "warnings",
        "estimated_fields",
        "confidence_reasons",
    }
)
_REPAIR_WARNING = (
    "De AI-uitvoer bevatte ongeldige aanvullende metadata. Het bruikbare "
    "recept is behouden; controleer de preview extra zorgvuldig."
)
_REPAIR_CONFIDENCE_REASON = (
    "Herstelbare schema-afwijkingen in de AI-uitvoer zijn automatisch gecorrigeerd."
)
_REPAIRED_CONFIDENCE_CAP = 0.90


@dataclass(frozen=True, slots=True)
class AIRecipeContext:
    source_type: SourceType
    source_url: str | None = None
    source_name: str | None = None


@dataclass(frozen=True, slots=True)
class AIRecipeImport:
    recipe: Recipe
    extracted_fields: list[str]
    estimated_fields: list[str]
    warnings: list[str]
    confidence: float | None = None
    confidence_reasons: list[str] = field(default_factory=list)


class AIRecipeImporter:
    def __init__(
        self,
        *,
        client: JSONGenerator,
        max_source_characters: int = 50_000,
    ) -> None:
        self.client = client
        self.max_source_characters = max_source_characters

    async def import_text(
        self,
        source_text: str,
        *,
        context: AIRecipeContext,
    ) -> AIRecipeImport:
        prompt = build_full_recipe_extraction_prompt(
            source_text=source_text,
            image_input=False,
            max_source_characters=self.max_source_characters,
            include_schema=self.client.uses_structured_outputs is not True,
        )
        payload = await self.client.generate_json(
            prompt=prompt.input,
            instructions=prompt.instructions,
        )
        return self._validate_and_map(payload, context=context)

    async def import_image(
        self,
        image: bytes,
        *,
        context: AIRecipeContext,
        source_text: str | None = None,
    ) -> AIRecipeImport:
        prompt = build_full_recipe_extraction_prompt(
            source_text=source_text,
            image_input=True,
            max_source_characters=self.max_source_characters,
            include_schema=self.client.uses_structured_outputs is not True,
        )
        payload = await self.client.generate_json(
            prompt=prompt.input,
            instructions=prompt.instructions,
            images=[image],
        )
        return self._validate_and_map(payload, context=context)

    def _validate_and_map(
        self,
        payload: dict[str, object],
        *,
        context: AIRecipeContext,
    ) -> AIRecipeImport:
        try:
            result = AIRecipeResult.model_validate(payload)
        except ValidationError as original_error:
            repaired = _repair_recoverable_ai_payload(payload)
            if repaired is None:
                raise AIValidationError(
                    "The model output does not satisfy the recipe schema"
                ) from original_error

            result, repaired_fields = repaired
            logger.warning(
                "Recovered an AI recipe with invalid non-essential output fields",
                extra={"ai_repaired_fields": sorted(repaired_fields)},
            )
            result = result.model_copy(
                update={
                    "warnings": list(
                        dict.fromkeys([*result.warnings, _REPAIR_WARNING])
                    ),
                    "confidence": min(
                        result.confidence
                        if result.confidence is not None
                        else _REPAIRED_CONFIDENCE_CAP,
                        _REPAIRED_CONFIDENCE_CAP,
                    ),
                    "confidence_reasons": list(
                        dict.fromkeys(
                            [
                                *result.confidence_reasons,
                                _REPAIR_CONFIDENCE_REASON,
                            ]
                        )
                    ),
                }
            )

        return map_ai_result_to_recipe(
            result,
            context=context,
            model=self.client.model,
            provider=self.client.provider,
        )


def _repair_recoverable_ai_payload(
    payload: dict[str, object],
) -> tuple[AIRecipeResult, set[str]] | None:
    """Keep a valid recipe core when only AI output metadata is malformed."""
    candidate: dict[str, Any] = deepcopy(payload)
    repaired_fields: set[str] = set()
    model_fields = AIRecipeResult.model_fields

    for field_name in set(candidate) - set(model_fields):
        candidate.pop(field_name)
        repaired_fields.add(field_name)

    for field_name in _STRING_LIST_FIELDS:
        value = candidate.get(field_name)
        if isinstance(value, str):
            candidate[field_name] = [value]
            repaired_fields.add(field_name)

    ingredients = candidate.get("ingredients")
    if isinstance(ingredients, dict):
        candidate["ingredients"] = [ingredients]
        repaired_fields.add("ingredients")

    _filter_allowed_list_values(
        candidate,
        field_name="estimated_fields",
        allowed=AI_RECIPE_FIELD_NAMES,
        repaired_fields=repaired_fields,
    )
    _filter_allowed_list_values(
        candidate,
        field_name="meal_types",
        allowed=AI_RECIPE_MEAL_TYPES,
        repaired_fields=repaired_fields,
    )

    for _ in range(len(model_fields)):
        try:
            return AIRecipeResult.model_validate(candidate), repaired_fields
        except ValidationError as error:
            invalid_optional_fields: set[str] = set()
            made_change = False

            for detail in error.errors():
                location = detail.get("loc", ())
                top_level = location[0] if location else None
                if not isinstance(top_level, str):
                    return None
                if top_level in _REQUIRED_RECIPE_FIELDS:
                    if top_level == "ingredients" and _repair_ingredient_detail(
                        candidate,
                        location=location,
                        repaired_fields=repaired_fields,
                    ):
                        made_change = True
                        continue
                    return None
                if top_level not in model_fields:
                    return None
                invalid_optional_fields.add(top_level)

            if not invalid_optional_fields and not made_change:
                return None

            for field_name in invalid_optional_fields:
                default = model_fields[field_name].get_default(
                    call_default_factory=True
                )
                if candidate.get(field_name) != default:
                    candidate[field_name] = default
                    repaired_fields.add(field_name)
                    made_change = True

            if not made_change:
                return None

    return None


def _repair_ingredient_detail(
    candidate: dict[str, Any],
    *,
    location: tuple[int | str, ...],
    repaired_fields: set[str],
) -> bool:
    if len(location) < 3 or not isinstance(location[1], int):
        return False

    ingredients = candidate.get("ingredients")
    index = location[1]
    field_name = location[2]
    if (
        not isinstance(ingredients, list)
        or index >= len(ingredients)
        or not isinstance(ingredients[index], dict)
        or not isinstance(field_name, str)
        or field_name == "name"
    ):
        return False

    ingredient = ingredients[index]
    ingredient_fields = AIIngredient.model_fields
    repair_label = f"ingredients.{field_name}"

    if field_name not in ingredient_fields:
        if field_name not in ingredient:
            return False
        ingredient.pop(field_name)
        repaired_fields.add(repair_label)
        return True

    default = ingredient_fields[field_name].get_default(call_default_factory=True)
    if ingredient.get(field_name) == default:
        return False

    ingredient[field_name] = default
    repaired_fields.add(repair_label)
    return True


def _filter_allowed_list_values(
    candidate: dict[str, Any],
    *,
    field_name: str,
    allowed: frozenset[str],
    repaired_fields: set[str],
) -> None:
    value = candidate.get(field_name)
    if not isinstance(value, list):
        return

    filtered = [item for item in value if isinstance(item, str) and item in allowed]
    if filtered != value:
        candidate[field_name] = filtered
        repaired_fields.add(field_name)


def map_ai_result_to_recipe(
    result: AIRecipeResult,
    *,
    context: AIRecipeContext,
    model: str,
    provider: str = "ollama",
) -> AIRecipeImport:
    missing_required: list[str] = []

    if result.title is None:
        missing_required.append("title")
    if not result.ingredients:
        missing_required.append("ingredients")
    if not result.instructions:
        missing_required.append("instructions")

    if missing_required:
        fields = ", ".join(missing_required)
        raise AIValidationError(
            f"No complete recipe was recognized; missing required fields: {fields}"
        )

    ingredients = [
        Ingredient(
            name=ingredient.name,
            quantity=ingredient.quantity,
            unit=ingredient.unit,
            preparation=ingredient.preparation,
            optional=ingredient.optional,
        )
        for ingredient in result.ingredients
    ]
    dietary = {value.casefold() for value in result.dietary}

    recipe = Recipe(
        title=result.title,
        source_type=context.source_type,
        source_url=context.source_url,
        source_name=context.source_name,
        extractor=f"{provider}:{model}",
        imported_at=datetime.now(UTC),
        servings=result.servings,
        prep_time_minutes=result.prep_time_minutes,
        cook_time_minutes=result.cook_time_minutes,
        total_time_minutes=result.total_time_minutes,
        difficulty=result.difficulty or "unknown",
        vegetarian=True if "vegetarian" in dietary or "vegan" in dietary else None,
        vegan=True if "vegan" in dietary else None,
        ingredients=ingredients,
        instructions=result.instructions,
        tags=[*result.tags, *result.cuisine, *result.dietary],
        meal_types=result.meal_types,
    )

    raw_fields = result.model_dump()
    extracted_fields = [
        field_name
        for field_name, value in raw_fields.items()
        if field_name
        not in {
            "warnings",
            "estimated_fields",
            "description",
            "confidence",
            "confidence_reasons",
        }
        and field_name not in result.estimated_fields
        and value not in (None, "", [])
    ]

    return AIRecipeImport(
        recipe=recipe,
        extracted_fields=extracted_fields,
        estimated_fields=result.estimated_fields,
        warnings=list(dict.fromkeys(result.warnings)),
        confidence=result.confidence,
        confidence_reasons=list(dict.fromkeys(result.confidence_reasons)),
    )
