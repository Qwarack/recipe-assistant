class MealPlanError(Exception):
    """Base exception for meal-planning domain errors."""


class MealPlanNotFoundError(MealPlanError):
    """Raised when a meal plan cannot be found."""


class MealPlanEntryNotFoundError(MealPlanError):
    """Raised when an entry is absent from the requested meal plan."""


class RecipeNotFoundError(MealPlanError):
    """Raised when a recipe identifier is unknown."""


class MealPlanDateOutsideRangeError(MealPlanError):
    """Raised when a date is outside the seven-day plan period."""


class MealPlanSlotOccupiedError(MealPlanError):
    """Raised when another entry already occupies a meal slot."""


class InvalidServingsError(MealPlanError):
    """Raised when a serving count is invalid."""
