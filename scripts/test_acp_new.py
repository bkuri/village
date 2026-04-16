"""E2E test: create a project via ACP transport."""

from __future__ import annotations

import asyncio

from acp import PROTOCOL_VERSION, spawn_agent_process
from acp.schema import (
    CreateTerminalResponse,
    Implementation,
    KillTerminalCommandResponse,
    ReadTextFileResponse,
    ReleaseTerminalResponse,
    RequestPermissionResponse,
    TerminalOutputResponse,
    TextContentBlock,
    WaitForTerminalExitResponse,
    WriteTextFileResponse,
)


class TestClient:
    def on_connect(self, conn: object) -> None:
        pass

    async def session_update(self, session_id: str, update: object, **kwargs: object) -> None:
        text = getattr(update, "text", str(update))
        print(f"  UPDATE: {text[:300]}")

    async def request_permission(self, *args: object, **kwargs: object) -> RequestPermissionResponse:
        return RequestPermissionResponse(outcome="allowed")

    async def read_text_file(self, *args: object, **kwargs: object) -> ReadTextFileResponse:
        return ReadTextFileResponse(content="")

    async def write_text_file(self, *args: object, **kwargs: object) -> WriteTextFileResponse:
        return WriteTextFileResponse(success=True)

    async def create_terminal(self, *args: object, **kwargs: object) -> CreateTerminalResponse:
        return CreateTerminalResponse(terminal_id="test")

    async def terminal_output(self, *args: object, **kwargs: object) -> TerminalOutputResponse:
        return TerminalOutputResponse(output="")

    async def release_terminal(self, *args: object, **kwargs: object) -> ReleaseTerminalResponse:
        return ReleaseTerminalResponse(released=True)

    async def wait_for_terminal_exit(self, *args: object, **kwargs: object) -> WaitForTerminalExitResponse:
        return WaitForTerminalExitResponse(exit_status=0)

    async def kill_terminal(self, *args: object, **kwargs: object) -> KillTerminalCommandResponse:
        return KillTerminalCommandResponse(killed=True)

    async def ext_method(self, *args: object, **kwargs: object) -> dict[str, object]:
        return {}

    async def ext_notification(self, *args: object, **kwargs: object) -> None:
        pass


async def main() -> None:
    print("Creating project via ACP transport...")

    async with spawn_agent_process(
        TestClient(),
        "uv",
        "run",
        "village",
        "--transport",
        "acp",
    ) as (conn, proc):
        print(f"Started village (pid={proc.pid})")

        await conn.initialize(
            protocol_version=PROTOCOL_VERSION,
            client_info=Implementation(name="e2e-test", version="1.0.0"),
        )

        session = await conn.new_session(cwd="/tmp")

        resp = await conn.prompt(
            prompt=[TextContentBlock(type="text", text="/new testproject")],
            session_id=session.session_id,
        )
        print(f"Response: stop_reason={resp.stop_reason}")

        await conn.close()

    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
