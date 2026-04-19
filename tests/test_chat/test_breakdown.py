"""Tests for task breakdown module."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from village.chat.chat_session import ChatSession
from village.chat.sequential_thinking import TaskBreakdown, TaskBreakdownItem
from village.chat.task_spec import TaskSpec
from village.extensibility import ExtensionRegistry
from village.extensibility.task_hooks import TaskHookSpec


def _make_two_item_breakdown() -> TaskBreakdown:
    return TaskBreakdown(
        items=[
            TaskBreakdownItem(
                title="Setup project",
                description="Init project structure",
                estimated_effort="2h",
                success_criteria=["Structure created"],
                blockers=[],
                dependencies=[],
                tags=[],
            ),
            TaskBreakdownItem(
                title="Add auth",
                description="JWT authentication",
                estimated_effort="1d",
                success_criteria=["Auth works"],
                blockers=[],
                dependencies=[0],
                tags=[],
            ),
        ],
        summary="Two tasks",
        created_at="2026-01-01T00:00:00",
    )


class TestConfirmBreakdown:
    @pytest.mark.asyncio
    async def test_no_breakdown_returns_error(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        session = ChatSession()
        store = MagicMock()
        extensions = ExtensionRegistry()
        result = await confirm_breakdown(session, store, extensions, "sid", None)
        assert "No breakdown to confirm" in result

    @pytest.mark.asyncio
    async def test_invalid_dependencies_returns_error(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        invalid_breakdown = TaskBreakdown(
            items=[
                TaskBreakdownItem(
                    title="T1",
                    description="D",
                    estimated_effort="1h",
                    success_criteria=[],
                    blockers=[],
                    dependencies=[5],
                    tags=[],
                ),
            ],
            summary="Invalid deps",
            created_at="2026-01-01T00:00:00",
        )
        session = ChatSession()
        session.current_breakdown = invalid_breakdown
        store = MagicMock()
        extensions = ExtensionRegistry()
        result = await confirm_breakdown(session, store, extensions, "sid", None)
        assert "invalid" in result.lower()

    @pytest.mark.asyncio
    async def test_creates_all_subtasks(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        session = ChatSession()
        session.current_breakdown = _make_two_item_breakdown()

        mock_task1 = MagicMock()
        mock_task1.id = "tsk-001"
        mock_task1.created_at = "2026-01-01T00:00:00"
        mock_task2 = MagicMock()
        mock_task2.id = "tsk-002"
        mock_task2.created_at = "2026-01-01T00:00:00"

        store = MagicMock()
        store.create_task.side_effect = [mock_task1, mock_task2]

        extensions = ExtensionRegistry()
        result = await confirm_breakdown(session, store, extensions, "sid", None)

        assert "Created 2 subtasks" in result
        assert "tsk-001" in result
        assert "tsk-002" in result
        assert session.current_breakdown is None
        assert store.create_task.call_count == 2

    @pytest.mark.asyncio
    async def test_dependency_resolution(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        session = ChatSession()
        session.current_breakdown = _make_two_item_breakdown()

        mock_task1 = MagicMock()
        mock_task1.id = "tsk-first"
        mock_task1.created_at = "2026-01-01T00:00:00"
        mock_task2 = MagicMock()
        mock_task2.id = "tsk-second"
        mock_task2.created_at = "2026-01-01T00:00:00"

        store = MagicMock()
        store.create_task.side_effect = [mock_task1, mock_task2]

        extensions = ExtensionRegistry()
        await confirm_breakdown(session, store, extensions, "sid", None)

        first_call = store.create_task.call_args_list[0][0][0]
        assert first_call.depends_on == []

        second_call = store.create_task.call_args_list[1][0][0]
        assert "tsk-first" in second_call.depends_on
        assert "tsk-first" in second_call.blocks

    @pytest.mark.asyncio
    async def test_task_hooks_fire_when_enabled(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        session = ChatSession()
        session.current_breakdown = _make_two_item_breakdown()

        mock_task = MagicMock()
        mock_task.id = "tsk-hooked"
        mock_task.created_at = "2026-01-01T00:00:00"
        store = MagicMock()
        store.create_task.return_value = mock_task

        mock_hooks = MagicMock()
        mock_hooks.should_create_task_hook = AsyncMock(return_value=True)
        mock_hooks.create_hook_spec = AsyncMock(
            return_value=TaskHookSpec(
                title="Hooked task",
                description="",
                issue_type="feature",
                priority=2,
                parent_id="parent-123",
                metadata={"key": "val"},
            )
        )
        mock_hooks.on_task_created = AsyncMock()

        extensions = ExtensionRegistry()
        extensions.register_task_hooks(mock_hooks)

        result = await confirm_breakdown(session, store, extensions, "sid", None)
        assert "Created 2 subtasks" in result
        assert mock_hooks.should_create_task_hook.call_count == 2
        assert mock_hooks.on_task_created.call_count == 2

    @pytest.mark.asyncio
    async def test_task_store_error_returns_error_message(self) -> None:
        from village.chat.breakdown import confirm_breakdown
        from village.tasks import TaskStoreError

        session = ChatSession()
        session.current_breakdown = _make_two_item_breakdown()

        store = MagicMock()
        store.create_task.side_effect = TaskStoreError("duplicate task")

        extensions = ExtensionRegistry()
        result = await confirm_breakdown(session, store, extensions, "sid", None)
        assert "Failed to create task" in result
        assert "duplicate task" in result

    @pytest.mark.asyncio
    async def test_breakdown_summary_included(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        session = ChatSession()
        bd = _make_two_item_breakdown()
        bd.summary = "This is a summary of the breakdown"
        session.current_breakdown = bd

        mock_task1 = MagicMock()
        mock_task1.id = "tsk-1"
        mock_task1.created_at = "2026-01-01T00:00:00"
        mock_task2 = MagicMock()
        mock_task2.id = "tsk-2"
        mock_task2.created_at = "2026-01-01T00:00:00"
        store = MagicMock()
        store.create_task.side_effect = [mock_task1, mock_task2]

        extensions = ExtensionRegistry()
        result = await confirm_breakdown(session, store, extensions, "sid", None)
        assert "This is a summary of the breakdown" in result

    @pytest.mark.asyncio
    async def test_empty_breakdown(self) -> None:
        from village.chat.breakdown import confirm_breakdown

        session = ChatSession()
        session.current_breakdown = TaskBreakdown(items=[], summary="", created_at="2026-01-01T00:00:00")
        store = MagicMock()
        extensions = ExtensionRegistry()
        result = await confirm_breakdown(session, store, extensions, "sid", None)
        assert "Created 0 subtasks" in result


class TestShouldDecompose:
    @pytest.mark.asyncio
    async def test_llm_says_decompose(self) -> None:
        from village.chat.breakdown import should_decompose

        llm_client = MagicMock()
        llm_client.call = MagicMock(return_value='{"should_decompose": true, "reasoning": "complex task"}')
        extensions = ExtensionRegistry()
        task_spec = TaskSpec(
            title="Build system",
            description="Build the whole system",
            scope="feature",
            blocks=[],
            blocked_by=[],
            success_criteria=[],
            estimate="2w",
        )
        should, reason = await should_decompose(llm_client, extensions, task_spec)
        assert should is True
        assert reason == "complex task"

    @pytest.mark.asyncio
    async def test_llm_says_no_decompose(self) -> None:
        from village.chat.breakdown import should_decompose

        llm_client = MagicMock()
        llm_client.call = MagicMock(return_value='{"should_decompose": false, "reasoning": "simple"}')
        extensions = ExtensionRegistry()
        task_spec = TaskSpec(
            title="Fix typo",
            description="Fix a typo in docs",
            scope="chore",
            blocks=[],
            blocked_by=[],
            success_criteria=[],
            estimate="1h",
        )
        should, reason = await should_decompose(llm_client, extensions, task_spec)
        assert should is False

    @pytest.mark.asyncio
    async def test_json_parse_error_fallback(self) -> None:
        from village.chat.breakdown import should_decompose

        llm_client = MagicMock()
        llm_client.call = MagicMock(return_value="not json")
        extensions = ExtensionRegistry()
        task_spec = TaskSpec(
            title="Test",
            description="Test",
            scope="task",
            blocks=[],
            blocked_by=[],
            success_criteria=[],
            estimate="1h",
        )
        should, reason = await should_decompose(llm_client, extensions, task_spec)
        assert should is False
        assert "Error" in reason

    @pytest.mark.asyncio
    async def test_retry_on_llm_failure(self) -> None:
        from village.chat.breakdown import should_decompose

        llm_client = MagicMock()
        llm_client.call = MagicMock(
            side_effect=[Exception("timeout"), '{"should_decompose": false, "reasoning": "ok"}']
        )
        extensions = ExtensionRegistry()
        task_spec = TaskSpec(
            title="Test",
            description="Test",
            scope="task",
            blocks=[],
            blocked_by=[],
            success_criteria=[],
            estimate="1h",
        )
        should, reason = await should_decompose(llm_client, extensions, task_spec)
        assert should is False


class TestOfferDecomposition:
    @pytest.mark.asyncio
    async def test_no_config_returns_error(self) -> None:
        from village.chat.breakdown import offer_decomposition

        llm_client = MagicMock()
        task_spec = TaskSpec(
            title="Test",
            description="Test",
            scope="task",
            blocks=[],
            blocked_by=[],
            success_criteria=[],
            estimate="1h",
        )
        extensions = ExtensionRegistry()
        breakdown, msg = await offer_decomposition(llm_client, None, task_spec, "input", extensions)
        assert breakdown is None
        assert "Config not available" in msg
