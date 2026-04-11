"""Interactive selection helpers using questionary."""

from typing import Callable, TypeVar

import questionary

T = TypeVar("T")


def select_from_list(
    items: list[T],
    prompt: str,
    formatter: Callable[[T], str] = str,
    allow_none: bool = True,
) -> T | None:
    """Select an item from a list using questionary.

    Args:
        items: List of items to choose from
        prompt: Prompt to display
        formatter: Function to format each item for display
        allow_none: If True, allow canceling selection

    Returns:
        Selected item or None if canceled
    """
    if not items:
        questionary.print("No items to select from.")
        return None

    choices = [questionary.Choice(title=formatter(item), value=item) for item in items]

    if allow_none:
        choices.append(questionary.Choice(title="(cancel)", value=None))

    result = questionary.select(
        prompt,
        choices=choices,
    ).ask()
    return result  # type: ignore[no-any-return]


def multi_select_from_list(
    items: list[T],
    prompt: str,
    formatter: Callable[[T], str] = str,
) -> list[T]:
    """Select multiple items from a list using questionary.

    Args:
        items: List of items to choose from
        prompt: Prompt to display
        formatter: Function to format each item for display

    Returns:
        List of selected items
    """
    if not items:
        questionary.print("No items to select from.")
        return []

    choices = [questionary.Choice(title=formatter(item), value=item) for item in items]

    selected = questionary.checkbox(
        prompt,
        choices=choices,
        instruction="(Use space to select, enter to confirm)",
    ).ask()

    return selected or []


def confirm_action(prompt: str, default: bool = False) -> bool:
    """Ask for confirmation using questionary.

    Args:
        prompt: Prompt to display
        default: Default value if user just presses enter

    Returns:
        True if confirmed, False otherwise
    """
    result = questionary.confirm(prompt, default=default).ask()
    return result  # type: ignore[no-any-return]
