class PlatformError(Exception):
    """Base class for domain errors. status_code maps to the HTTP response."""

    status_code = 400

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.message = message
        self.detail = detail  # extra structured data merged into the error response


class RuleValidationError(PlatformError):
    status_code = 422


class RuleConflictError(PlatformError):
    """Raised when a rule save would duplicate/overlap an existing rule and the
    caller hasn't explicitly confirmed (RuleCreate.confirm_conflict). `detail`
    carries the ConflictCheckResult so the client can show which rule(s) and why."""

    status_code = 409


class RuleNotFoundError(PlatformError):
    status_code = 404


class ProductNotFoundError(PlatformError):
    status_code = 404


class DecisionNotFoundError(PlatformError):
    status_code = 404


class LLMError(PlatformError):
    status_code = 502
