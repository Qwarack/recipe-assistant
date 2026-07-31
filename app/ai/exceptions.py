class AIServiceError(RuntimeError):
    """Base error for failures in an AI integration."""


class AIUnavailableError(AIServiceError):
    """An AI provider cannot currently process a request."""


class AITimeoutError(AIUnavailableError):
    """An AI provider did not finish within the configured timeout."""


class AIModelNotFoundError(AIUnavailableError):
    """The configured model is not installed in Ollama."""


class AIInvalidResponseError(AIServiceError):
    """An AI provider returned an empty or invalid JSON response."""


class AIValidationError(AIServiceError):
    """The model JSON does not satisfy the recipe contract."""


class AIAuthenticationError(AIUnavailableError):
    """The OpenAI API key is missing, invalid or unauthorized."""


class AIRateLimitError(AIUnavailableError):
    """The OpenAI account is rate limited or has insufficient quota."""


class AIFallbackNotAllowedError(AIServiceError):
    """The paid cloud fallback is not allowed before a failed local attempt."""
