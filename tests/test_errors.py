"""Test Village exception hierarchy and error handling."""

from village.errors import (
    EXIT_BLOCKED,
    EXIT_ERROR,
    EXIT_NOT_READY,
    EXIT_PARTIAL,
    EXIT_SUCCESS,
    EXIT_USAGE,
    BlockedError,
    ConfigError,
    InterruptedResume,
    LockValidationError,
    PermanentError,
    TransientError,
    UserInputError,
    VillageError,
)


class TestExitCodeConstants:
    """Test exit code constant values."""

    def test_exit_success(self):
        """EXIT_SUCCESS should be 0."""
        assert EXIT_SUCCESS == 0

    def test_exit_error(self):
        """EXIT_ERROR should be 1."""
        assert EXIT_ERROR == 1

    def test_exit_not_ready(self):
        """EXIT_NOT_READY should be 2."""
        assert EXIT_NOT_READY == 2

    def test_exit_blocked(self):
        """EXIT_BLOCKED should be 3."""
        assert EXIT_BLOCKED == 3

    def test_exit_partial(self):
        """EXIT_PARTIAL should be 4."""
        assert EXIT_PARTIAL == 4

    def test_exit_usage(self):
        """EXIT_USAGE should be 5."""
        assert EXIT_USAGE == 5


class TestVillageErrorBase:
    """Test VillageError base exception."""

    def test_inherits_exception(self):
        """VillageError should inherit from Exception."""
        assert issubclass(VillageError, Exception)

    def test_has_exit_code(self):
        """VillageError should have exit_code attribute."""
        exc = VillageError("test message")
        assert exc.exit_code == EXIT_ERROR

    def test_custom_exit_code(self):
        """VillageError should accept custom exit code."""
        exc = VillageError("test message", exit_code=EXIT_BLOCKED)
        assert exc.exit_code == EXIT_BLOCKED

    def test_has_message(self):
        """VillageError should have message attribute."""
        exc = VillageError("test message")
        assert exc.message == "test message"
        assert str(exc) == "test message"


class TestTransientError:
    """Test TransientError with retry metadata."""

    def test_inherits_village_error(self):
        """TransientError should inherit from VillageError."""
        assert issubclass(TransientError, VillageError)

    def test_default_exit_code_not_ready(self):
        """TransientError should use EXIT_NOT_READY exit code."""
        exc = TransientError("test")
        assert exc.exit_code == EXIT_NOT_READY

    def test_default_retry_metadata(self):
        """TransientError should have default retry metadata."""
        exc = TransientError("test")
        assert exc.attempt == 1
        assert exc.max_attempts == 3
        assert exc.retry_in is None

    def test_custom_retry_metadata(self):
        """TransientError should accept custom retry metadata."""
        exc = TransientError(
            "test",
            attempt=2,
            max_attempts=5,
            retry_in=60,
        )
        assert exc.attempt == 2
        assert exc.max_attempts == 5
        assert exc.retry_in == 60

    def test_message_propagation(self):
        """TransientError should propagate message to base class."""
        exc = TransientError("transient failure")
        assert exc.message == "transient failure"
        assert str(exc) == "transient failure"


class TestPermanentError:
    """Test PermanentError for non-retryable errors."""

    def test_inherits_village_error(self):
        """PermanentError should inherit from VillageError."""
        assert issubclass(PermanentError, VillageError)

    def test_default_exit_code_error(self):
        """PermanentError should use EXIT_ERROR exit code."""
        exc = PermanentError("permanent failure")
        assert exc.exit_code == EXIT_ERROR


class TestConfigError:
    """Test ConfigError for configuration issues."""

    def test_inherits_permanent_error(self):
        """ConfigError should inherit from PermanentError."""
        assert issubclass(ConfigError, PermanentError)

    def test_has_message(self):
        """ConfigError should support message."""
        exc = ConfigError("invalid config")
        assert exc.message == "invalid config"
        assert str(exc) == "invalid config"


class TestUserInputError:
    """Test UserInputError for invalid CLI usage."""

    def test_inherits_village_error(self):
        """UserInputError should inherit from VillageError."""
        assert issubclass(UserInputError, VillageError)

    def test_default_exit_code_usage(self):
        """UserInputError should use EXIT_USAGE exit code."""
        exc = UserInputError("invalid args")
        assert exc.exit_code == EXIT_USAGE


class TestBlockedError:
    """Test BlockedError for no work available."""

    def test_inherits_village_error(self):
        """BlockedError should inherit from VillageError."""
        assert issubclass(BlockedError, VillageError)

    def test_default_exit_code_blocked(self):
        """BlockedError should use EXIT_BLOCKED exit code."""
        exc = BlockedError("no work available")
        assert exc.exit_code == EXIT_BLOCKED


class TestLockValidationError:
    """Test LockValidationError for corrupted locks."""

    def test_inherits_permanent_error(self):
        """LockValidationError should inherit from PermanentError."""
        assert issubclass(LockValidationError, PermanentError)

    def test_default_exit_code_error(self):
        """LockValidationError should use EXIT_ERROR exit code."""
        exc = LockValidationError("corrupted lock file")
        assert exc.exit_code == EXIT_ERROR


class TestInterruptedResume:
    """Test InterruptedResume for Ctrl+C handling."""

    def test_inherits_village_error(self):
        """InterruptedResume should inherit from VillageError."""
        assert issubclass(InterruptedResume, VillageError)

    def test_default_exit_code_not_ready(self):
        """InterruptedResume should use EXIT_NOT_READY exit code."""
        exc = InterruptedResume()
        assert exc.exit_code == EXIT_NOT_READY

    def test_default_message(self):
        """InterruptedResume should have default message."""
        exc = InterruptedResume()
        assert exc.message == "Resume interrupted by user"

    def test_custom_message(self):
        """InterruptedResume should accept custom message."""
        exc = InterruptedResume(message="Custom interrupt message")
        assert exc.message == "Custom interrupt message"
        assert str(exc) == "Custom interrupt message"
