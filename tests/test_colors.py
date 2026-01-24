"""Test color utilities for TTY output."""

from unittest.mock import patch

import click

from village.render.colors import (
    echo_error,
    echo_header,
    echo_info,
    echo_success,
    echo_warning,
    should_color,
    style_status,
    style_task_id,
)


class TestColorDetection:
    """Test color detection based on TTY."""

    def test_should_color_is_true_for_tty(self):
        """should_color() should return True for TTY."""
        with patch("sys.stdout.isatty", return_value=True):
            assert should_color() is True

    def test_should_color_is_false_for_pipe(self):
        """should_color() should return False for piped output."""
        with patch("sys.stdout.isatty", return_value=False):
            assert should_color() is False


class TestColorOutput:
    """Test colored output functions."""

    def test_echo_success_uses_click_secho(self):
        """echo_success() should use click.secho for TTY."""
        with patch("village.render.colors.should_color", return_value=True):
            with patch("click.secho") as mock_secho:
                echo_success("Success message")

                mock_secho.assert_called_once_with("Success message", fg="green")

    def test_echo_success_fallback_to_echo(self):
        """echo_success() should use click.echo for non-TTY."""
        with patch("village.render.colors.should_color", return_value=False):
            with patch("click.echo") as mock_echo:
                echo_success("Success message")

                mock_echo.assert_called_once_with("Success message")

    def test_echo_error_uses_click_secho(self):
        """echo_error() should use click.secho with err=True."""
        with patch("village.render.colors.should_color", return_value=True):
            with patch("click.secho") as mock_secho:
                echo_error("Error message")

                mock_secho.assert_called_once_with("Error message", fg="red", err=True)

    def test_echo_warning_uses_click_secho(self):
        """echo_warning() should use click.secho with err=True."""
        with patch("village.render.colors.should_color", return_value=True):
            with patch("click.secho") as mock_secho:
                echo_warning("Warning message")

                mock_secho.assert_called_once_with("Warning message", fg="yellow", err=True)

    def test_echo_info_uses_click_secho(self):
        """echo_info() should use click.secho for TTY."""
        with patch("village.render.colors.should_color", return_value=True):
            with patch("click.secho") as mock_secho:
                echo_info("Info message")

                mock_secho.assert_called_once_with("Info message", fg="blue")

    def test_echo_header_uses_bold(self):
        """echo_header() should use click.secho with bold=True."""
        with patch("village.render.colors.should_color", return_value=True):
            with patch("click.secho") as mock_secho:
                echo_header("Header")

                mock_secho.assert_called_once_with("Header", bold=True)


class TestStyleFunctions:
    """Test styling functions."""

    def test_style_task_id_colors_on_tty(self):
        """style_task_id() should color on TTY."""
        with patch("village.render.colors.should_color", return_value=True):
            styled = style_task_id("bd-a3f8")

            assert styled == click.style("bd-a3f8", fg="cyan")

    def test_style_task_id_plain_on_pipe(self):
        """style_task_id() should be plain for non-TTY."""
        with patch("village.render.colors.should_color", return_value=False):
            styled = style_task_id("bd-a3f8")

            assert styled == "bd-a3f8"

    def test_style_status_active_green(self):
        """style_status() should color ACTIVE green."""
        with patch("village.render.colors.should_color", return_value=True):
            styled = style_status("ACTIVE")

            assert styled == click.style("ACTIVE", fg="green")

    def test_style_status_stale_red(self):
        """style_status() should color STALE red."""
        with patch("village.render.colors.should_color", return_value=True):
            styled = style_status("STALE")

            assert styled == click.style("STALE", fg="red")

    def test_style_status_corrupted_red(self):
        """style_status() should color CORRUPTED red."""
        with patch("village.render.colors.should_color", return_value=True):
            styled = style_status("CORRUPTED")

            assert styled == click.style("CORRUPTED", fg="red")

    def test_style_status_orphan_yellow(self):
        """style_status() should color ORPHAN yellow."""
        with patch("village.render.colors.should_color", return_value=True):
            styled = style_status("ORPHAN")

            assert styled == click.style("ORPHAN", fg="yellow")

    def test_style_status_unknown_blue(self):
        """style_status() should color UNKNOWN blue."""
        with patch("village.render.colors.should_color", return_value=True):
            styled = style_status("UNKNOWN")

            assert styled == click.style("UNKNOWN", fg="blue")
