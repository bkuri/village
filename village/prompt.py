from __future__ import annotations

import logging
import threading

import click

logger = logging.getLogger(__name__)


class PromptBridge:
    def __init__(self) -> None:
        self._request = threading.Event()
        self._response = threading.Event()
        self._prompt_text: str = ""
        self._answer: str = ""

    def request_prompt(self, text: str) -> str:
        self._response.clear()
        self._prompt_text = text
        self._request.set()
        self._response.wait()
        return self._answer

    @property
    def has_pending_prompt(self) -> bool:
        return self._request.is_set()

    def get_prompt_text(self) -> str | None:
        if self._request.is_set():
            return self._prompt_text
        return None

    def provide_answer(self, answer: str) -> None:
        self._answer = answer
        self._request.clear()
        self._response.set()

    def cancel(self) -> None:
        self._answer = ""
        self._request.clear()
        self._response.set()


_active_bridge: PromptBridge | None = None


def set_bridge(bridge: PromptBridge | None) -> None:
    global _active_bridge
    _active_bridge = bridge


def get_bridge() -> PromptBridge | None:
    return _active_bridge


def sync_prompt(
    text: str = "",
    default: str = "",
    show_default: bool = True,
    type: type | None = None,
    prompt_suffix: str = ": ",
) -> str:
    bridge = _active_bridge
    if bridge is not None:
        display = text
        if show_default and default:
            display += f" [{default}]"
        answer = bridge.request_prompt(display or text)
        if not answer and default:
            return default
        if type is int and answer:
            return str(int(answer))
        return answer
    result = click.prompt(text, default=default, show_default=show_default, type=type, prompt_suffix=prompt_suffix)
    return str(result)


def sync_confirm(
    text: str,
    default: bool = True,
) -> bool:
    bridge = _active_bridge
    if bridge is not None:
        suffix = " [Y/n]" if default else " [y/N]"
        display = text + suffix
        answer = bridge.request_prompt(display).strip().lower()
        if not answer:
            return default
        return answer in ("y", "yes")
    return click.confirm(text, default=default)
