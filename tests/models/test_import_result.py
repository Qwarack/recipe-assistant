from datetime import UTC, datetime

import pytest
from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from pydantic import ValidationError


def make_recipe() -> Recipe:
    return Recipe(
        title="Pasta",
        source_type=SourceType.MANUAL,
        ingredients=[
            Ingredient(name="pasta"),
        ],
        instructions=[
            "Cook the pasta.",
        ],
    )


def test_successful_import_contains_recipe() -> None:
    result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=make_recipe(),
        extractor="manual",
        confidence=1.0,
    )

    assert result.recipe is not None
    assert result.status is ImportStatus.SUCCESS
    assert result.confidence == 1.0


def test_partial_import_can_contain_warnings() -> None:
    result = ImportResult(
        status=ImportStatus.PARTIAL,
        recipe=make_recipe(),
        warnings=[
            ImportWarning(
                code="missing_servings",
                message="No servings value was found",
                field="servings",
            )
        ],
        confidence=0.75,
    )

    assert len(result.warnings) == 1
    assert result.warnings[0].code == "missing_servings"


def test_successful_import_requires_recipe() -> None:
    with pytest.raises(ValidationError):
        ImportResult(
            status=ImportStatus.SUCCESS,
        )


def test_failed_import_cannot_contain_recipe() -> None:
    with pytest.raises(ValidationError):
        ImportResult(
            status=ImportStatus.FAILED,
            recipe=make_recipe(),
        )


def test_confidence_must_be_between_zero_and_one() -> None:
    with pytest.raises(ValidationError):
        ImportResult(
            status=ImportStatus.SUCCESS,
            recipe=make_recipe(),
            confidence=1.5,
        )


def test_failed_import_can_exist_without_recipe() -> None:
    result = ImportResult(
        status=ImportStatus.FAILED,
        warnings=[
            ImportWarning(
                code="unsupported_source",
                message="The source could not be processed",
            )
        ],
    )

    assert result.recipe is None
    assert result.status is ImportStatus.FAILED


def test_import_result_created_at_uses_utc() -> None:
    result = ImportResult(
        status=ImportStatus.FAILED,
    )

    assert result.created_at.tzinfo is not None
    assert result.created_at.utcoffset() == UTC.utcoffset(result.created_at)


def test_import_result_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError):
        ImportResult(
            status=ImportStatus.FAILED,
            created_at=datetime(2026, 7, 14, 12, 0),
        )
