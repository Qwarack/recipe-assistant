from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from app.services.recipe_candidate_service import RecipeCandidate


@dataclass(slots=True)
class PlanningContext:
    target_date: date
    used_tags: set[str] = field(default_factory=set)
    previous_tags: set[str] = field(default_factory=set)


@dataclass(frozen=True, slots=True)
class RuleScore:
    score: float
    reason: str | None = None


class PlanningRule(Protocol):
    def score(
        self,
        *,
        candidate: RecipeCandidate,
        context: PlanningContext,
    ) -> RuleScore: ...


class RecencyRule:
    def score(
        self,
        *,
        candidate: RecipeCandidate,
        context: PlanningContext,
    ) -> RuleScore:
        last_planned = candidate.recipe.last_planned_at
        if last_planned is None:
            return RuleScore(5.0, "Nog niet eerder gepland")
        days_ago = max(0, (context.target_date - last_planned.date()).days)
        score = min(5.0, days_ago / 30)
        return RuleScore(score, f"{days_ago} dagen geleden gepland")


class PreparationTimeRule:
    def score(
        self,
        *,
        candidate: RecipeCandidate,
        context: PlanningContext,
    ) -> RuleScore:
        minutes = candidate.recipe.preparation_time_minutes
        if minutes is None:
            return RuleScore(0.0, "Bereidingstijd onbekend")
        if context.target_date.weekday() < 5:
            score = max(-2.0, min(3.0, (60 - minutes) / 20))
            return RuleScore(score, f"{minutes} minuten op een werkdag")
        score = min(2.0, minutes / 60)
        return RuleScore(score, f"{minutes} minuten in het weekend")


class TagVarietyRule:
    def score(
        self,
        *,
        candidate: RecipeCandidate,
        context: PlanningContext,
    ) -> RuleScore:
        tags = candidate.tags
        if not tags:
            return RuleScore(0.0, "Geen tags voor variatiescore")
        if tags & context.previous_tags:
            return RuleScore(-3.0, "Deelt tags met de vorige maaltijd")
        if tags - context.used_tags:
            return RuleScore(3.0, "Voegt nieuwe tags toe aan de week")
        return RuleScore(0.0, "Neutrale tagvariatie")


class DifficultyRule:
    def score(
        self,
        *,
        candidate: RecipeCandidate,
        context: PlanningContext,
    ) -> RuleScore:
        difficulty = candidate.recipe.difficulty
        weekend = context.target_date.weekday() >= 5
        if weekend and difficulty in {"hard", "moeilijk"}:
            return RuleScore(1.5, "Uitgebreider recept past bij het weekend")
        if not weekend and difficulty in {"easy", "makkelijk"}:
            return RuleScore(1.5, "Makkelijk recept past bij een werkdag")
        return RuleScore(0.0, "Neutrale moeilijkheid")
