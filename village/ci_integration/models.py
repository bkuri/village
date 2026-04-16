"""CI/CD integration data types."""

from dataclasses import dataclass
from typing import Literal


class CIIntegrationError(Exception):
    """Base exception for CI integration errors."""


class BuildTriggerError(CIIntegrationError):
    """Exception raised when build triggering fails."""


class BuildTimeoutError(CIIntegrationError):
    """Exception raised when build monitoring times out."""


class PlatformNotConfiguredError(CIIntegrationError):
    """Exception raised when CI platform is not configured."""


@dataclass
class BuildResult:
    """Result of a build trigger operation."""

    success: bool
    build_id: str
    platform: str
    message: str


@dataclass
class BuildStatus:
    """Status of a running build."""

    status: Literal["pending", "running", "success", "failure"]
    url: str | None
    logs: str | None


@dataclass
class CIPlatformConfig:
    """Configuration for a CI/CD platform."""

    token: str | None
    url: str | None
    polling_interval_seconds: int = 30
    timeout_seconds: int = 3600
