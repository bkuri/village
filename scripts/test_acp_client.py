"""Quick ACP transport test - spawns village and sends messages via ACP protocol."""

from __future__ import annotations

import asyncio

from acp import PROTOCOL_VERSION, spawn_agent_process


async def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("Usage: python scripts/test_acp_client.py <message>")
        sys.exit(1)

    message = " ".join(sys.argv[1:])

    class TestClient:
        def on_connect(self, conn: object) -> None:
            print("CLIENT: Connected to Village ACP agent")

        async def session_update(self, session_id: str, update: object, **kwargs: object) -> None:
            text = getattr(update, "text", str(update))
            print(f"CLIENT UPDATE [{session_id[:8]}]: {text[:200]}")

        async def request_permission(self, *args: object, **kwargs: object) -> object:
            from acp.schema import RequestPermissionResponse

            return RequestPermissionResponse(outcome="allowed")

        async def read_text_file(self, *args: object, **kwargs: object) -> object:
            return None

        async def write_text_file(self, *args: object, **kwargs: object) -> object:
            return None

        async def create_terminal(self, *args: object, **kwargs: object) -> object:
            return None

        async def terminal_output(self, *args: object, **kwargs: object) -> object:
            return None

        async def release_terminal(self, *args: object, **kwargs: object) -> object:
            return None

        async def wait_for_terminal_exit(self, *args: object, **kwargs: object) -> object:
            return None

        async def kill_terminal(self, *args: object, **kwargs: object) -> object:
            return None

        async def ext_method(self, *args: object, **kwargs: object) -> object:
            return {}

        async def ext_notification(self, *args: object, **kwargs: object) -> None:
            pass

    async with spawn_agent_process(
        TestClient(),
        "uv",
        "run",
        "village",
        "--transport",
        "acp",
    ) as (conn, proc):
        print(f"CLIENT: Village process started (pid={proc.pid})")

        init_resp = await conn.initialize(
            protocol_version=PROTOCOL_VERSION,
            client_info={"name": "test-client", "version": "1.0.0"},
        )
        print(f"CLIENT: Initialized: protocol={init_resp.protocol_version}")

        session = await conn.new_session(cwd="/tmp")
        print(f"CLIENT: Session: {session.session_id}")

        resp = await conn.prompt(
            prompt=[{"type": "text", "text": message}],
            session_id=session.session_id,
        )
        print(f"CLIENT: Response stop_reason={resp.stop_reason}")

        await conn.close()
        print("CLIENT: Done")


if __name__ == "__main__":
    asyncio.run(main())
