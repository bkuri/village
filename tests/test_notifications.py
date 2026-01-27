"""Test notification systems functionality."""

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import requests

from village.config import Config
from village.notifications import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS,
    DEFAULT_TIMEOUT_SECONDS,
    InvalidEventTypeError,
    InvalidWebhookURLError,
    NotificationBackend,
    NotificationError,
    NotificationEvent,
    NotificationResult,
    WebhookDeliveryError,
    _detect_backend_type,
    _is_event_enabled,
    _send_webhook_with_retry,
    create_event,
    log_notification_event,
    send_discord_notification,
    send_notification,
    send_slack_notification,
    send_webhook,
)


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create test configuration."""
    subprocess.run(["git", "init"], cwd=tmp_path, check=True)
    config = Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )
    config.ensure_exists()
    return config


@pytest.fixture
def sample_event() -> NotificationEvent:
    """Create sample notification event."""
    return NotificationEvent(
        event_type="task_failed",
        task_id="bd-a3f8",
        timestamp=datetime.now(timezone.utc),
        context={"error": "Task failed", "attempt": 1},
    )


@pytest.fixture
def sample_backend() -> NotificationBackend:
    """Create sample notification backend."""
    return NotificationBackend(
        webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
        events=["task_failed", "orphan_detected"],
    )


class TestNotificationBackend:
    """Test NotificationBackend dataclass."""

    def test_valid_backend(self):
        """Test creating valid backend."""
        backend = NotificationBackend(
            webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
            events=["task_failed", "orphan_detected"],
        )

        assert backend.webhook_url == "https://hooks.slack.com/services/T000/B000/XXX"
        assert backend.events == ["task_failed", "orphan_detected"]

    def test_backend_supports_event(self, sample_backend):
        """Test supports_event method."""
        assert sample_backend.supports_event("task_failed") is True
        assert sample_backend.supports_event("orphan_detected") is True
        assert sample_backend.supports_event("high_priority_task") is False

    def test_invalid_url_empty(self):
        """Test backend rejects empty URL."""
        with pytest.raises(InvalidWebhookURLError, match="URL must be a non-empty string"):
            NotificationBackend(webhook_url="", events=["task_failed"])

    def test_invalid_url_not_string(self):
        """Test backend rejects non-string URL."""
        with pytest.raises(InvalidWebhookURLError, match="URL must be a non-empty string"):
            NotificationBackend(webhook_url=None, events=["task_failed"])

    def test_invalid_url_no_protocol(self):
        """Test backend rejects URL without protocol."""
        with pytest.raises(InvalidWebhookURLError, match="URL must start with http:// or https://"):
            NotificationBackend(
                webhook_url="hooks.slack.com/services/T000/B000/XXX", events=["task_failed"]
            )

    def test_invalid_events_not_list(self):
        """Test backend rejects non-list events."""
        with pytest.raises(ValueError, match="events must be a list"):
            NotificationBackend(
                webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
                events="task_failed",
            )

    def test_invalid_event_type(self):
        """Test backend rejects unsupported event type."""
        with pytest.raises(InvalidEventTypeError, match="Invalid event type: unknown_event"):
            NotificationBackend(
                webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
                events=["unknown_event"],
            )


class TestNotificationEvent:
    """Test NotificationEvent dataclass."""

    def test_valid_event(self):
        """Test creating valid event."""
        event = NotificationEvent(
            event_type="task_failed",
            task_id="bd-a3f8",
            timestamp=datetime.now(timezone.utc),
            context={"error": "Failed"},
        )

        assert event.event_type == "task_failed"
        assert event.task_id == "bd-a3f8"
        assert event.context == {"error": "Failed"}

    def test_invalid_event_type(self):
        """Test event rejects invalid event type."""
        with pytest.raises(InvalidEventTypeError, match="Invalid event type: unknown"):
            NotificationEvent(
                event_type="unknown",
                task_id="bd-a3f8",
                timestamp=datetime.now(timezone.utc),
                context={},
            )

    def test_event_without_task_id(self):
        """Test event without task ID."""
        event = NotificationEvent(
            event_type="orphan_detected",
            task_id=None,
            timestamp=datetime.now(timezone.utc),
            context={},
        )

        assert event.event_type == "orphan_detected"
        assert event.task_id is None


class TestNotificationResult:
    """Test NotificationResult dataclass."""

    def test_success_result(self):
        """Test success result."""
        result = NotificationResult(
            success=True,
            backend="slack",
            status_code=200,
            message="Delivered successfully",
        )

        assert result.success is True
        assert result.backend == "slack"
        assert result.status_code == 200
        assert result.message == "Delivered successfully"

    def test_failure_result(self):
        """Test failure result."""
        result = NotificationResult(
            success=False,
            backend="slack",
            status_code=None,
            message="Timeout",
        )

        assert result.success is False
        assert result.status_code is None

    def test_to_dict(self):
        """Test to_dict method."""
        result = NotificationResult(
            success=True,
            backend="slack",
            status_code=200,
            message="Success",
        )

        expected = {
            "success": True,
            "backend": "slack",
            "status_code": 200,
            "message": "Success",
        }

        assert result.to_dict() == expected


class TestDetectBackendType:
    """Test backend type detection."""

    def test_detect_slack(self):
        """Test detecting Slack webhook."""
        url = "https://hooks.slack.com/services/T000/B000/XXX"
        assert _detect_backend_type(url) == "slack"

    def test_detect_discord(self):
        """Test detecting Discord webhook."""
        url = "https://discord.com/api/webhooks/123/abc"
        assert _detect_backend_type(url) == "discord"

    def test_detect_generic_webhook(self):
        """Test detecting generic webhook."""
        url = "https://example.com/webhook"
        assert _detect_backend_type(url) == "webhook"


class TestIsEventEnabled:
    """Test event enabled checking."""

    def test_event_enabled(self, sample_backend):
        """Test event is enabled."""
        assert _is_event_enabled(sample_backend, "task_failed") is True

    def test_event_disabled(self, sample_backend):
        """Test event is disabled."""
        assert _is_event_enabled(sample_backend, "high_priority_task") is False


class TestSendWebhookWithRetry:
    """Test webhook delivery with retry logic."""

    @patch("village.notifications.requests.post")
    def test_success_first_attempt(self, mock_post):
        """Test successful delivery on first attempt."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        success, status_code, message = _send_webhook_with_retry(
            url="https://example.com/webhook",
            payload={"test": "data"},
        )

        assert success is True
        assert status_code == 200
        assert "attempt 1" in message
        assert mock_post.call_count == 1

    @patch("village.notifications.requests.post")
    @patch("village.notifications.time.sleep")
    def test_success_after_retry(self, mock_sleep, mock_post):
        """Test successful delivery after retry."""
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_post.side_effect = [mock_response_fail, mock_response_success]

        success, status_code, message = _send_webhook_with_retry(
            url="https://example.com/webhook",
            payload={"test": "data"},
        )

        assert success is True
        assert status_code == 200
        assert "attempt 2" in message
        assert mock_post.call_count == 2

    @patch("village.notifications.requests.post")
    @patch("village.notifications.time.sleep")
    def test_max_retries_exceeded(self, mock_sleep, mock_post):
        """Test failure after max retries."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        success, status_code, message = _send_webhook_with_retry(
            url="https://example.com/webhook",
            payload={"test": "data"},
            max_retries=2,
        )

        assert success is False
        assert status_code == 500
        assert "Failed after 3 attempts" in message
        assert mock_post.call_count == 3

    @patch("village.notifications.requests.post")
    @patch("village.notifications.time.sleep")
    def test_timeout_retry(self, mock_sleep, mock_post):
        """Test retry on timeout."""
        mock_post.side_effect = [
            requests.exceptions.Timeout(),
            Mock(status_code=200),
        ]

        success, status_code, message = _send_webhook_with_retry(
            url="https://example.com/webhook",
            payload={"test": "data"},
            max_retries=2,
        )

        assert success is True
        assert status_code == 200

    @patch("village.notifications.requests.post")
    @patch("village.notifications.time.sleep")
    def test_connection_error_retry(self, mock_sleep, mock_post):
        """Test retry on connection error."""
        mock_post.side_effect = [
            requests.exceptions.ConnectionError("Connection failed"),
            Mock(status_code=200),
        ]

        success, status_code, message = _send_webhook_with_retry(
            url="https://example.com/webhook",
            payload={"test": "data"},
            max_retries=2,
        )

        assert success is True
        assert status_code == 200


class TestSendWebhook:
    """Test webhook delivery without retry."""

    @patch("village.notifications.requests.post")
    def test_success_webhook(self, mock_post):
        """Test successful webhook delivery."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_webhook(
            url="https://hooks.slack.com/services/T000/B000/XXX",
            payload={"text": "Test message"},
        )

        assert result.success is True
        assert result.backend == "slack"
        assert result.status_code == 200
        assert result.message == "Webhook delivered successfully"

    @patch("village.notifications.requests.post")
    def test_failed_webhook(self, mock_post):
        """Test failed webhook delivery."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        with pytest.raises(WebhookDeliveryError, match="HTTP 400"):
            send_webhook(
                url="https://hooks.slack.com/services/T000/B000/XXX",
                payload={"text": "Test message"},
            )

    @patch("village.notifications.requests.post")
    def test_timeout_webhook(self, mock_post):
        """Test webhook timeout."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        with pytest.raises(WebhookDeliveryError, match="Timeout"):
            send_webhook(
                url="https://hooks.slack.com/services/T000/B000/XXX",
                payload={"text": "Test message"},
            )

    def test_invalid_url(self):
        """Test webhook with invalid URL."""
        with pytest.raises(InvalidWebhookURLError):
            send_webhook(
                url="invalid-url",
                payload={"text": "Test message"},
            )


class TestSendNotification:
    """Test notification sending with retry."""

    @patch("village.notifications._send_webhook_with_retry")
    def test_success_notification(self, mock_webhook, sample_event, sample_backend, test_config):
        """Test successful notification."""
        mock_webhook.return_value = (True, 200, "Delivered successfully")

        result = send_notification(
            event=sample_event,
            backend=sample_backend,
            config_path=test_config.village_dir,
        )

        assert result.success is True
        assert result.status_code == 200
        assert result.message == "Delivered successfully"

    @patch("village.notifications._send_webhook_with_retry")
    def test_failed_notification(self, mock_webhook, sample_event, sample_backend, test_config):
        """Test failed notification."""
        mock_webhook.return_value = (False, 500, "Server error")

        result = send_notification(
            event=sample_event,
            backend=sample_backend,
            config_path=test_config.village_dir,
        )

        assert result.success is False
        assert result.status_code == 500

    def test_event_not_enabled(self, sample_event, test_config):
        """Test event not enabled for backend."""
        backend = NotificationBackend(
            webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
            events=["orphan_detected"],
        )

        with pytest.raises(NotificationError, match="not enabled for backend"):
            send_notification(
                event=sample_event,
                backend=backend,
                config_path=test_config.village_dir,
            )

    @patch("village.notifications._send_webhook_with_retry")
    def test_event_logged(self, mock_webhook, sample_event, sample_backend, test_config):
        """Test notification is logged to event log."""
        mock_webhook.return_value = (True, 200, "Delivered")

        send_notification(
            event=sample_event,
            backend=sample_backend,
            config_path=test_config.village_dir,
        )

        from village.event_log import read_events

        events = read_events(test_config.village_dir)
        assert len(events) == 1
        assert events[0].cmd == "notification"
        assert events[0].task_id == "bd-a3f8"
        assert events[0].result == "ok"


class TestLogNotificationEvent:
    """Test notification event logging."""

    def test_log_success_notification(self, sample_event, test_config):
        """Test logging successful notification."""
        result = NotificationResult(
            success=True,
            backend="slack",
            status_code=200,
            message="Delivered",
        )

        log_notification_event(sample_event, "slack", result, test_config.village_dir)

        from village.event_log import read_events

        events = read_events(test_config.village_dir)
        assert len(events) == 1
        assert events[0].cmd == "notification"
        assert events[0].task_id == "bd-a3f8"
        assert events[0].result == "ok"
        assert events[0].error is None

    def test_log_failed_notification(self, sample_event, test_config):
        """Test logging failed notification."""
        result = NotificationResult(
            success=False,
            backend="slack",
            status_code=500,
            message="Server error",
        )

        log_notification_event(sample_event, "slack", result, test_config.village_dir)

        from village.event_log import read_events

        events = read_events(test_config.village_dir)
        assert len(events) == 1
        assert events[0].cmd == "notification"
        assert events[0].result == "error"
        assert events[0].error == "Server error"


class TestSendSlackNotification:
    """Test Slack-specific notification."""

    @patch("village.notifications._send_webhook_with_retry")
    def test_success_slack(self, mock_webhook, sample_event, test_config):
        """Test successful Slack notification."""
        mock_webhook.return_value = (True, 200, "Delivered")

        result = send_slack_notification(
            event=sample_event,
            webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
            config_path=test_config.village_dir,
        )

        assert result.success is True
        assert result.backend == "slack"
        assert result.status_code == 200

    @patch("village.notifications._send_webhook_with_retry")
    def test_slack_payload_format(self, mock_webhook, sample_event, test_config):
        """Test Slack payload formatting."""
        mock_webhook.return_value = (True, 200, "Delivered")

        send_slack_notification(
            event=sample_event,
            webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
            config_path=test_config.village_dir,
        )

        call_args = mock_webhook.call_args
        payload = call_args[1]["payload"]

        assert "text" in payload
        assert "task_failed" in payload["text"]
        assert "bd-a3f8" in payload["text"]


class TestSendDiscordNotification:
    """Test Discord-specific notification."""

    @patch("village.notifications._send_webhook_with_retry")
    def test_success_discord(self, mock_webhook, sample_event, test_config):
        """Test successful Discord notification."""
        mock_webhook.return_value = (True, 200, "Delivered")

        result = send_discord_notification(
            event=sample_event,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            config_path=test_config.village_dir,
        )

        assert result.success is True
        assert result.backend == "discord"
        assert result.status_code == 200

    @patch("village.notifications._send_webhook_with_retry")
    def test_discord_payload_format(self, mock_webhook, sample_event, test_config):
        """Test Discord payload formatting."""
        mock_webhook.return_value = (True, 200, "Delivered")

        send_discord_notification(
            event=sample_event,
            webhook_url="https://discord.com/api/webhooks/123/abc",
            config_path=test_config.village_dir,
        )

        call_args = mock_webhook.call_args
        payload = call_args[1]["payload"]

        assert "content" in payload
        assert "task_failed" in payload["content"]
        assert "bd-a3f8" in payload["content"]


class TestCreateEvent:
    """Test event creation helper."""

    def test_create_event_with_task(self):
        """Test creating event with task ID."""
        event = create_event(
            event_type="task_failed",
            task_id="bd-a3f8",
            context={"error": "Failed"},
        )

        assert event.event_type == "task_failed"
        assert event.task_id == "bd-a3f8"
        assert event.context == {"error": "Failed"}
        assert isinstance(event.timestamp, datetime)

    def test_create_event_without_task(self):
        """Test creating event without task ID."""
        event = create_event(
            event_type="orphan_detected",
            context={"count": 5},
        )

        assert event.event_type == "orphan_detected"
        assert event.task_id is None
        assert event.context == {"count": 5}

    def test_create_event_no_context(self):
        """Test creating event without context."""
        event = create_event(event_type="task_failed", task_id="bd-a3f8")

        assert event.context == {}

    def test_create_event_invalid_type(self):
        """Test creating event with invalid type."""
        with pytest.raises(InvalidEventTypeError):
            create_event(event_type="invalid")


class TestIntegration:
    """Integration tests."""

    @patch("village.notifications._send_webhook_with_retry")
    def test_full_notification_flow(self, mock_webhook, test_config):
        """Test full notification flow."""
        mock_webhook.return_value = (True, 200, "Delivered")

        event = create_event(
            event_type="task_failed",
            task_id="bd-a3f8",
            context={"error": "Test error"},
        )

        backend = NotificationBackend(
            webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
            events=["task_failed"],
        )

        result = send_notification(
            event=event,
            backend=backend,
            config_path=test_config.village_dir,
        )

        assert result.success is True

        from village.event_log import read_events

        events = read_events(test_config.village_dir)
        assert len(events) == 1
        assert events[0].cmd == "notification"
        assert events[0].task_id == "bd-a3f8"
        assert events[0].result == "ok"

    def test_multiple_backends(self, test_config):
        """Test sending to multiple backends."""
        backends = [
            NotificationBackend(
                webhook_url="https://hooks.slack.com/services/T000/B000/XXX",
                events=["task_failed"],
            ),
            NotificationBackend(
                webhook_url="https://discord.com/api/webhooks/123/abc",
                events=["task_failed"],
            ),
        ]

        event = create_event(
            event_type="task_failed",
            task_id="bd-a3f8",
        )

        with patch("village.notifications._send_webhook_with_retry") as mock_webhook:
            mock_webhook.return_value = (True, 200, "Delivered")

            for backend in backends:
                result = send_notification(
                    event=event,
                    backend=backend,
                    config_path=test_config.village_dir,
                )
                assert result.success is True

        from village.event_log import read_events

        events = read_events(test_config.village_dir)
        assert len(events) == 2


class TestDefaultConstants:
    """Test default constants."""

    def test_default_max_retries(self):
        """Test default max retries."""
        assert DEFAULT_MAX_RETRIES == 3

    def test_default_retry_delay(self):
        """Test default retry delay."""
        assert DEFAULT_RETRY_DELAY_SECONDS == 1

    def test_default_timeout(self):
        """Test default timeout."""
        assert DEFAULT_TIMEOUT_SECONDS == 30
