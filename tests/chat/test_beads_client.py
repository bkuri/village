"""Tests for BeadsClient wrapper."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from village.chat.beads_client import BeadsClient, BeadsError
from village.chat.task_spec import TaskSpec


@pytest.fixture
def beads_client() -> BeadsClient:
    """Create a BeadsClient instance."""
    return BeadsClient()


class TestBeadsClient:
    """Test BeadsClient methods."""

    @pytest.mark.asyncio
    async def test_search_tasks(self, beads_client: BeadsClient) -> None:
        """Test searching tasks in Beads."""
        mock_tasks = [
            {"id": "bd-a1b2", "title": "Fix bug", "status": "open"},
            {"id": "bd-c3d4", "title": "Add feature", "status": "open"},
        ]

        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_tasks)
            mock_run.return_value = mock_result

            tasks = await beads_client.search_tasks("bug", limit=5, status="open")

            assert len(tasks) == 2
            assert tasks[0]["id"] == "bd-a1b2"
            assert tasks[0]["title"] == "Fix bug"

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "bd" in cmd
            assert "list" in cmd
            assert "--title" in cmd
            assert "bug" in cmd
            assert "--limit" in cmd
            assert "5" in cmd
            assert "--status" in cmd
            assert "open" in cmd

    @pytest.mark.asyncio
    async def test_search_tasks_invalid_json(self, beads_client):
        """Test search_tasks with invalid JSON response."""
        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "invalid json{{"
            mock_run.return_value = mock_result

            with pytest.raises(BeadsError, match="Failed to parse Beads response"):
                await beads_client.search_tasks("test")

    @pytest.mark.asyncio
    async def test_search_tasks_not_a_list(self, beads_client):
        """Test search_tasks when response is not a list."""
        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps({"error": "something went wrong"})
            mock_run.return_value = mock_result

            with pytest.raises(BeadsError, match="Expected list from bd list"):
                await beads_client.search_tasks("test")

    @pytest.mark.asyncio
    async def test_create_task(self, beads_client):
        """Test creating a task in Beads."""
        spec = TaskSpec(
            title="Add new feature",
            description="Implement new feature with proper testing",
            scope="feature",
            blocks=["bd-a1b2"],
            blocked_by=[],
            success_criteria=["Tests pass"],
            estimate="2h",
        )

        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "Created task bd-x7y8\nTask saved successfully"
            mock_run.return_value = mock_result

            task_id = await beads_client.create_task(spec)

            assert task_id == "bd-x7y8"

            mock_run.assert_called_once()
            cmd = mock_run.call_args[0][0]
            assert "bd" in cmd
            assert "create" in cmd
            assert "Add new feature" in cmd
            assert "--description" in cmd
            assert "Implement new feature with proper testing" in cmd
            assert "--deps" in cmd
            assert "blocks:bd-a1b2" in cmd

    @pytest.mark.asyncio
    async def test_create_task_multiple_deps(self, beads_client):
        """Test creating a task with multiple dependencies."""
        spec = TaskSpec(
            title="Integration test",
            description="Add integration tests",
            scope="test",
            blocks=["bd-a1b2", "bd-c3d4"],
            blocked_by=["bd-e5f6"],
            success_criteria=["Integration tests pass"],
            estimate="1h",
        )

        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "Created task bd-z9y8\nTask saved"
            mock_run.return_value = mock_result

            task_id = await beads_client.create_task(spec)

            assert task_id == "bd-z9y8"

            cmd = mock_run.call_args[0][0]
            deps_arg = cmd[cmd.index("--deps") + 1]
            assert "blocks:bd-a1b2,bd-c3d4" in deps_arg
            assert "blocked_by:bd-e5f6" in deps_arg

    @pytest.mark.asyncio
    async def test_create_task_no_deps(self, beads_client):
        """Test creating a task without dependencies."""
        spec = TaskSpec(
            title="Simple task",
            description="Just a simple task",
            scope="feature",
            blocks=[],
            blocked_by=[],
            success_criteria=["Task completes"],
            estimate="30m",
        )

        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "Task bd-1234 created"
            mock_run.return_value = mock_result

            task_id = await beads_client.create_task(spec)

            assert task_id == "bd-1234"

            cmd = mock_run.call_args[0][0]
            assert "--deps" not in cmd

    @pytest.mark.asyncio
    async def test_create_task_no_task_id(self, beads_client):
        """Test create_task when output doesn't contain task ID."""
        spec = TaskSpec(
            title="Test task",
            description="Test",
            scope="test",
            blocks=[],
            blocked_by=[],
            success_criteria=["Test passes"],
            estimate="1h",
        )

        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "Something happened but no task ID"
            mock_run.return_value = mock_result

            with pytest.raises(BeadsError, match="Could not extract task ID"):
                await beads_client.create_task(spec)

    @pytest.mark.asyncio
    async def test_get_dependencies(self, beads_client):
        """Test getting task dependencies."""
        mock_deps = {
            "task_id": "bd-a1b2",
            "blocks": ["bd-c3d4"],
            "blocked": ["bd-e5f6"],
        }

        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(mock_deps)
            mock_run.return_value = mock_result

            deps = await beads_client.get_dependencies("bd-a1b2")

            assert deps["task_id"] == "bd-a1b2"
            assert deps["blocks"] == ["bd-c3d4"]
            assert deps["blocked"] == ["bd-e5f6"]

            cmd = mock_run.call_args[0][0]
            assert "bd" in cmd
            assert "dep" in cmd
            assert "list" in cmd
            assert "bd-a1b2" in cmd

    @pytest.mark.asyncio
    async def test_get_dependencies_invalid_json(self, beads_client):
        """Test get_dependencies with invalid JSON response."""
        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = "invalid json"
            mock_run.return_value = mock_result

            with pytest.raises(BeadsError, match="Failed to parse Beads response"):
                await beads_client.get_dependencies("bd-a1b2")

    @pytest.mark.asyncio
    async def test_get_dependencies_not_a_dict(self, beads_client):
        """Test get_dependencies when response is not a dict."""
        with patch.object(beads_client, "_run_command", new_callable=AsyncMock) as mock_run:
            mock_result = MagicMock()
            mock_result.stdout = json.dumps(["list", "not", "dict"])
            mock_run.return_value = mock_result

            with pytest.raises(BeadsError, match="Expected dict from bd dep list"):
                await beads_client.get_dependencies("bd-a1b2")

    @pytest.mark.asyncio
    async def test_run_command_success(self, beads_client):
        """Test running a successful Beads command."""
        with patch("subprocess.run") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "success output"
            mock_result.stderr = ""
            mock_subprocess.return_value = mock_result

            result = await beads_client._run_command(["bd", "list"])

            assert result.returncode == 0
            assert result.stdout == "success output"
            mock_subprocess.assert_called_once_with(
                ["bd", "list"],
                capture_output=True,
                text=True,
                check=False,
            )

    @pytest.mark.asyncio
    async def test_run_command_failure(self, beads_client):
        """Test running a failed Beads command."""
        with patch("subprocess.run") as mock_subprocess:
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_result.stderr = "Error: task not found"
            mock_subprocess.return_value = mock_result

            with pytest.raises(BeadsError, match="Beads command failed"):
                await beads_client._run_command(["bd", "list"])

            mock_subprocess.assert_called_once()


class TestParseEstimate:
    """Test parse_estimate method."""

    def test_parse_estimate_range_hours(self, beads_client):
        """Test parsing range estimate in hours."""
        assert beads_client.parse_estimate("2-3 hours") == 150
        assert beads_client.parse_estimate("2-3 hrs") == 150
        assert beads_client.parse_estimate("1-2 hours") == 90
        assert beads_client.parse_estimate("0.5-1 hours") == 45

    def test_parse_estimate_single_hours(self, beads_client):
        """Test parsing single value estimate in hours."""
        assert beads_client.parse_estimate("2 hours") == 120
        assert beads_client.parse_estimate("2 hrs") == 120
        assert beads_client.parse_estimate("2 hr") == 120
        assert beads_client.parse_estimate("2 h") == 120
        assert beads_client.parse_estimate("1.5 hours") == 90

    def test_parse_estimate_minutes(self, beads_client):
        """Test parsing estimate in minutes."""
        assert beads_client.parse_estimate("30 min") == 30
        assert beads_client.parse_estimate("30 mins") == 30
        assert beads_client.parse_estimate("30 minutes") == 30
        assert beads_client.parse_estimate("30 minute") == 30
        assert beads_client.parse_estimate("30 m") == 30
        assert beads_client.parse_estimate("45 minutes") == 45

    def test_parse_estimate_days(self, beads_client):
        """Test parsing estimate in days (8-hour workday)."""
        assert beads_client.parse_estimate("1 day") == 8 * 60
        assert beads_client.parse_estimate("1 days") == 8 * 60
        assert beads_client.parse_estimate("2 days") == 16 * 60
        assert beads_client.parse_estimate("1.5 days") == 12 * 60
        assert beads_client.parse_estimate("1 d") == 8 * 60

    def test_parse_estimate_weeks(self, beads_client):
        """Test parsing estimate in weeks (5-day workweek, 8-hour day)."""
        assert beads_client.parse_estimate("1 week") == 5 * 8 * 60
        assert beads_client.parse_estimate("2 weeks") == 10 * 8 * 60
        assert beads_client.parse_estimate("1 w") == 5 * 8 * 60

    def test_parse_estimate_empty_string(self, beads_client):
        """Test parsing empty estimate string."""
        with pytest.raises(BeadsError, match="Empty estimate string"):
            beads_client.parse_estimate("")

    def test_parse_estimate_invalid_format(self, beads_client):
        """Test parsing invalid estimate format."""
        with pytest.raises(BeadsError, match="Invalid estimate format"):
            beads_client.parse_estimate("invalid")

        with pytest.raises(BeadsError, match="Invalid estimate format"):
            beads_client.parse_estimate("just text")

    def test_parse_estimate_whitespace(self, beads_client):
        """Test parsing estimate with whitespace."""
        assert beads_client.parse_estimate("  2 hours  ") == 120
        assert beads_client.parse_estimate("\t3 hours\n") == 180


class TestExtractTaskId:
    """Test _extract_task_id method."""

    def test_extract_task_id_standard_format(self, beads_client):
        """Test extracting task ID from standard format."""
        assert beads_client._extract_task_id("Created task bd-a1b2c3") == "bd-a1b2c3"
        assert beads_client._extract_task_id("Task bd-x7y8z9 saved") == "bd-x7y8z9"

    def test_extract_task_id_with_created_prefix(self, beads_client):
        """Test extracting task ID with 'created:' prefix."""
        assert beads_client._extract_task_id("created: bd-a1b2") == "bd-a1b2"
        assert beads_client._extract_task_id("created:bd-c3d4") == "bd-c3d4"

    def test_extract_task_id_with_task_id_prefix(self, beads_client):
        """Test extracting task ID with 'task id:' prefix."""
        assert beads_client._extract_task_id("task id: bd-a1b2") == "bd-a1b2"
        assert beads_client._extract_task_id("task id:bd-c3d4") == "bd-c3d4"

    def test_extract_task_id_with_id_prefix(self, beads_client):
        """Test extracting task ID with 'id:' prefix."""
        assert beads_client._extract_task_id("id: bd-a1b2") == "bd-a1b2"
        assert beads_client._extract_task_id("id:bd-c3d4") == "bd-c3d4"

    def test_extract_task_id_case_insensitive(self, beads_client):
        """Test extracting task ID with different cases."""
        assert beads_client._extract_task_id("Created task BD-A1B2") == "bd-a1b2"
        assert beads_client._extract_task_id("CREATED: bd-x7y8") == "bd-x7y8"

    def test_extract_task_id_not_found(self, beads_client):
        """Test when task ID is not in output."""
        assert beads_client._extract_task_id("No task ID here") is None
        assert beads_client._extract_task_id("") is None
