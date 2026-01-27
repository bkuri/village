"""Test CI/CD integration operations."""

import json
import os
import subprocess
from pathlib import Path
from typing import Literal, cast
from unittest.mock import MagicMock, patch

import pytest

from village.ci_integration import (
    BuildResult,
    BuildStatus,
    BuildTimeoutError,
    CIPlatformConfig,
    PlatformNotConfiguredError,
    _append_ci_event,
    _monitor_github_actions,
    _monitor_gitlab_ci,
    _monitor_jenkins,
    _trigger_github_actions,
    _trigger_gitlab_ci,
    _trigger_jenkins,
    get_ci_config,
    monitor_build,
    trigger_build,
    update_task_on_failure,
)


@pytest.fixture
def mock_config(tmp_path: Path):
    """Mock config with temp directory."""
    tmp_path.mkdir(parents=True, exist_ok=True)
    return tmp_path


class TestCIPlatformConfig:
    """Tests for CIPlatformConfig dataclass."""

    def test_config_creation(self):
        """Test creating CI platform config."""
        config = CIPlatformConfig(
            token="test-token",
            url="https://ci.example.com",
            polling_interval_seconds=60,
            timeout_seconds=1800,
        )
        assert config.token == "test-token"
        assert config.url == "https://ci.example.com"
        assert config.polling_interval_seconds == 60
        assert config.timeout_seconds == 1800

    def test_config_defaults(self):
        """Test default values for CI config."""
        config = CIPlatformConfig(token="test-token", url=None)
        assert config.token == "test-token"
        assert config.url is None
        assert config.polling_interval_seconds == 30
        assert config.timeout_seconds == 3600


class TestBuildResult:
    """Tests for BuildResult dataclass."""

    def test_build_result_success(self):
        """Test successful build result."""
        result = BuildResult(
            success=True,
            build_id="12345",
            platform="github_actions",
            message="Build triggered successfully",
        )
        assert result.success is True
        assert result.build_id == "12345"
        assert result.platform == "github_actions"
        assert result.message == "Build triggered successfully"

    def test_build_result_failure(self):
        """Test failed build result."""
        result = BuildResult(
            success=False,
            build_id="",
            platform="github_actions",
            message="Build trigger failed",
        )
        assert result.success is False
        assert result.build_id == ""
        assert result.message == "Build trigger failed"


class TestBuildStatus:
    """Tests for BuildStatus dataclass."""

    def test_build_status_success(self):
        """Test successful build status."""
        status = BuildStatus(status="success", url="https://ci.example.com/build/123", logs=None)
        assert status.status == "success"
        assert status.url == "https://ci.example.com/build/123"
        assert status.logs is None

    def test_build_status_with_logs(self):
        """Test build status with logs."""
        logs = "Build step 1 passed\nBuild step 2 failed"
        status = BuildStatus(status="failure", url=None, logs=logs)
        assert status.status == "failure"
        assert status.url is None
        assert status.logs == logs


class TestGetCIConfig:
    """Tests for get_ci_config function."""

    def test_github_config_from_env(self, mock_config: Path):
        """Test loading GitHub config from environment."""
        os.environ["GITHUB_TOKEN"] = "ghp_test_token"
        os.environ["GITHUB_API_URL"] = "https://api.github.com"

        configs = get_ci_config(mock_config)

        assert "github_actions" in configs
        assert configs["github_actions"].token == "ghp_test_token"
        assert configs["github_actions"].url == "https://api.github.com"

        os.environ.pop("GITHUB_TOKEN", None)
        os.environ.pop("GITHUB_API_URL", None)

    def test_gitlab_config_from_env(self, mock_config: Path):
        """Test loading GitLab config from environment."""
        os.environ["GITLAB_TOKEN"] = "glpat_test_token"
        os.environ["GITLAB_URL"] = "https://gitlab.example.com"

        configs = get_ci_config(mock_config)

        assert "gitlab_ci" in configs
        assert configs["gitlab_ci"].token == "glpat_test_token"
        assert configs["gitlab_ci"].url == "https://gitlab.example.com"

        os.environ.pop("GITLAB_TOKEN", None)
        os.environ.pop("GITLAB_URL", None)

    def test_jenkins_config_from_env(self, mock_config: Path):
        """Test loading Jenkins config from environment."""
        os.environ["JENKINS_TOKEN"] = "jenkins_test_token"
        os.environ["JENKINS_URL"] = "https://jenkins.example.com"

        configs = get_ci_config(mock_config)

        assert "jenkins" in configs
        assert configs["jenkins"].token == "jenkins_test_token"
        assert configs["jenkins"].url == "https://jenkins.example.com"

        os.environ.pop("JENKINS_TOKEN", None)
        os.environ.pop("JENKINS_URL", None)

    def test_village_specific_env_vars(self, mock_config: Path):
        """Test VILLAGE_ prefixed environment variables."""
        os.environ["VILLAGE_GITHUB_TOKEN"] = "ghp_village_token"
        os.environ["VILLAGE_GITLAB_TOKEN"] = "glpat_village_token"

        configs = get_ci_config(mock_config)

        assert configs["github_actions"].token == "ghp_village_token"
        assert configs["gitlab_ci"].token == "glpat_village_token"

        os.environ.pop("VILLAGE_GITHUB_TOKEN", None)
        os.environ.pop("VILLAGE_GITLAB_TOKEN", None)

    def test_custom_polling_interval(self, mock_config: Path):
        """Test custom polling interval configuration."""
        os.environ["VILLAGE_GITHUB_POLLING_INTERVAL"] = "60"

        configs = get_ci_config(mock_config)

        assert configs["github_actions"].polling_interval_seconds == 60

        os.environ.pop("VILLAGE_GITHUB_POLLING_INTERVAL", None)

    def test_custom_timeout(self, mock_config: Path):
        """Test custom timeout configuration."""
        os.environ["VILLAGE_GITHUB_TIMEOUT"] = "7200"

        configs = get_ci_config(mock_config)

        assert configs["github_actions"].timeout_seconds == 7200

        os.environ.pop("VILLAGE_GITHUB_TIMEOUT", None)

    def test_defaults_when_no_env_vars(self, mock_config: Path):
        """Test default values when no environment variables set."""
        configs = get_ci_config(mock_config)

        assert configs["gitlab_ci"].url == "https://gitlab.com"
        assert configs["github_actions"].polling_interval_seconds == 30
        assert configs["jenkins"].timeout_seconds == 3600


class TestTriggerBuild:
    """Tests for trigger_build function."""

    def test_trigger_github_actions_success(self, mock_config: Path):
        """Test triggering GitHub Actions build successfully."""
        os.environ["GITHUB_TOKEN"] = "ghp_test_token"

        with patch("village.ci_integration._trigger_github_actions") as mock_trigger:
            mock_trigger.return_value = BuildResult(
                success=True,
                build_id="12345",
                platform="github_actions",
                message="Build triggered",
            )

            result = trigger_build("bd-a3f8", "github_actions", mock_config)

            assert result.success is True
            assert result.build_id == "12345"
            mock_trigger.assert_called_once()

            os.environ.pop("GITHUB_TOKEN", None)

    def test_trigger_gitlab_ci_success(self, mock_config: Path):
        """Test triggering GitLab CI build successfully."""
        os.environ["GITLAB_TOKEN"] = "glpat_test_token"

        with patch("village.ci_integration._trigger_gitlab_ci") as mock_trigger:
            mock_trigger.return_value = BuildResult(
                success=True,
                build_id="67890",
                platform="gitlab_ci",
                message="Pipeline triggered",
            )

            result = trigger_build("bd-b7d2", "gitlab_ci", mock_config)

            assert result.success is True
            assert result.build_id == "67890"

            os.environ.pop("GITLAB_TOKEN", None)

    def test_trigger_jenkins_success(self, mock_config: Path):
        """Test triggering Jenkins build successfully."""
        os.environ["JENKINS_TOKEN"] = "jenkins_token"
        os.environ["JENKINS_URL"] = "https://jenkins.example.com"

        with patch("village.ci_integration._trigger_jenkins") as mock_trigger:
            mock_trigger.return_value = BuildResult(
                success=True,
                build_id="42",
                platform="jenkins",
                message="Build triggered",
            )

            result = trigger_build("bd-c4e1", "jenkins", mock_config)

            assert result.success is True
            assert result.build_id == "42"

            os.environ.pop("JENKINS_TOKEN", None)
            os.environ.pop("JENKINS_URL", None)

    def test_trigger_without_token_raises_error(self, mock_config: Path):
        """Test triggering build without token raises error."""
        with pytest.raises(PlatformNotConfiguredError) as exc:
            trigger_build("bd-a3f8", "github_actions", mock_config)

        assert "not configured: missing token" in str(exc.value)

    def test_trigger_logs_event(self, mock_config: Path):
        """Test that build trigger is logged to events.log."""
        os.environ["GITHUB_TOKEN"] = "ghp_test_token"

        with patch("village.ci_integration._trigger_github_actions") as mock_trigger:
            mock_trigger.return_value = BuildResult(
                success=True,
                build_id="12345",
                platform="github_actions",
                message="Build triggered",
            )

            trigger_build("bd-a3f8", "github_actions", mock_config)

            # Check event log
            event_log = mock_config / "events.log"
            assert event_log.exists()

            with open(event_log, "r") as f:
                events = [json.loads(line) for line in f]

            assert any(
                e["cmd"] == "ci_trigger"
                and e["task_id"] == "bd-a3f8"
                and e["platform"] == "github_actions"
                and e["build_id"] == "12345"
                for e in events
            )

            os.environ.pop("GITHUB_TOKEN", None)

    def test_trigger_unknown_platform_raises_error(self, mock_config: Path):
        """Test triggering build with unknown platform raises error."""
        with pytest.raises(PlatformNotConfiguredError) as exc:
            trigger_build(
                "bd-a3f8",
                cast(Literal["github_actions", "gitlab_ci", "jenkins"], "unknown_platform"),
                mock_config,
            )

        assert "not configured: missing token" in str(exc.value)


class TestMonitorBuild:
    """Tests for monitor_build function."""

    def test_monitor_build_success(self, mock_config: Path):
        """Test monitoring build until success."""
        os.environ["GITHUB_TOKEN"] = "ghp_test_token"

        with patch("village.ci_integration._monitor_github_actions") as mock_monitor:
            mock_monitor.return_value = BuildStatus(
                status="success",
                url="https://github.com/repo/actions/runs/12345",
                logs=None,
            )

            status = monitor_build("12345", "github_actions", mock_config)

            assert status.status == "success"
            mock_monitor.assert_called_once()

            os.environ.pop("GITHUB_TOKEN", None)

    def test_monitor_build_failure(self, mock_config: Path):
        """Test monitoring build until failure."""
        os.environ["GITLAB_TOKEN"] = "glpat_test_token"

        with patch("village.ci_integration._monitor_gitlab_ci") as mock_monitor:
            mock_monitor.return_value = BuildStatus(
                status="failure",
                url="https://gitlab.com/pipelines/67890",
                logs="Build failed on step 3",
            )

            status = monitor_build("67890", "gitlab_ci", mock_config)

            assert status.status == "failure"
            assert status.logs == "Build failed on step 3"

            os.environ.pop("GITLAB_TOKEN", None)

    def test_monitor_build_timeout(self, mock_config: Path):
        """Test monitoring build times out."""
        os.environ["GITHUB_TOKEN"] = "ghp_test_token"

        with patch("village.ci_integration._monitor_github_actions") as mock_monitor:
            mock_monitor.return_value = BuildStatus(status="running", url=None, logs=None)

            with pytest.raises(BuildTimeoutError) as exc:
                # Mock small timeout for testing
                with patch("village.ci_integration.get_ci_config") as mock_ci_config:
                    mock_ci_config.return_value = {
                        "github_actions": CIPlatformConfig(
                            token="test",
                            url=None,
                            polling_interval_seconds=int(0.1 * 10),
                            timeout_seconds=int(0.2 * 10),
                        )
                    }

                    monitor_build("12345", "github_actions", Path("/tmp"))

            assert "timed out" in str(exc.value).lower()

            os.environ.pop("GITHUB_TOKEN", None)

    def test_monitor_logs_completion_event(self, mock_config: Path):
        """Test that build completion is logged to events.log."""
        os.environ["GITHUB_TOKEN"] = "ghp_test_token"

        with patch("village.ci_integration._monitor_github_actions") as mock_monitor:
            mock_monitor.return_value = BuildStatus(
                status="success",
                url="https://github.com/repo/actions/runs/12345",
                logs=None,
            )

            monitor_build("12345", "github_actions", mock_config)

            # Check event log
            event_log = mock_config / "events.log"
            assert event_log.exists()

            with open(event_log, "r") as f:
                events = [json.loads(line) for line in f]

            assert any(
                e["cmd"] == "ci_monitor"
                and e["build_id"] == "12345"
                and e["platform"] == "github_actions"
                and e["status"] == "success"
                for e in events
            )

            os.environ.pop("GITHUB_TOKEN", None)


class TestUpdateTaskOnFailure:
    """Tests for update_task_on_failure function."""

    def test_update_task_logs_failure(self, mock_config: Path):
        """Test updating task on build failure."""
        update_task_on_failure("bd-a3f8", "12345", "Tests failed", mock_config)

        # Check event log
        event_log = mock_config / "events.log"
        assert event_log.exists()

        with open(event_log, "r") as f:
            events = [json.loads(line) for line in f]

        assert any(
            e["cmd"] == "ci_failure"
            and e["task_id"] == "bd-a3f8"
            and e["build_id"] == "12345"
            and e["reason"] == "Tests failed"
            for e in events
        )

    def test_update_task_with_empty_reason(self, mock_config: Path):
        """Test updating task with empty reason."""
        update_task_on_failure("bd-a3f8", "12345", "", mock_config)

        event_log = mock_config / "events.log"
        with open(event_log, "r") as f:
            events = [json.loads(line) for line in f]

        assert any(
            e["cmd"] == "ci_failure" and e["task_id"] == "bd-a3f8" and e["reason"] == ""
            for e in events
        )


class TestTriggerGitHubActions:
    """Tests for _trigger_github_actions function."""

    def test_github_success(self):
        """Test successful GitHub Actions trigger."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="12345\n",
                stderr="",
            )

            result = _trigger_github_actions("bd-a3f8", config)

            assert result.success is True
            assert result.build_id == "12345"
            assert "GitHub Actions workflow triggered" in result.message

    def test_github_command_failure(self):
        """Test GitHub Actions trigger when command fails."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Workflow not found",
            )

            result = _trigger_github_actions("bd-a3f8", config)

            assert result.success is False
            assert "gh workflow failed" in result.message

    def test_github_timeout(self):
        """Test GitHub Actions trigger timeout."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("gh", 30)

            result = _trigger_github_actions("bd-a3f8", config)

            assert result.success is False
            assert "timed out" in result.message.lower()

    def test_github_cli_not_found(self):
        """Test GitHub Actions trigger when gh CLI not found."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError("gh")

            result = _trigger_github_actions("bd-a3f8", config)

            assert result.success is False
            assert "not found" in result.message


class TestTriggerGitLabCI:
    """Tests for _trigger_gitlab_ci function."""

    def test_gitlab_success(self):
        """Test successful GitLab CI trigger."""
        config = CIPlatformConfig(token="glpat_test_token", url="https://gitlab.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="67890\n",
                stderr="",
            )

            result = _trigger_gitlab_ci("bd-b7d2", config)

            assert result.success is True
            assert result.build_id == "67890"
            assert "GitLab CI pipeline triggered" in result.message

    def test_gitlab_command_failure(self):
        """Test GitLab CI trigger when command fails."""
        config = CIPlatformConfig(token="glpat_test_token", url="https://gitlab.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Pipeline not found",
            )

            result = _trigger_gitlab_ci("bd-b7d2", config)

            assert result.success is False
            assert "gitlab-ci trigger failed" in result.message


class TestTriggerJenkins:
    """Tests for _trigger_jenkins function."""

    def test_jenkins_success(self):
        """Test successful Jenkins trigger."""
        config = CIPlatformConfig(token="jenkins_token", url="https://jenkins.example.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="42\n",
                stderr="",
            )

            result = _trigger_jenkins("bd-c4e1", config)

            assert result.success is True
            assert result.build_id == "42"
            assert "Jenkins build triggered" in result.message

    def test_jenkins_no_url(self):
        """Test Jenkins trigger without URL configured."""
        config = CIPlatformConfig(token="jenkins_token", url=None)

        result = _trigger_jenkins("bd-c4e1", config)

        assert result.success is False
        assert "Jenkins URL not configured" in result.message


class TestMonitorGitHubActions:
    """Tests for _monitor_github_actions function."""

    def test_monitor_success_status(self):
        """Test monitoring GitHub Actions with success status."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"status":"completed","conclusion":"success","logsUrl":"https://github.com/logs"}',
                stderr="",
            )

            status = _monitor_github_actions("12345", config)

            assert status.status == "success"
            assert status.url == "https://github.com/logs"

    def test_monitor_failure_status(self):
        """Test monitoring GitHub Actions with failure status."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"status":"completed","conclusion":"failure","logsUrl":"https://github.com/logs"}',
                stderr="",
            )

            status = _monitor_github_actions("12345", config)

            assert status.status == "failure"

    def test_monitor_running_status(self):
        """Test monitoring GitHub Actions with running status."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"status":"in_progress","conclusion":null,"logsUrl":"https://github.com/logs"}',
                stderr="",
            )

            status = _monitor_github_actions("12345", config)

            assert status.status == "running"

    def test_monitor_pending_status(self):
        """Test monitoring GitHub Actions with pending status."""
        config = CIPlatformConfig(token="ghp_test_token", url=None)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"status":"queued","conclusion":null,"logsUrl":"https://github.com/logs"}',
                stderr="",
            )

            status = _monitor_github_actions("12345", config)

            assert status.status == "pending"


class TestMonitorGitLabCI:
    """Tests for _monitor_gitlab_ci function."""

    def test_monitor_success_status(self):
        """Test monitoring GitLab CI with success status."""
        config = CIPlatformConfig(token="glpat_test_token", url="https://gitlab.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Pipeline #12345: success\n",
                stderr="",
            )

            status = _monitor_gitlab_ci("12345", config)

            assert status.status == "success"
            assert status.url is not None and "12345" in status.url

    def test_monitor_failure_status(self):
        """Test monitoring GitLab CI with failure status."""
        config = CIPlatformConfig(token="glpat_test_token", url="https://gitlab.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Pipeline #12345: failed\n",
                stderr="",
            )

            status = _monitor_gitlab_ci("12345", config)

            assert status.status == "failure"


class TestMonitorJenkins:
    """Tests for _monitor_jenkins function."""

    def test_monitor_success_status(self):
        """Test monitoring Jenkins with success status."""
        config = CIPlatformConfig(token="jenkins_token", url="https://jenkins.example.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"result":"SUCCESS","building":false}',
                stderr="",
            )

            status = _monitor_jenkins("42", config)

            assert status.status == "success"
            assert status.url is not None and "42" in status.url

    def test_monitor_failure_status(self):
        """Test monitoring Jenkins with failure status."""
        config = CIPlatformConfig(token="jenkins_token", url="https://jenkins.example.com")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='{"result":"FAILURE","building":false}',
                stderr="",
            )

            status = _monitor_jenkins("42", config)

            assert status.status == "failure"

    def test_monitor_no_url(self):
        """Test monitoring Jenkins without URL configured."""
        config = CIPlatformConfig(token="jenkins_token", url=None)

        status = _monitor_jenkins("42", config)

        assert status.status == "pending"
        assert status.logs is not None and "Jenkins URL not configured" in status.logs


class TestAppendCIEvent:
    """Tests for _append_ci_event function."""

    def test_append_event(self, mock_config: Path):
        """Test appending CI event to log."""
        event_dict = {
            "ts": "2026-01-26T10:00:00Z",
            "cmd": "ci_trigger",
            "task_id": "bd-a3f8",
            "platform": "github_actions",
            "build_id": "12345",
            "result": "ok",
        }

        _append_ci_event(event_dict, mock_config)

        event_log = mock_config / "events.log"
        assert event_log.exists()

        with open(event_log, "r") as f:
            events = [json.loads(line) for line in f]

        assert len(events) == 1
        assert events[0]["cmd"] == "ci_trigger"
        assert events[0]["task_id"] == "bd-a3f8"

    def test_append_multiple_events(self, mock_config: Path):
        """Test appending multiple CI events."""
        event_dict1 = {
            "ts": "2026-01-26T10:00:00Z",
            "cmd": "ci_trigger",
            "task_id": "bd-a3f8",
            "platform": "github_actions",
            "build_id": "12345",
            "result": "ok",
        }

        event_dict2 = {
            "ts": "2026-01-26T10:05:00Z",
            "cmd": "ci_monitor",
            "build_id": "12345",
            "platform": "github_actions",
            "status": "success",
            "result": "ok",
        }

        _append_ci_event(event_dict1, mock_config)
        _append_ci_event(event_dict2, mock_config)

        event_log = mock_config / "events.log"
        with open(event_log, "r") as f:
            events = [json.loads(line) for line in f]

        assert len(events) == 2
        assert events[0]["cmd"] == "ci_trigger"
        assert events[1]["cmd"] == "ci_monitor"
