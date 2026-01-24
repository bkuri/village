"""Village exception hierarchy with exit codes and recovery metadata."""

# Exit code constants (simple 0-5 range)
EXIT_SUCCESS = 0  # Operation succeeded
EXIT_ERROR = 1  # Generic error / failure
EXIT_NOT_READY = 2  # Not ready / precondition failed
EXIT_BLOCKED = 3  # No work available
EXIT_PARTIAL = 4  # Partial success (some ops succeeded, some failed)
EXIT_USAGE = 5  # Invalid usage / arguments


class VillageError(Exception):
    """Base exception for all Village errors."""

    def __init__(self, message: str, exit_code: int = EXIT_ERROR):
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code


class TransientError(VillageError):
    """
    Retryable errors (network glitches, temporary failures).

    Carries retry metadata for debugging.
    """

    def __init__(
        self,
        message: str,
        attempt: int = 1,
        max_attempts: int = 3,
        retry_in: int | None = None,
    ):
        super().__init__(message, exit_code=EXIT_NOT_READY)
        self.attempt = attempt
        self.max_attempts = max_attempts
        self.retry_in = retry_in


class PermanentError(VillageError):
    """Non-retryable errors (config errors, missing dependencies)."""

    exit_code = EXIT_ERROR


class ConfigError(PermanentError):
    """Configuration errors (invalid values, missing files)."""

    exit_code = EXIT_ERROR

    def __init__(self, message: str = "Configuration error"):
        super().__init__(message, exit_code=self.exit_code)


class UserInputError(VillageError):
    """Invalid CLI usage / arguments."""

    exit_code = EXIT_USAGE

    def __init__(self, message: str = "Invalid arguments"):
        super().__init__(message, exit_code=self.exit_code)


class BlockedError(VillageError):
    """No work available / blocked state."""

    exit_code = EXIT_BLOCKED

    def __init__(self, message: str = "No work available"):
        super().__init__(message, exit_code=self.exit_code)


class LockValidationError(PermanentError):
    """Corrupted or invalid lock file."""

    exit_code = EXIT_ERROR

    def __init__(self, message: str = "Lock file corrupted"):
        super().__init__(message, exit_code=self.exit_code)


class InterruptedResume(VillageError):
    """Resume interrupted by user (Ctrl+C)."""

    exit_code = EXIT_NOT_READY

    def __init__(self, message: str = "Resume interrupted by user"):
        super().__init__(message, exit_code=self.exit_code)
