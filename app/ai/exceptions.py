class AIServiceError(RuntimeError):
    """Base error for failures in the local AI integration."""


class AIUnavailableError(AIServiceError):
    """Ollama cannot currently process a request."""


class AITimeoutError(AIUnavailableError):
    """Ollama did not finish within the configured timeout."""


class AIModelNotFoundError(AIUnavailableError):
    """The configured model is not installed in Ollama."""


class AIInvalidResponseError(AIServiceError):
    """Ollama returned an empty or invalid JSON response."""


class AIValidationError(AIServiceError):
    """The model JSON does not satisfy the recipe contract."""
