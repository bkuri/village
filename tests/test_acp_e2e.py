from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest
from acp import PROTOCOL_VERSION, spawn_agent_process
from acp.schema import (
    CreateTerminalResponse,
    Implementation,
    KillTerminalCommandResponse,
    PromptResponse,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    TextContentBlock,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)


class _ACPDummyClient:
    def on_connect(self, conn: object) -> None:
        pass

    async def session_update(self, session_id: str, update: object, **kwargs: object) -> None:
        pass

    async def request_permission(self, *args: object, **kwargs: object) -> RequestPermissionResponse:
        return RequestPermissionResponse(outcome="allowed")

    async def read_text_file(self, *args: object, **kwargs: object) -> ReadTextFileResponse:
        return ReadTextFileResponse(content="")

    async def write_text_file(self, *args: object, **kwargs: object) -> WriteTextFileResponse:
        return WriteTextFileResponse()

    async def create_terminal(self, *args: object, **kwargs: object) -> CreateTerminalResponse:
        return CreateTerminalResponse(terminal_id="test")

    async def terminal_output(self, *args: object, **kwargs: object) -> TerminalOutputResponse:
        return TerminalOutputResponse(output="", truncated=False)

    async def release_terminal(self, *args: object, **kwargs: object) -> ReleaseTerminalResponse:
        return ReleaseTerminalResponse()

    async def wait_for_terminal_exit(self, *args: object, **kwargs: object) -> WaitForTerminalExitResponse:
        return WaitForTerminalExitResponse(exit_code=0)

    async def kill_terminal(self, *args: object, **kwargs: object) -> KillTerminalCommandResponse:
        return KillTerminalCommandResponse()

    async def ext_method(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {}

    async def ext_notification(self, *args: object, **kwargs: object) -> None:
        pass


def _init_git_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, capture_output=True, check=True)
    (path / ".gitignore").write_text(".village/\n.worktrees/\n")
    subprocess.run(["git", "add", ".gitignore"], cwd=path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "init", "--author", "test <test@test.com>"],
        cwd=path,
        capture_output=True,
        check=True,
    )


async def _send_prompt(
    conn: Any,
    session_id: str,
    text: str,
) -> PromptResponse:
    return await conn.prompt(
        prompt=[TextContentBlock(type="text", text=text)],
        session_id=session_id,
    )


async def _collect_until_output(
    conn: Any,
    session_id: str,
    initial_resp: PromptResponse,
    max_turns: int = 60,
) -> dict[str, str]:
    meta = initial_resp.field_meta or {}
    if "output" in meta:
        return meta

    for _ in range(max_turns):
        if "prompt" in meta:
            prompt_text = meta.get("prompt", "")
            if "[Y/n]" in prompt_text or "[y/N]" in prompt_text:
                answer = "Y"
            else:
                answer = "skip"
        else:
            answer = ""

        resp = await _send_prompt(conn, session_id, answer)
        meta = resp.field_meta or {}

        if "output" in meta:
            return meta

    return meta


@pytest.mark.asyncio
async def test_acp_new_with_name_creates_project() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir)
        repo_dir = parent / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)
        non_git_dir = parent / "workspace"
        non_git_dir.mkdir()

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(non_git_dir))

            resp = await _send_prompt(conn, session.session_id, "/new testproject")
            assert resp.stop_reason == "end_turn"

            meta = await _collect_until_output(conn, session.session_id, resp)
            assert "output" in meta, f"Expected output, got: {meta}"
            output = meta["output"].lower()
            assert "testproject" in output or "created" in output, f"Unexpected: {meta['output']}"

            await conn.close()

            project_dir = non_git_dir / "testproject"
            assert project_dir.exists(), f"Project dir not found: {project_dir}"
            assert (project_dir / ".git").exists()


@pytest.mark.asyncio
async def test_acp_new_interactive_multi_turn() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        parent = Path(tmpdir)
        repo_dir = parent / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)
        non_git_dir = parent / "workspace"
        non_git_dir.mkdir()

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(non_git_dir))

            resp1 = await _send_prompt(conn, session.session_id, "/new")
            assert resp1.stop_reason == "end_turn"

            meta1 = resp1.field_meta or {}

            if "prompt" in meta1:
                prompt_text = meta1["prompt"]
                assert "what" in prompt_text.lower() or "building" in prompt_text.lower(), (
                    f"Unexpected prompt text: {prompt_text}"
                )

                resp2 = await _send_prompt(conn, session.session_id, "my-cool-app")
                meta_final = await _collect_until_output(conn, session.session_id, resp2)
                assert "output" in meta_final, f"Expected output, got: {meta_final}"
                output = meta_final["output"].lower()
                assert "my-cool-app" in output or "created" in output, f"Unexpected: {meta_final['output']}"

                project_dir = non_git_dir / "my-cool-app"
                assert project_dir.exists(), f"Project dir not found: {project_dir}"

            elif "output" in meta1:
                pass

            await conn.close()


@pytest.mark.asyncio
async def test_acp_tasks_list() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/tasks list")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta
            output_lower = meta["output"].lower()
            assert "no tasks" in output_lower or "error" in output_lower

            await conn.close()


@pytest.mark.asyncio
async def test_acp_help() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/help")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta
            assert "available commands" in meta["output"].lower()
            assert "tasks" in meta["output"].lower()
            assert "new" in meta["output"].lower()

            await conn.close()


@pytest.mark.asyncio
async def test_acp_goals() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/goals")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta
            output_lower = meta["output"].lower()
            assert "goal" in output_lower or "no goals" in output_lower or "no active" in output_lower

            await conn.close()


@pytest.mark.asyncio
async def test_acp_down() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/down")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta

            await conn.close()


@pytest.mark.asyncio
async def test_acp_builder_status() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/builder status")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta

            await conn.close()


@pytest.mark.asyncio
async def test_acp_planner_inspect() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/planner inspect")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta

            await conn.close()


@pytest.mark.asyncio
async def test_acp_watcher_status() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/watcher status")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta

            await conn.close()


@pytest.mark.asyncio
async def test_acp_doctor_diagnose() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/doctor diagnose")
            assert resp.stop_reason == "end_turn"

            meta = await _collect_until_output(conn, session.session_id, resp)
            assert "output" in meta

            await conn.close()


@pytest.mark.asyncio
async def test_acp_scribe() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_dir = Path(tmpdir) / "repo"
        repo_dir.mkdir()
        _init_git_repo(repo_dir)

        async with spawn_agent_process(
            _ACPDummyClient(),
            "uv",
            "run",
            "village",
            "--transport",
            "acp",
            cwd=str(repo_dir),
        ) as (conn, proc):
            await conn.initialize(
                protocol_version=PROTOCOL_VERSION,
                client_info=Implementation(name="e2e-test", version="1.0.0"),
            )

            session = await conn.new_session(cwd=str(repo_dir))

            resp = await _send_prompt(conn, session.session_id, "/scribe")
            assert resp.stop_reason == "end_turn"

            meta = resp.field_meta or {}
            assert "output" in meta or "prompt" in meta

            await conn.close()
