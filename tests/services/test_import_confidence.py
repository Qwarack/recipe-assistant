from app.models.import_result import ImportResult, ImportStatus, ImportWarning
from app.models.import_session import ConfidenceAction, ParseMethod
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.import_confidence import ConfidencePolicy


def _complete_result(*, confidence: float | None = None) -> ImportResult:
    recipe = Recipe(
        title="Soep",
        source_type=SourceType.MANUAL,
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        difficulty="easy",
        ingredients=[Ingredient(name="water", quantity=1, unit="l")],
        instructions=["Kook het water."],
        tags=["soep"],
        meal_types=["dinner"],
    )
    return ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=recipe,
        confidence=confidence,
    )


def test_high_confidence_result_is_ready() -> None:
    assessment = ConfidencePolicy().assess(
        _complete_result(confidence=0.98),
        method=ParseMethod.NORMAL,
    )

    assert assessment.score == 0.98
    assert assessment.action is ConfidenceAction.READY
    assert assessment.reasons == []


def test_parser_confidence_is_capped_by_structural_quality() -> None:
    result = _complete_result(confidence=0.99)
    result.recipe = result.recipe.model_copy(
        update={
            "servings": None,
            "prep_time_minutes": None,
            "cook_time_minutes": None,
            "total_time_minutes": None,
            "difficulty": "unknown",
            "tags": [],
            "meal_types": [],
        }
    )

    assessment = ConfidencePolicy().assess(
        result,
        method=ParseMethod.NORMAL,
    )

    assert assessment.score == 0.79
    assert assessment.action is ConfidenceAction.TRY_LOCAL_AI
    assert "missing:tags" in assessment.reasons


def test_first_uncertain_local_result_requests_one_retry() -> None:
    assessment = ConfidencePolicy().assess(
        _complete_result(),
        method=ParseMethod.AI_TEXT,
        model_confidence=0.70,
        local_successful_attempts=1,
    )

    assert assessment.score == 0.70
    assert assessment.action is ConfidenceAction.RETRY_LOCAL_AI


def test_second_uncertain_local_result_offers_openai() -> None:
    assessment = ConfidencePolicy().assess(
        _complete_result(),
        method=ParseMethod.AI_REPARSE,
        model_confidence=0.70,
        local_successful_attempts=2,
    )

    assert assessment.action is ConfidenceAction.OFFER_OPENAI


def test_very_low_local_result_offers_openai_immediately() -> None:
    result = _complete_result()
    result.warnings.append(
        ImportWarning(code="ocr_unclear", message="De foto is moeilijk leesbaar.")
    )

    assessment = ConfidencePolicy().assess(
        result,
        method=ParseMethod.AI_IMAGE,
        model_confidence=0.40,
        local_successful_attempts=1,
    )

    assert assessment.score == 0.40
    assert assessment.action is ConfidenceAction.OFFER_OPENAI


def test_low_openai_result_requires_manual_review() -> None:
    assessment = ConfidencePolicy().assess(
        _complete_result(),
        method=ParseMethod.OPENAI_FALLBACK,
        model_confidence=0.70,
    )

    assert assessment.action is ConfidenceAction.MANUAL_REVIEW
