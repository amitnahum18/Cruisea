class ApifyError(Exception):
    """Base class for all Apify integration errors."""


class ApifyConfigError(ApifyError):
    """Missing or invalid client configuration (e.g. no API token)."""


class ApifyAuthError(ApifyError):
    """401/403 — token missing, revoked, or lacking access to this actor."""


class ApifyRateLimitError(ApifyError):
    """429 — too many requests; caller should back off."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class ApifyRunFailedError(ApifyError):
    """The actor ran but its own logic failed (bad input it didn't validate,
    the target site changed, upstream rate limiting, etc.)."""


class ApifyTimeoutError(ApifyError):
    """The actor did not finish within the configured timeout."""


class ApifyResponseError(ApifyError):
    """Apify returned a 2xx response we couldn't parse as expected."""
