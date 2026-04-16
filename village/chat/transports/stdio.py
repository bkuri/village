from __future__ import annotations

import asyncio
import json
import sys
from typing import Any

from village.chat.transports import AsyncTransport, TransportCapabilities
from village.dispatch import PendingCommand


class StdioTransport(AsyncTransport):
    def __init__(self) -> None:
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    @property
    def name(self) -> str:
        return "stdio"

    @property
    def capabilities(self) -> TransportCapabilities:
        return TransportCapabilities(streaming=True, files=True)

    async def start(self) -> None:
        loop = asyncio.get_event_loop()
        self._reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(self._reader)
        await loop.connect_read_pipe(lambda: protocol, sys.stdin)
        write_pipe = sys.stdout
        w_transport, _ = await loop.connect_write_pipe(asyncio.streams.FlowControlMixin, write_pipe)
        self._writer = asyncio.StreamWriter(w_transport, asyncio.streams.FlowControlMixin(), None, loop)

    async def stop(self) -> None:
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
            self._writer = None

    async def send(self, message: str) -> None:
        line = json.dumps({"type": "message", "content": message}, ensure_ascii=False)
        if self._writer:
            self._writer.write(line.encode() + b"\n")
            await self._writer.drain()

    async def receive(self) -> str:
        if self._reader is None:
            return ""
        data = await self._reader.readline()
        if not data:
            return ""
        try:
            obj: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError:
            return data.decode().strip()
        return str(obj.get("content", ""))

    async def route(self, target_role: str, context: str | None = None) -> None:
        msg = f"Routing to {target_role}."
        if context:
            msg += f"\nContext: {context}"
        await self.send(msg)


async def run_stdio_transport(config: Any) -> None:
    from village.dispatch import (
        parse_command,
        spawn_command_by_name,
    )

    transport = StdioTransport()
    await transport.start()

    pending: PendingCommand | None = None

    try:
        while True:
            raw = await transport.receive()
            if not raw:
                break

            message = raw.strip()
            if not message:
                continue

            if pending is not None:
                if pending.bridge.has_pending_prompt:
                    pending.bridge.provide_answer(message)
                    await _wait_for_command(pending)

                if pending.future.done():
                    try:
                        pending.output = pending.future.result(timeout=0.1)
                    except Exception as e:
                        pending.output = f"Error: {e}"
                    await transport.send(pending.output)
                    pending = None
                    continue

                if pending.bridge.has_pending_prompt:
                    prompt_text = pending.bridge.get_prompt_text() or ""
                    await transport.send(prompt_text)
                    continue

                await transport.send("")
                continue

            cmd_name, cmd_args = parse_command(message)

            if cmd_name:
                result = spawn_command_by_name(cmd_name, cmd_args)
                if result is not None:
                    pending = result
                    await _wait_for_command(pending)

                    if pending.bridge.has_pending_prompt:
                        prompt_text = pending.bridge.get_prompt_text() or ""
                        await transport.send(prompt_text)
                        continue

                    if pending.future.done():
                        try:
                            pending.output = pending.future.result(timeout=0.1)
                        except Exception as e:
                            pending.output = f"Error: {e}"
                        await transport.send(pending.output)
                        pending = None
                        continue

                    await transport.send("")
                    continue

            output = await _dispatch_fallback(message, config, transport)
            if output:
                await transport.send(output)

    except Exception:
        pass
    finally:
        if pending and not pending.future.done():
            pending.bridge.cancel()
            pending.future.cancel()
        await transport.stop()


async def _wait_for_command(pending: PendingCommand, timeout: float = 5.0) -> None:
    elapsed = 0.0
    interval = 0.05
    while elapsed < timeout:
        if pending.future.done() or pending.bridge.has_pending_prompt:
            return
        await asyncio.sleep(interval)
        elapsed += interval


async def _dispatch_fallback(message: str, config: Any, transport: AsyncTransport) -> str:
    from village.dispatch import _ensure_registry

    registry = _ensure_registry()
    stripped = message.strip()
    parts = stripped.split(None, 1)
    cmd = parts[0].lstrip("/")
    args = parts[1] if len(parts) > 1 else ""

    entry = registry.get(cmd)
    if entry is None and len(parts) >= 2:
        two_word = f"{cmd} {parts[1]}"
        entry = registry.get(two_word)
        if entry:
            remaining = parts[2:] if len(parts) > 2 else []
            args = " ".join(remaining)

    if entry:
        try:
            result = await entry.handler(transport, args, {"config": config})
            return result or ""
        except Exception as e:
            return f"Error: {e}"

    try:
        from village.chat.llm_chat import LLMChat
        from village.llm.factory import get_llm_client

        llm_client = get_llm_client(config)
        llm_chat = LLMChat(llm_client, config=config)
        result = await llm_chat.handle_message(message)
        return result or ""
    except Exception:
        return ""
