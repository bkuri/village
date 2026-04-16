from __future__ import annotations

import asyncio
import logging
from typing import Any

from acp.interfaces import Agent
from acp.schema import (
    AgentCapabilities,
    AuthenticateResponse,
    ClientCapabilities,
    ForkSessionResponse,
    Implementation,
    InitializeResponse,
    ListSessionsResponse,
    LoadSessionResponse,
    NewSessionResponse,
    PromptResponse,
    ResumeSessionResponse,
    SetSessionConfigOptionResponse,
    SetSessionModelResponse,
    SetSessionModeResponse,
)

from village.config import Config, get_config

logger = logging.getLogger(__name__)


class ACPTransportAgent(Agent):
    def __init__(self, config: Config) -> None:
        self._config = config
        self._sessions: dict[str, dict[str, Any]] = {}
        self._pending_commands: dict[str, Any] = {}
        self._conn: Any = None

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities: ClientCapabilities | None = None,
        client_info: Implementation | None = None,
        **kwargs: Any,
    ) -> InitializeResponse:
        return InitializeResponse(
            protocol_version=protocol_version,
            agent_capabilities=AgentCapabilities(),
            agent_info=Implementation(name="village", version="1.0.0"),
        )

    async def new_session(
        self,
        cwd: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> NewSessionResponse:
        import uuid

        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {"cwd": cwd}
        logger.info(f"ACP session created: {session_id}")
        return NewSessionResponse(session_id=session_id)

    async def load_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> LoadSessionResponse | None:
        return LoadSessionResponse()

    async def list_sessions(
        self,
        cursor: str | None = None,
        cwd: str | None = None,
        **kwargs: Any,
    ) -> ListSessionsResponse:
        from acp.schema import SessionInfo

        sessions = [SessionInfo(session_id=sid, cwd=s.get("cwd", "")) for sid, s in self._sessions.items()]
        return ListSessionsResponse(sessions=sessions)

    async def set_session_mode(
        self,
        mode_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModeResponse | None:
        return None

    async def set_session_model(
        self,
        model_id: str,
        session_id: str,
        **kwargs: Any,
    ) -> SetSessionModelResponse | None:
        if session_id in self._sessions:
            self._sessions[session_id]["model"] = model_id
        return SetSessionModelResponse()

    async def set_config_option(
        self,
        config_id: str,
        session_id: str,
        value: str,
        **kwargs: Any,
    ) -> SetSessionConfigOptionResponse | None:
        return None

    async def authenticate(
        self,
        method_id: str,
        **kwargs: Any,
    ) -> AuthenticateResponse | None:
        return None

    async def _wait_for_command(self, pending: Any, timeout: float = 5.0) -> None:
        elapsed = 0.0
        interval = 0.05
        while elapsed < timeout:
            if pending.future.done() or pending.bridge.has_pending_prompt:
                return
            if pending.progress and pending.progress.has_progress:
                return
            await asyncio.sleep(interval)
            elapsed += interval

    async def prompt(
        self,
        prompt: list[Any],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        from village.dispatch import parse_command, spawn_command_by_name

        message = self._extract_text(prompt)
        logger.info(f"ACP prompt for session {session_id}: {message[:100]}")

        if session_id not in self._sessions:
            self._sessions[session_id] = {}

        if session_id in self._pending_commands:
            pending = self._pending_commands[session_id]
            if pending.bridge.has_pending_prompt:
                pending.bridge.provide_answer(message)
                await self._wait_for_command(pending)
            else:
                await self._wait_for_command(pending)

            if (
                pending.progress
                and pending.progress.has_progress
                and not pending.bridge.has_pending_prompt
                and not pending.future.done()
            ):
                progress_text = pending.progress.drain_progress()
                return PromptResponse(
                    stop_reason="end_turn",
                    field_meta={"progress": progress_text},
                )

            if pending.future.done():
                try:
                    pending.output = pending.future.result(timeout=0.1)
                except Exception as e:
                    pending.output = f"Error: {e}"
                del self._pending_commands[session_id]
                logger.info(f"ACP response for session {session_id}: {pending.output[:200]}")
                return PromptResponse(
                    stop_reason="end_turn",
                    field_meta={"output": pending.output},
                )

            if pending.bridge.has_pending_prompt:
                prompt_text = pending.bridge.get_prompt_text() or ""
                return PromptResponse(
                    stop_reason="end_turn",
                    field_meta={"prompt": prompt_text},
                )

            return PromptResponse(stop_reason="end_turn")

        cmd_name, cmd_args = parse_command(message)

        session_cwd = self._sessions.get(session_id, {}).get("cwd")

        if cmd_name:
            result = spawn_command_by_name(cmd_name, cmd_args, cwd=session_cwd)
            if result is not None:
                self._pending_commands[session_id] = result
                await self._wait_for_command(result)

                if (
                    result.progress
                    and result.progress.has_progress
                    and not result.bridge.has_pending_prompt
                    and not result.future.done()
                ):
                    progress_text = result.progress.drain_progress()
                    return PromptResponse(
                        stop_reason="end_turn",
                        field_meta={"progress": progress_text},
                    )

                if result.bridge.has_pending_prompt:
                    prompt_text = result.bridge.get_prompt_text() or ""
                    return PromptResponse(
                        stop_reason="end_turn",
                        field_meta={"prompt": prompt_text},
                    )

                if result.future.done():
                    try:
                        result.output = result.future.result(timeout=0.1)
                    except Exception as e:
                        result.output = f"Error: {e}"
                    del self._pending_commands[session_id]
                    logger.info(f"ACP response for session {session_id}: {result.output[:200]}")
                    return PromptResponse(
                        stop_reason="end_turn",
                        field_meta={"output": result.output},
                    )

                return PromptResponse(stop_reason="end_turn")

        output = await self._dispatch_fallback(message, session_id)
        return PromptResponse(
            stop_reason="end_turn",
            field_meta={"output": output},
        )

    async def _dispatch_fallback(self, message: str, session_id: str) -> str:
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
                result = await entry.handler(self._mock_transport(), args, {"config": self._config})
                return result or ""
            except Exception as e:
                return f"Error: {e}"

        try:
            from village.chat.llm_chat import LLMChat
            from village.llm.factory import get_llm_client

            if session_id not in self._sessions:
                self._sessions[session_id] = {}
            llm_chat = self._sessions[session_id].get("llm_chat")
            if llm_chat is None:
                llm_client = get_llm_client(self._config)
                llm_chat = LLMChat(llm_client, config=self._config)
                self._sessions[session_id]["llm_chat"] = llm_chat
            result = await llm_chat.handle_message(message)
            return result or ""
        except Exception as e:
            logger.warning(f"LLM fallback failed: {e}")
            return ""

    def _mock_transport(self) -> Any:
        from unittest.mock import MagicMock

        from village.chat.transports import AsyncTransport, TransportCapabilities

        transport = MagicMock(spec=AsyncTransport)
        transport.name = "acp"
        transport.capabilities = TransportCapabilities()
        return transport

    async def fork_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> ForkSessionResponse:
        raise NotImplementedError("Session forking not supported")

    async def resume_session(
        self,
        cwd: str,
        session_id: str,
        mcp_servers: list[Any] | None = None,
        **kwargs: Any,
    ) -> ResumeSessionResponse:
        return ResumeSessionResponse()

    async def cancel(self, session_id: str, **kwargs: Any) -> None:
        if session_id in self._pending_commands:
            pending = self._pending_commands.pop(session_id)
            pending.bridge.cancel()
            if not pending.future.done():
                pending.future.cancel()
        if session_id in self._sessions:
            self._sessions[session_id].pop("llm_chat", None)

    async def ext_method(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        return {}

    async def ext_notification(self, method: str, params: dict[str, Any]) -> None:
        pass

    def on_connect(self, conn: Any) -> None:
        self._conn = conn
        logger.info("ACP client connected")

    def _extract_text(self, prompt: list[Any]) -> str:
        texts: list[str] = []
        for block in prompt:
            if hasattr(block, "text"):
                texts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
        return " ".join(texts)


async def run_acp_transport(config: Config | None = None) -> None:
    from acp import run_agent

    cfg = config or get_config()
    agent = ACPTransportAgent(cfg)
    logger.info("Starting Village ACP transport daemon")
    await run_agent(agent)
