from __future__ import annotations

import threading
import time
from unittest.mock import patch

from village.prompt import (
    PromptBridge,
    get_bridge,
    set_bridge,
    sync_confirm,
    sync_prompt,
)


def test_bridge_request_prompt() -> None:
    bridge = PromptBridge()
    results: list[str] = []

    def ask() -> None:
        answer = bridge.request_prompt("What is your name?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.has_pending_prompt
    assert bridge.get_prompt_text() == "What is your name?"
    bridge.provide_answer("Alice")
    t.join(timeout=1.0)
    assert results == ["Alice"]


def test_bridge_has_pending_prompt_false_initially() -> None:
    bridge = PromptBridge()
    assert bridge.has_pending_prompt is False


def test_bridge_get_prompt_text_none_when_no_pending() -> None:
    bridge = PromptBridge()
    assert bridge.get_prompt_text() is None


def test_bridge_cancel() -> None:
    bridge = PromptBridge()
    results: list[str] = []

    def ask() -> None:
        answer = bridge.request_prompt("Cancelled?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.has_pending_prompt
    bridge.cancel()
    t.join(timeout=1.0)
    assert results == [""]
    assert bridge.has_pending_prompt is False


def test_bridge_provide_answer_clears_pending() -> None:
    bridge = PromptBridge()
    results: list[str] = []

    def ask() -> None:
        answer = bridge.request_prompt("Q?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.has_pending_prompt
    bridge.provide_answer("A")
    t.join(timeout=1.0)
    assert bridge.has_pending_prompt is False


def test_sync_prompt_with_bridge() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[str] = []

    def ask() -> None:
        answer = sync_prompt("Name?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("Bob")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == ["Bob"]


def test_sync_prompt_without_bridge_falls_back_to_click() -> None:
    set_bridge(None)
    with patch("village.prompt.click.prompt", return_value="hello") as mock_prompt:
        result = sync_prompt("What is your name?")
        assert result == "hello"
        mock_prompt.assert_called_once_with(
            "What is your name?", default="", show_default=True, type=None, prompt_suffix=": "
        )


def test_sync_prompt_with_bridge_and_default() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[str] = []

    def ask() -> None:
        answer = sync_prompt("Port?", default="8080")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.get_prompt_text() == "Port? [8080]"
    bridge.provide_answer("")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == ["8080"]


def test_sync_prompt_with_bridge_and_type_int() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[str] = []

    def ask() -> None:
        answer = sync_prompt("Count?", type=int)
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("42")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == ["42"]


def test_sync_prompt_with_bridge_type_int_invalid_raises() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    errors: list[ValueError] = []

    def ask() -> None:
        try:
            sync_prompt("Count?", type=int)
        except ValueError as e:
            errors.append(e)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("not_a_number")
    t.join(timeout=1.0)
    set_bridge(None)
    assert len(errors) == 1


def test_sync_prompt_with_bridge_no_show_default() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[str] = []

    def ask() -> None:
        answer = sync_prompt("Port?", default="8080", show_default=False)
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.get_prompt_text() == "Port?"
    bridge.provide_answer("3000")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == ["3000"]


def test_sync_confirm_with_bridge_yes() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.get_prompt_text() == "Continue? [Y/n]"
    bridge.provide_answer("y")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [True]


def test_sync_confirm_with_bridge_no() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("n")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [False]


def test_sync_confirm_with_bridge_empty_returns_default_true() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?", default=True)
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.get_prompt_text() == "Continue? [Y/n]"
    bridge.provide_answer("")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [True]


def test_sync_confirm_with_bridge_empty_returns_default_false() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?", default=False)
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    assert bridge.get_prompt_text() == "Continue? [y/N]"
    bridge.provide_answer("")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [False]


def test_sync_confirm_with_bridge_uppercase_yes() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("YES")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [True]


def test_sync_confirm_with_bridge_full_word_yes() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("yes")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [True]


def test_sync_confirm_with_bridge_arbitrary_text_returns_false() -> None:
    bridge = PromptBridge()
    set_bridge(bridge)
    results: list[bool] = []

    def ask() -> None:
        answer = sync_confirm("Continue?")
        results.append(answer)

    t = threading.Thread(target=ask)
    t.start()
    time.sleep(0.05)
    bridge.provide_answer("maybe")
    t.join(timeout=1.0)
    set_bridge(None)
    assert results == [False]


def test_sync_confirm_without_bridge_falls_back_to_click() -> None:
    set_bridge(None)
    with patch("village.prompt.click.confirm", return_value=True) as mock_confirm:
        result = sync_confirm("Continue?")
        assert result is True
        mock_confirm.assert_called_once_with("Continue?", default=True)


def test_set_and_get_bridge() -> None:
    set_bridge(None)
    assert get_bridge() is None
    bridge = PromptBridge()
    set_bridge(bridge)
    assert get_bridge() is bridge
    set_bridge(None)
    assert get_bridge() is None
