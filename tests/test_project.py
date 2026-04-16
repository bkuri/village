"""Tests for project name derivation."""

from pathlib import Path
from unittest.mock import MagicMock

from village.plans.project import (
    extract_project_from_label,
    get_project_name,
    make_project_label,
    normalize_project_path,
    sanitize_project_name,
)


def test_sanitize_simple():
    assert sanitize_project_name("My Web App") == "my-web-app"


def test_sanitize_special_chars():
    assert sanitize_project_name("project@v2.0!") == "project-v2-0"


def test_sanitize_collapse_hyphens():
    assert sanitize_project_name("foo---bar") == "foo-bar"


def test_sanitize_strip_hyphens():
    assert sanitize_project_name("--foo--") == "foo"


def test_sanitize_max_length():
    long_name = "a" * 100
    assert len(sanitize_project_name(long_name)) == 50


def test_sanitize_with_slashes():
    assert sanitize_project_name("code/my-app") == "code/my-app"


def test_sanitize_empty_returns_unnamed():
    assert sanitize_project_name("") == "unnamed"


def test_normalize_simple():
    result = normalize_project_path(Path("/home/bk/source/village"))
    assert result == "village"


def test_normalize_with_base():
    result = normalize_project_path(
        Path("/home/bk/source/code/my-app"),
        Path("/home/bk/source"),
    )
    assert result == "code/my-app"


def test_normalize_outside_base():
    result = normalize_project_path(
        Path("/other/path/my-project"),
        Path("/home/bk/source"),
    )
    assert result == "my-project"


def test_get_project_name_default():
    # Should not raise, returns something
    result = get_project_name()
    assert isinstance(result, str)
    assert len(result) > 0


def test_get_project_name_with_config():
    config = MagicMock(spec=[])
    result = get_project_name(config=config, project_path=Path("/home/user/code/my-app"))
    assert result == "my-app"


def test_get_project_name_with_path():
    result = get_project_name(project_path=Path("/home/user/code/my-app"))
    assert result == "my-app"


def test_make_project_label():
    assert make_project_label("my-webapp") == "project:my-webapp"


def test_extract_project_from_label():
    assert extract_project_from_label("project:my-webapp") == "my-webapp"


def test_extract_project_non_project_label():
    assert extract_project_from_label("stack:layer:1") is None


def test_extract_project_empty():
    assert extract_project_from_label("project:") == ""


def test_make_project_label_empty():
    assert make_project_label("unnamed") == "project:unnamed"


def test_roundtrip():
    name = "my-webapp"
    label = make_project_label(name)
    extracted = extract_project_from_label(label)
    assert extracted == name
