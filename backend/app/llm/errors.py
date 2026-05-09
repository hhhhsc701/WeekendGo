class LLMError(RuntimeError):
    """Base LLM integration error."""


class LLMConfigurationError(LLMError):
    """Raised when required LLM settings are missing."""


class LLMOutputValidationError(LLMError):
    """Raised when an LLM response cannot be parsed or validated."""
