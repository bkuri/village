"""Notification systems for task events."""

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from village.event_log import append_event

logger = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1
DEFAULT_TIMEOUT_SECONDS = 30

SUPPORTED_EVENT_TYPES = ["task_failed", "orphan_detected", "high_priority_task"]


class NotificationError(Exception):
    """Base exception for notification errors."""


class WebhookDeliveryError(NotificationError):
    """Raised when webhook delivery fails."""

    def __init__(self, url: str, status_code: int | None, message: str):
        self.url = url
        self.status_code = status_code
        super().__init__(f"Webhook delivery failed to {url}: {message} (status={status_code})")


class InvalidWebhookURLError(NotificationError):
    """Raised when webhook URL is invalid."""

    def __init__(self, url: str, message: str):
        self.url = url
        super().__init__(f"Invalid webhook URL {url}: {message}")


class InvalidEventTypeError(NotificationError):
    """Raised when event type is not supported."""

    def __init__(self, event_type: str):
        self.event_type = event_type
        super().__init__(
            f"Invalid event type: {event_type}. Must be one of: {', '.join(SUPPORTED_EVENT_TYPES)}"
        )


@dataclass
class NotificationBackend:
    """Configuration for a notification backend."""

    webhook_url: str
    events: list[str]

    def __post_init__(self) -> None:
        """Validate webhook URL and event types."""
        self._validate_webhook_url()
        self._validate_event_types()

    def _validate_webhook_url(self) -> None:
        """Validate webhook URL format."""
        if not self.webhook_url or not isinstance(self.webhook_url, str):
            raise InvalidWebhookURLError(self.webhook_url, "URL must be a non-empty string")

        if not self.webhook_url.startswith(("http://", "https://")):
            raise InvalidWebhookURLError(
                self.webhook_url, "URL must start with http:// or https://"
            )

    def _validate_event_types(self) -> None:
        """Validate event types are supported."""
        if not isinstance(self.events, list):
            raise ValueError("events must be a list")

        for event_type in self.events:
            if event_type not in SUPPORTED_EVENT_TYPES:
                raise InvalidEventTypeError(event_type)

    def supports_event(self, event_type: str) -> bool:
        """Check if backend supports the given event type."""
        return event_type in self.events


@dataclass
class NotificationEvent:
    """Event data for notification."""

    event_type: str
    task_id: str | None
    timestamp: datetime
    context: dict[str, Any]

    def __post_init__(self) -> None:
        """Validate event type."""
        if self.event_type not in SUPPORTED_EVENT_TYPES:
            raise InvalidEventTypeError(self.event_type)


@dataclass
class NotificationResult:
    """Result of a notification attempt."""

    success: bool
    backend: str
    status_code: int | None
    message: str

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "backend": self.backend,
            "status_code": self.status_code,
            "message": self.message,
        }


def _is_event_enabled(backend: NotificationBackend, event_type: str) -> bool:
    """
    Check if event type is enabled for backend.

    Args:
        backend: Notification backend configuration
        event_type: Event type to check

    Returns:
        True if event is enabled, False otherwise
    """
    return backend.supports_event(event_type)


def _send_webhook_with_retry(
    url: str,
    payload: dict[str, Any],
    max_retries: int = DEFAULT_MAX_RETRIES,
    initial_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
) -> tuple[bool, int | None, str]:
    """
    Send webhook with exponential backoff retry logic.

    Args:
        url: Webhook URL
        payload: JSON payload to send
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay between retries in seconds
        timeout: HTTP request timeout in seconds

    Returns:
        Tuple of (success, status_code, message)
    """
    headers = {"Content-Type": "application/json"}

    for attempt in range(max_retries + 1):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)

            if response.status_code >= 200 and response.status_code < 300:
                return (
                    True,
                    response.status_code,
                    f"Webhook delivered successfully on attempt {attempt + 1}",
                )
            else:
                if attempt == max_retries:
                    return (
                        False,
                        response.status_code,
                        f"Failed after {max_retries + 1} attempts: {response.text}",
                    )
                else:
                    logger.warning(
                        f"Webhook attempt {attempt + 1} failed with status "
                        f"{response.status_code}, retrying..."
                    )

        except requests.exceptions.Timeout:
            if attempt == max_retries:
                return False, None, f"Timeout after {max_retries + 1} attempts"
            else:
                logger.warning(f"Webhook attempt {attempt + 1} timed out, retrying...")

        except requests.exceptions.RequestException as e:
            if attempt == max_retries:
                return False, None, f"Request failed after {max_retries + 1} attempts: {e}"
            else:
                logger.warning(f"Webhook attempt {attempt + 1} failed with error: {e}, retrying...")

        if attempt < max_retries:
            delay = initial_delay * (2**attempt)
            logger.debug(f"Waiting {delay}s before retry...")
            time.sleep(delay)

    return False, None, "Max retries exceeded"


def _detect_backend_type(webhook_url: str) -> str:
    """
    Detect backend type from webhook URL.

    Args:
        webhook_url: Webhook URL to analyze

    Returns:
        Backend type name (slack, discord, or webhook)
    """
    if "hooks.slack.com" in webhook_url:
        return "slack"
    elif "discord.com/api/webhooks" in webhook_url:
        return "discord"
    else:
        return "webhook"


def send_webhook(url: str, payload: dict[str, Any]) -> NotificationResult:
    """
    Send webhook notification without retry logic.

    Args:
        url: Webhook URL
        payload: JSON payload to send

    Returns:
        NotificationResult with delivery status

    Raises:
        InvalidWebhookURLError: If webhook URL is invalid
        WebhookDeliveryError: If webhook delivery fails
    """
    backend_type = _detect_backend_type(url)

    if not url or not isinstance(url, str):
        raise InvalidWebhookURLError(url, "URL must be a non-empty string")

    if not url.startswith(("http://", "https://")):
        raise InvalidWebhookURLError(url, "URL must start with http:// or https://")

    try:
        response = requests.post(url, json=payload, timeout=DEFAULT_TIMEOUT_SECONDS)

        if response.status_code >= 200 and response.status_code < 300:
            logger.info(f"Webhook delivered to {backend_type} at {url}")
            return NotificationResult(
                success=True,
                backend=backend_type,
                status_code=response.status_code,
                message="Webhook delivered successfully",
            )
        else:
            error_msg = f"HTTP {response.status_code}: {response.text}"
            logger.error(f"Webhook delivery failed to {url}: {error_msg}")
            raise WebhookDeliveryError(url, response.status_code, error_msg)

    except requests.exceptions.Timeout as e:
        error_msg = f"Timeout: {e}"
        logger.error(f"Webhook delivery failed to {url}: {error_msg}")
        raise WebhookDeliveryError(url, None, error_msg)

    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {e}"
        logger.error(f"Webhook delivery failed to {url}: {error_msg}")
        raise WebhookDeliveryError(url, None, error_msg)


def send_notification(
    event: NotificationEvent,
    backend: NotificationBackend,
    config_path: Path,
    max_retries: int = DEFAULT_MAX_RETRIES,
    retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
) -> NotificationResult:
    """
    Send notification to backend with retry logic.

    Args:
        event: Event data to send
        backend: Notification backend configuration
        config_path: Path to village directory for event logging
        max_retries: Maximum number of retry attempts
        retry_delay: Initial delay between retries in seconds

    Returns:
        NotificationResult with delivery status

    Raises:
        InvalidEventTypeError: If event type is not supported
        NotificationError: If event is not enabled for backend
    """
    backend_type = _detect_backend_type(backend.webhook_url)

    if not _is_event_enabled(backend, event.event_type):
        logger.info(f"Event {event.event_type} not enabled for backend {backend_type}")
        raise NotificationError(f"Event {event.event_type} not enabled for backend {backend_type}")

    payload: dict[str, Any] = {
        "event_type": event.event_type,
        "task_id": event.task_id,
        "timestamp": event.timestamp.isoformat(),
        "context": event.context,
    }

    logger.info(
        f"Sending {event.event_type} notification to {backend_type}: {event.task_id or 'no task'}"
    )

    success, status_code, message = _send_webhook_with_retry(
        url=backend.webhook_url,
        payload=payload,
        max_retries=max_retries,
        initial_delay=retry_delay,
    )

    result = NotificationResult(
        success=success,
        backend=backend_type,
        status_code=status_code,
        message=message,
    )

    log_notification_event(event, backend_type, result, config_path)

    return result


def log_notification_event(
    event: NotificationEvent,
    backend: str,
    result: NotificationResult,
    config_path: Path,
) -> None:
    """
    Log notification attempt to event log.

    Args:
        event: Event that was notified
        backend: Backend type
        result: Notification result
        config_path: Path to village directory
    """
    from village.event_log import Event

    log_event = Event(
        ts=datetime.now(timezone.utc).isoformat(),
        cmd="notification",
        task_id=event.task_id,
        result="ok" if result.success else "error",
        error=None if result.success else result.message,
    )

    append_event(log_event, config_path)


def send_slack_notification(
    event: NotificationEvent,
    webhook_url: str,
    config_path: Path,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> NotificationResult:
    """
    Send notification to Slack webhook.

    Args:
        event: Event data to send
        webhook_url: Slack webhook URL
        config_path: Path to village directory for event logging
        max_retries: Maximum number of retry attempts

    Returns:
        NotificationResult with delivery status
    """
    text = f"Village Event: {event.event_type}"
    if event.task_id:
        text += f" (Task: {event.task_id})"

    slack_payload = {"text": text}

    success, status_code, message = _send_webhook_with_retry(
        url=webhook_url,
        payload=slack_payload,
        max_retries=max_retries,
    )

    result = NotificationResult(
        success=success,
        backend="slack",
        status_code=status_code,
        message=message,
    )

    log_notification_event(event, "slack", result, config_path)

    return result


def send_discord_notification(
    event: NotificationEvent,
    webhook_url: str,
    config_path: Path,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> NotificationResult:
    """
    Send notification to Discord webhook.

    Args:
        event: Event data to send
        webhook_url: Discord webhook URL
        config_path: Path to village directory for event logging
        max_retries: Maximum number of retry attempts

    Returns:
        NotificationResult with delivery status
    """
    content = f"**Village Event**: {event.event_type}"
    if event.task_id:
        content += f"\nTask: {event.task_id}"

    discord_payload = {"content": content}

    success, status_code, message = _send_webhook_with_retry(
        url=webhook_url,
        payload=discord_payload,
        max_retries=max_retries,
    )

    result = NotificationResult(
        success=success,
        backend="discord",
        status_code=status_code,
        message=message,
    )

    log_notification_event(event, "discord", result, config_path)

    return result


def create_event(
    event_type: str,
    task_id: str | None = None,
    context: dict[str, Any] | None = None,
) -> NotificationEvent:
    """
    Create a notification event with current timestamp.

    Args:
        event_type: Type of event (task_failed, orphan_detected, high_priority_task)
        task_id: Optional task ID
        context: Optional additional context data

    Returns:
        NotificationEvent object

    Raises:
        InvalidEventTypeError: If event type is not supported
    """
    if event_type not in SUPPORTED_EVENT_TYPES:
        raise InvalidEventTypeError(event_type)

    return NotificationEvent(
        event_type=event_type,
        task_id=task_id,
        timestamp=datetime.now(timezone.utc),
        context=context or {},
    )
