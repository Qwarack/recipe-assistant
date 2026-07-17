class MealPlanGenerationError(Exception):
    """Base exception for automatic planning failures."""


class InvalidMealPlanGenerationConfigError(MealPlanGenerationError):
    """Raised when stored generation settings are invalid."""


class MealPlanDraftNotFoundError(MealPlanGenerationError):
    """Raised when a draft plan cannot be found."""


class MealPlanAlreadyActiveError(MealPlanGenerationError):
    """Raised when an active plan is treated as a draft."""


class MealPlanCannotActivateError(MealPlanGenerationError):
    """Raised when a draft does not pass activation validation."""


class MealPlanEntryCannotRerollError(MealPlanGenerationError):
    """Raised when a generated entry has no valid replacement."""
