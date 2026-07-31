from dataclasses import dataclass

from app.models.import_result import ImportResult
from app.models.import_session import ConfidenceAction, ParseMethod

LOCAL_AI_METHODS = {
    ParseMethod.AI_TEXT,
    ParseMethod.AI_IMAGE,
    ParseMethod.AI_REPARSE,
}


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    score: float
    action: ConfidenceAction
    reasons: list[str]


@dataclass(frozen=True, slots=True)
class ConfidencePolicy:
    high_threshold: float = 0.95
    warning_threshold: float = 0.80
    retry_threshold: float = 0.60
    max_local_retries: int = 1

    def __post_init__(self) -> None:
        if not (
            0
            <= self.retry_threshold
            < self.warning_threshold
            < self.high_threshold
            <= 1
        ):
            raise ValueError("Confidence thresholds must be ordered between 0 and 1")
        if self.max_local_retries < 0:
            raise ValueError("max_local_retries cannot be negative")

    def assess(
        self,
        result: ImportResult,
        *,
        method: ParseMethod,
        model_confidence: float | None = None,
        model_reasons: list[str] | None = None,
        estimated_fields: list[str] | None = None,
        local_successful_attempts: int = 0,
    ) -> ConfidenceAssessment:
        if result.recipe is None:
            return ConfidenceAssessment(
                score=0.0,
                action=(
                    ConfidenceAction.TRY_LOCAL_AI
                    if method is ParseMethod.NORMAL
                    else ConfidenceAction.OFFER_OPENAI
                ),
                reasons=["recipe_missing"],
            )

        structural_score, structural_reasons = self._structural_score(
            result,
            estimated_fields=estimated_fields or [],
        )
        candidates = [structural_score]
        if result.confidence is not None:
            candidates.append(result.confidence)
        if model_confidence is not None:
            candidates.append(model_confidence)

        raw_score = max(0.0, min(candidates))
        score = round(raw_score, 2)
        reasons = list(
            dict.fromkeys(
                [
                    *(model_reasons or []),
                    *structural_reasons,
                ]
            )
        )
        action = self._action_for(
            raw_score,
            method=method,
            local_successful_attempts=local_successful_attempts,
        )
        return ConfidenceAssessment(score=score, action=action, reasons=reasons)

    def _action_for(
        self,
        score: float,
        *,
        method: ParseMethod,
        local_successful_attempts: int,
    ) -> ConfidenceAction:
        if method is ParseMethod.OPENAI_FALLBACK:
            if score >= self.high_threshold:
                return ConfidenceAction.READY
            if score >= self.warning_threshold:
                return ConfidenceAction.REVIEW_WARNING
            return ConfidenceAction.MANUAL_REVIEW

        if method is ParseMethod.NORMAL:
            if score >= self.high_threshold:
                return ConfidenceAction.READY
            if score >= self.warning_threshold:
                return ConfidenceAction.REVIEW_WARNING
            return ConfidenceAction.TRY_LOCAL_AI

        if method in LOCAL_AI_METHODS:
            if score >= self.high_threshold:
                return ConfidenceAction.READY
            if score >= self.warning_threshold:
                return ConfidenceAction.REVIEW_WARNING
            if score < self.retry_threshold:
                return ConfidenceAction.OFFER_OPENAI
            if local_successful_attempts > self.max_local_retries:
                return ConfidenceAction.OFFER_OPENAI
            return ConfidenceAction.RETRY_LOCAL_AI

        if score >= self.high_threshold:
            return ConfidenceAction.READY
        if score >= self.warning_threshold:
            return ConfidenceAction.REVIEW_WARNING
        return ConfidenceAction.MANUAL_REVIEW

    @staticmethod
    def _structural_score(
        result: ImportResult,
        *,
        estimated_fields: list[str],
    ) -> tuple[float, list[str]]:
        recipe = result.recipe
        if recipe is None:
            return 0.0, ["recipe_missing"]

        score = 1.0
        reasons: list[str] = []

        missing_penalties = (
            ("servings", recipe.servings is None, 0.05),
            ("prep_time_minutes", recipe.prep_time_minutes is None, 0.03),
            ("cook_time_minutes", recipe.cook_time_minutes is None, 0.03),
            ("total_time_minutes", recipe.total_time_minutes is None, 0.02),
            ("difficulty", recipe.difficulty == "unknown", 0.02),
            ("meal_types", not recipe.meal_types, 0.03),
            ("tags", not recipe.tags, 0.03),
        )
        for field_name, missing, penalty in missing_penalties:
            if missing:
                score -= penalty
                reasons.append(f"missing:{field_name}")

        missing_quantities = sum(
            ingredient.quantity is None for ingredient in recipe.ingredients
        )
        if missing_quantities:
            ratio = missing_quantities / len(recipe.ingredients)
            score -= min(0.10, 0.10 * ratio)
            reasons.append("ingredient_quantities_missing")

        relevant_warnings = [
            warning
            for warning in result.warnings
            if warning.code != "confidence_review_recommended"
        ]
        if relevant_warnings:
            score -= min(0.15, 0.04 * len(relevant_warnings))
            reasons.append("parser_warnings")

        if estimated_fields:
            score -= min(0.10, 0.02 * len(set(estimated_fields)))
            reasons.append("estimated_fields")

        return max(0.0, score), reasons
