import hashlib
import json
from decimal import Decimal

from app.models.recipe import Recipe
from app.utils.title_normalizer import normalize_title


def normalize_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None

    normalized = value.normalize()

    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))

    return format(normalized, "f")


def calculate_recipe_hash(recipe: Recipe) -> str:
    payload = {
        "title": normalize_title(recipe.title),
        "ingredients": [
            {
                "quantity": normalize_decimal(ingredient.quantity),
                "unit": (
                    ingredient.unit.casefold().strip()
                    if ingredient.unit is not None
                    else None
                ),
                "name": ingredient.name.casefold().strip(),
                "preparation": (
                    ingredient.preparation.casefold().strip()
                    if ingredient.preparation is not None
                    else None
                ),
            }
            for ingredient in recipe.ingredients
        ],
        "instructions": [
            " ".join(instruction.casefold().split())
            for instruction in recipe.instructions
        ],
    }

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
