import json
from dataclasses import dataclass

from app.ai.exceptions import AIValidationError
from app.ai.prompts import build_enrichment_prompt
from app.ai.protocols import JSONGenerator
from app.ai.schemas import AIRecipeResult
from app.models.recipe import Recipe
from pydantic import BaseModel, Field, ValidationError


class MissingFieldReport(BaseModel):
    required: list[str] = Field(default_factory=list)
    enrichable: list[str] = Field(default_factory=list)
    unsafe_to_guess: list[str] = Field(default_factory=list)

    @property
    def has_missing_fields(self) -> bool:
        return bool(self.required or self.enrichable or self.unsafe_to_guess)


@dataclass(frozen=True, slots=True)
class EnrichmentResult:
    recipe: Recipe
    extracted_fields: list[str]
    estimated_fields: list[str]
    warnings: list[str]


def detect_missing_fields(recipe: Recipe) -> MissingFieldReport:
    report = MissingFieldReport()

    if recipe.servings is None:
        report.enrichable.append("servings")
    if recipe.prep_time_minutes is None:
        report.enrichable.append("prep_time_minutes")
    if recipe.cook_time_minutes is None:
        report.enrichable.append("cook_time_minutes")
    if recipe.total_time_minutes is None:
        report.enrichable.append("total_time_minutes")
    if recipe.difficulty == "unknown":
        report.enrichable.append("difficulty")
    if not recipe.meal_types:
        report.enrichable.append("meal_types")
    if not recipe.tags:
        report.enrichable.append("tags")

    for index, ingredient in enumerate(recipe.ingredients):
        if ingredient.quantity is None:
            report.unsafe_to_guess.append(f"ingredients.{index}.quantity")

    return report


class RecipeEnrichmentService:
    def __init__(
        self,
        *,
        client: JSONGenerator,
        max_source_characters: int = 50_000,
    ) -> None:
        self.client = client
        self.max_source_characters = max_source_characters

    async def enrich(
        self,
        *,
        recipe: Recipe,
        source_context: str,
        report: MissingFieldReport,
    ) -> EnrichmentResult:
        if not report.enrichable:
            return EnrichmentResult(
                recipe=recipe,
                extracted_fields=[],
                estimated_fields=[],
                warnings=[],
            )

        prompt = build_enrichment_prompt(
            recipe_json=json.dumps(
                recipe.model_dump(mode="json"),
                ensure_ascii=False,
                separators=(",", ":"),
            ),
            source_text=source_context,
            missing_fields=report.enrichable,
            unsafe_to_guess=report.unsafe_to_guess,
            max_source_characters=self.max_source_characters,
        )
        payload = await self.client.generate_json(
            prompt=prompt.input,
            instructions=prompt.instructions,
        )

        try:
            enrichment = AIRecipeResult.model_validate(payload)
        except ValidationError as exc:
            raise AIValidationError(
                "The enrichment output does not satisfy the recipe schema"
            ) from exc

        return merge_enrichment(
            original=recipe,
            enrichment=enrichment,
            allowed_fields=report.enrichable,
        )


def merge_enrichment(
    *,
    original: Recipe,
    enrichment: AIRecipeResult,
    allowed_fields: list[str] | None = None,
) -> EnrichmentResult:
    allowed = set(
        allowed_fields
        or [
            "servings",
            "prep_time_minutes",
            "cook_time_minutes",
            "total_time_minutes",
            "difficulty",
            "meal_types",
            "tags",
        ]
    )
    recipe_data = original.model_dump()
    merged_fields: list[str] = []

    scalar_fields = (
        "servings",
        "prep_time_minutes",
        "cook_time_minutes",
        "total_time_minutes",
    )

    for field_name in scalar_fields:
        new_value = getattr(enrichment, field_name)
        if (
            field_name in allowed
            and getattr(original, field_name) is None
            and new_value is not None
        ):
            recipe_data[field_name] = new_value
            merged_fields.append(field_name)

    if (
        "difficulty" in allowed
        and original.difficulty == "unknown"
        and enrichment.difficulty
    ):
        recipe_data["difficulty"] = enrichment.difficulty
        merged_fields.append("difficulty")

    if "meal_types" in allowed and not original.meal_types and enrichment.meal_types:
        recipe_data["meal_types"] = enrichment.meal_types
        merged_fields.append("meal_types")

    enriched_tags = [
        *enrichment.tags,
        *enrichment.cuisine,
        *enrichment.dietary,
    ]
    if "tags" in allowed and not original.tags and enriched_tags:
        recipe_data["tags"] = enriched_tags
        merged_fields.append("tags")

    try:
        recipe = Recipe.model_validate(recipe_data)
    except ValidationError as exc:
        raise AIValidationError(
            "The enriched recipe does not satisfy the recipe model"
        ) from exc

    estimated_fields = [
        field_name
        for field_name in merged_fields
        if field_name in enrichment.estimated_fields
        or (
            field_name == "tags"
            and any(
                source_field in enrichment.estimated_fields
                for source_field in ("tags", "cuisine", "dietary")
            )
        )
    ]
    extracted_fields = [
        field_name for field_name in merged_fields if field_name not in estimated_fields
    ]

    return EnrichmentResult(
        recipe=recipe,
        extracted_fields=extracted_fields,
        estimated_fields=estimated_fields,
        warnings=list(dict.fromkeys(enrichment.warnings)),
    )
