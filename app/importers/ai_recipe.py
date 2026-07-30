from dataclasses import dataclass
from datetime import UTC, datetime

from pydantic import ValidationError

from app.ai.client import OllamaClient
from app.ai.exceptions import AIValidationError
from app.ai.prompts import build_full_recipe_extraction_prompt
from app.ai.schemas import AIRecipeResult
from app.models.recipe import Ingredient, Recipe, SourceType


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


class AIRecipeImporter:
    def __init__(
        self,
        *,
        client: OllamaClient,
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
        )
        payload = await self.client.generate_json(prompt=prompt)
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
        )
        payload = await self.client.generate_json(
            prompt=prompt,
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
        except ValidationError as exc:
            raise AIValidationError(
                "The model output does not satisfy the recipe schema"
            ) from exc

        return map_ai_result_to_recipe(result, context=context, model=self.client.model)


def map_ai_result_to_recipe(
    result: AIRecipeResult,
    *,
    context: AIRecipeContext,
    model: str,
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
        extractor=f"ollama:{model}",
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
        if field_name not in {"warnings", "estimated_fields", "description"}
        and field_name not in result.estimated_fields
        and value not in (None, "", [])
    ]

    return AIRecipeImport(
        recipe=recipe,
        extracted_fields=extracted_fields,
        estimated_fields=result.estimated_fields,
        warnings=list(dict.fromkeys(result.warnings)),
    )
