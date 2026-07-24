class PlatformError(Exception):
    """Base class for domain errors. status_code maps to the HTTP response."""

    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class RuleValidationError(PlatformError):
    status_code = 422


class RuleNotFoundError(PlatformError):
    status_code = 404


class ProductNotFoundError(PlatformError):
    status_code = 404


class DecisionNotFoundError(PlatformError):
    status_code = 404


class LLMError(PlatformError):
    status_code = 502
