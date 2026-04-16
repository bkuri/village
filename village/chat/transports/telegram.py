from __future__ import annotations

import asyncio
import logging
import os
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, filters

from village.chat.transports import AsyncTransport, TransportCapabilities
from village.config import TelegramConfig
from village.dispatch import dispatch

if TYPE_CHECKING:
    from telegram.ext import Application

logger = logging.getLogger(__name__)


class SessionPhase(str, Enum):
    NEW = "NEW"
    ACTIVE = "ACTIVE"
    MILESTONE = "MILESTONE"
    RECOVER = "RECOVER"


@dataclass
class ParsedState:
    counter: int = 0
    interval: int = 50
    milestone: str = ""


_COUNTER_RE = re.compile(r"Counter:\s*(\d+)/(\d+)")
_MILESTONE_RE = re.compile(r"Milestone:\s*\n(.*?)(?:\n|$)", re.DOTALL)


class TelegramStateManager:
    def __init__(
        self,
        bot: Bot,
        chat_id: int,
        config: TelegramConfig,
        summarize_fn: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._bot = bot
        self._chat_id = chat_id
        self._config = config
        self._summarize_fn = summarize_fn
        self._pinned_message_id: int | None = None
        self._counter: int = 0
        self._phase: SessionPhase = SessionPhase.NEW
        self._milestone: str = ""
        self._context_messages: list[str] = []

    @property
    def phase(self) -> SessionPhase:
        return self._phase

    @property
    def milestone(self) -> str:
        return self._milestone

    @property
    def counter(self) -> int:
        return self._counter

    async def initialize(self) -> None:
        pinned = await self._find_pinned_message()
        if pinned is not None:
            state = self._parse_state(pinned)
            self._counter = state.counter
            self._milestone = state.milestone
            self._phase = SessionPhase.RECOVER
        else:
            await self._create_pinned_message()
            self._phase = SessionPhase.NEW

    def track_message(self, text: str) -> None:
        self._context_messages.append(text)
        if len(self._context_messages) > self._config.max_context_messages:
            self._context_messages = self._context_messages[-self._config.max_context_messages :]

    async def tick(self) -> None:
        self._counter += 1
        await self._update_pinned_message()
        if self._counter % self._config.milestone_interval == 0:
            self._phase = SessionPhase.MILESTONE
            await self._compact_milestone()
            await self._update_pinned_message()
            self._phase = SessionPhase.ACTIVE
        elif self._phase in (SessionPhase.NEW, SessionPhase.RECOVER):
            self._phase = SessionPhase.ACTIVE

    async def _find_pinned_message(self) -> str | None:
        try:
            chat = await self._bot.get_chat(self._chat_id)
            pinned_msg = chat.pinned_message
            if pinned_msg and pinned_msg.from_user and pinned_msg.text:
                if pinned_msg.from_user.id == self._bot.id and "[VILLAGE SESSION]" in pinned_msg.text:
                    self._pinned_message_id = pinned_msg.message_id
                    return pinned_msg.text
        except TelegramError as e:
            logger.warning(f"Failed to check pinned message: {e}")
        return None

    async def _create_pinned_message(self) -> None:
        text = self._build_state_message(0, self._config.milestone_interval, "")
        sent = await self._bot.send_message(
            chat_id=self._chat_id,
            text=text,
            disable_notification=True,
        )
        self._pinned_message_id = sent.message_id
        try:
            await self._bot.pin_chat_message(
                chat_id=self._chat_id,
                message_id=sent.message_id,
                disable_notification=True,
            )
        except TelegramError as e:
            logger.warning(f"Failed to pin message: {e}")

    def _parse_state(self, message_text: str) -> ParsedState:
        counter_match = _COUNTER_RE.search(message_text)
        milestone_match = _MILESTONE_RE.search(message_text)

        counter = int(counter_match.group(1)) if counter_match else 0
        interval = int(counter_match.group(2)) if counter_match else self._config.milestone_interval
        milestone = milestone_match.group(1).strip() if milestone_match else ""

        return ParsedState(counter=counter, interval=interval, milestone=milestone)

    def _build_state_message(self, counter: int, interval: int, milestone: str) -> str:
        parts = ["[VILLAGE SESSION]", f"Counter: {counter}/{interval}"]
        if milestone:
            parts.append(f"\nMilestone:\n{milestone}")
        return "\n".join(parts)

    async def _update_pinned_message(self) -> None:
        if self._pinned_message_id is None:
            return
        text = self._build_state_message(
            self._counter,
            self._config.milestone_interval,
            self._milestone,
        )
        try:
            await self._bot.edit_message_text(
                chat_id=self._chat_id,
                message_id=self._pinned_message_id,
                text=text,
            )
        except TelegramError as e:
            logger.warning(f"Failed to update pinned message: {e}")

    async def _compact_milestone(self) -> None:
        if self._summarize_fn and self._context_messages:
            context_text = "\n".join(self._context_messages)
            try:
                summary = await self._summarize_fn(context_text)
                self._milestone = summary
                self._context_messages = []
            except Exception as e:
                logger.error(f"Milestone compaction failed: {e}")
                self._milestone = context_text[-500:] if len(context_text) > 500 else context_text


class TelegramTransport(AsyncTransport):
    def __init__(
        self,
        config: TelegramConfig,
        summarize_fn: Callable[[str], Awaitable[str]] | None = None,
    ) -> None:
        self._config = config
        self._summarize_fn = summarize_fn
        self._application: Application[Any, Any, Any, Any, Any, Any] | None = None
        self._bot: Bot | None = None
        self._state_manager: TelegramStateManager | None = None
        self._chat_id: int | None = None
        self._message_queue: asyncio.Queue[str] = asyncio.Queue()
        self._running = False
        self._pending: dict[int, Any] = {}

    @property
    def name(self) -> str:
        return "telegram"

    @property
    def capabilities(self) -> TransportCapabilities:
        return TransportCapabilities(markdown=True, menus=True, persistence=True)

    async def start(self) -> None:
        token = os.environ.get(self._config.bot_token_env, "")
        if not token:
            import click

            raise click.ClickException(
                f"Telegram bot token not found. Set {self._config.bot_token_env} environment variable."
            )

        try:
            bot = Bot(token=token)
            me = await bot.get_me()
            logger.info(f"Telegram bot authenticated: @{me.username}")
        except TelegramError as e:
            import click

            raise click.ClickException(f"Invalid Telegram bot token: {e}") from e

        self._bot = bot
        app = ApplicationBuilder().token(token).build()
        self._application = app

        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        app.add_handler(MessageHandler(filters.COMMAND, self._handle_command))
        app.add_handler(MessageHandler(filters.ALL & ~filters.TEXT, self._handle_non_text))

        async def post_init(a: Application[Any, Any, Any, Any, Any, Any]) -> None:
            await a.bot.delete_webhook(drop_pending_updates=True)

        app.post_init = post_init

        await app.initialize()
        await app.start()
        if app.updater:
            await app.updater.start_polling(drop_pending_updates=True)

        self._running = True

    async def stop(self) -> None:
        self._running = False
        for pending in self._pending.values():
            pending.bridge.cancel()
            if not pending.future.done():
                pending.future.cancel()
        self._pending.clear()
        if self._application:
            updater = self._application.updater
            if updater:
                await updater.stop()
            await self._application.stop()
            await self._application.shutdown()

    async def send(self, message: str) -> None:
        if self._bot is None or self._chat_id is None:
            return
        try:
            await self._bot.send_message(chat_id=self._chat_id, text=message)
        except TelegramError as e:
            logger.error(f"Failed to send message: {e}")

    async def receive(self) -> str:
        while self._running:
            try:
                return await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
            except TimeoutError:
                continue
        return "/exit"

    async def route(self, target_role: str, context: str | None = None) -> None:
        msg = f"Routing to {target_role}."
        if context:
            msg += f"\nContext: {context}"
        await self.send(msg)

    @property
    def _dispatch_ctx(self) -> dict[str, Any]:
        return {"config": self._config}

    async def _poll_pending(self, pending: Any, chat_id: int, timeout: float = 5.0) -> None:
        elapsed = 0.0
        interval = 0.05
        while elapsed < timeout:
            if pending.future.done() or pending.bridge.has_pending_prompt:
                return
            await asyncio.sleep(interval)
            elapsed += interval

    async def _handle_interactive(self, chat_id: int, text: str) -> bool:
        pending = self._pending.get(chat_id)
        if pending is None:
            return False

        if not pending.bridge.has_pending_prompt:
            return False

        pending.bridge.provide_answer(text)
        await self._poll_pending(pending, chat_id)

        if pending.future.done():
            try:
                output = pending.future.result(timeout=0.1)
            except Exception as e:
                output = f"Error: {e}"
            del self._pending[chat_id]
            if self._bot:
                await self._bot.send_message(chat_id=chat_id, text=output or "Done.")
            return True

        if pending.bridge.has_pending_prompt:
            prompt_text = pending.bridge.get_prompt_text() or ""
            if self._bot:
                await self._bot.send_message(chat_id=chat_id, text=f"❓ {prompt_text}")
            return True

        if pending.progress and pending.progress.has_progress:
            progress_text = pending.progress.drain_progress()
            if self._bot and progress_text.strip():
                await self._bot.send_message(chat_id=chat_id, text=progress_text[:4000])
            return True

        return True

    async def _handle_message(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not update.message or not update.effective_chat:
            return

        chat_id = update.effective_chat.id

        if self._chat_id is None:
            self._chat_id = chat_id
            await self._init_state_manager()

        text = update.message.text or ""

        if await self._handle_interactive(chat_id, text):
            if self._state_manager:
                self._state_manager.track_message(text)
                await self._state_manager.tick()
            return

        result = await dispatch(self, text, self._dispatch_ctx)
        if result is not None:
            if self._bot and self._chat_id:
                await self._bot.send_message(chat_id=self._chat_id, text=result)
            return

        from village.dispatch import parse_command, spawn_command_by_name

        cmd_name, cmd_args = parse_command(text)
        if cmd_name:
            spawned = spawn_command_by_name(cmd_name, cmd_args)
            if spawned is not None:
                self._pending[chat_id] = spawned
                await self._poll_pending(spawned, chat_id)

                if spawned.bridge.has_pending_prompt:
                    prompt_text = spawned.bridge.get_prompt_text() or ""
                    if self._bot:
                        await self._bot.send_message(chat_id=chat_id, text=f"❓ {prompt_text}")
                    if self._state_manager:
                        self._state_manager.track_message(text)
                        await self._state_manager.tick()
                    return

                if spawned.future.done():
                    try:
                        output = spawned.future.result(timeout=0.1)
                    except Exception as e:
                        output = f"Error: {e}"
                    del self._pending[chat_id]
                    if self._bot:
                        await self._bot.send_message(chat_id=chat_id, text=output or "Done.")
                    return

        await self._message_queue.put(text)

        if self._state_manager:
            self._state_manager.track_message(text)
            await self._state_manager.tick()

    async def _handle_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not update.message or not update.message.text:
            return

        command = update.message.text.split()[0].lower()

        if command == "/exit":
            if update.effective_chat:
                self._chat_id = update.effective_chat.id
            await self._message_queue.put("/exit")
            self._running = False
            return

        if not update.effective_chat or not self._bot:
            return

        if command == "/start":
            self._chat_id = update.effective_chat.id
            await self._init_state_manager()
            lines = ["Village Greeter — How can I help?", "", "Type your message or /help for commands."]
            await self._bot.send_message(chat_id=self._chat_id, text="\n".join(lines))
        else:
            result = await dispatch(self, update.message.text, self._dispatch_ctx)
            if result is not None:
                await self._bot.send_message(chat_id=update.effective_chat.id, text=result)
            else:
                await self._bot.send_message(
                    chat_id=update.effective_chat.id,
                    text=f"Unknown command: {command}\nType /help for available commands.",
                )

    async def _handle_non_text(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        if not update.message or not update.effective_chat or self._bot is None:
            return
        try:
            await self._bot.send_message(
                chat_id=update.effective_chat.id,
                text="Text only, please.",
            )
        except TelegramError as e:
            logger.error(f"Failed to send rejection: {e}")

    async def _init_state_manager(self) -> None:
        if self._bot is None or self._chat_id is None:
            return
        self._state_manager = TelegramStateManager(
            bot=self._bot,
            chat_id=self._chat_id,
            config=self._config,
            summarize_fn=self._summarize_fn,
        )
        await self._state_manager.initialize()
