"""Color utilities for TTY output."""

import sys

import click


def echo_success(message: str) -> None:
    """Print success message (green)."""
    if should_color():
        click.secho(message, fg="green")
    else:
        click.echo(message)


def echo_error(message: str) -> None:
    """Print error message (red)."""
    if should_color():
        click.secho(message, fg="red", err=True)
    else:
        click.echo(message, err=True)


def echo_warning(message: str) -> None:
    """Print warning message (yellow)."""
    if should_color():
        click.secho(message, fg="yellow", err=True)
    else:
        click.echo(message, err=True)


def echo_info(message: str) -> None:
    """Print info message (blue)."""
    if should_color():
        click.secho(message, fg="blue")
    else:
        click.echo(message)


def echo_header(message: str) -> None:
    """Print header (bold)."""
    if should_color():
        click.secho(message, bold=True)
    else:
        click.echo(message)


def should_color() -> bool:
    """Check if color output should be used."""
    return sys.stdout.isatty()


def style_task_id(task_id: str) -> str:
    """Style task ID for display."""
    if should_color():
        return click.style(task_id, fg="cyan")
    return task_id


def style_status(status: str) -> str:
    """Style status indicator."""
    color_map = {
        "ACTIVE": "green",
        "STALE": "red",
        "CORRUPTED": "red",
        "ORPHAN": "yellow",
        "UNKNOWN": "blue",
    }
    if should_color() and status in color_map:
        return click.style(status, fg=color_map[status])
    return status
