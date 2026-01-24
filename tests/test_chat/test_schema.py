"""Test JSON schema validation for LLM responses."""

from village.chat.schema import validate_schema


def test_valid_schema():
    """Test validation of valid JSON response."""
    data = {
        "writes": {"project.md": "# Project\n\nSummary..."},
        "notes": [],
        "open_questions": [],
    }

    errors = validate_schema(data)

    assert errors == []


def test_valid_schema_with_notes():
    """Test validation with notes field."""
    data = {
        "writes": {"project.md": "# Project\n\nSummary..."},
        "notes": ["Some metadata"],
        "open_questions": ["Question 1"],
    }

    errors = validate_schema(data)

    assert errors == []


def test_missing_writes():
    """Test validation error when 'writes' field is missing."""
    data = {"notes": []}

    errors = validate_schema(data)

    assert len(errors) == 1
    assert errors[0].field == "writes"
    assert "Missing" in errors[0].message


def test_writes_not_dict():
    """Test validation error when 'writes' is not a dict."""
    data = {"writes": "invalid"}

    errors = validate_schema(data)

    assert len(errors) == 1
    assert errors[0].field == "writes"
    assert "must be a dict" in errors[0].message


def test_invalid_filename():
    """Test validation error with invalid filename."""
    data = {"writes": {"invalid.md": "# Invalid"}}

    errors = validate_schema(data)

    assert len(errors) == 1
    assert errors[0].field == "writes.invalid.md"
    assert "Unknown file name" in errors[0].message


def test_write_value_not_string():
    """Test validation error when write value is not a string."""
    data = {"writes": {"project.md": 123}}

    errors = validate_schema(data)

    assert len(errors) == 1
    assert errors[0].field == "writes.project.md"
    assert "must be string" in errors[0].message


def test_notes_not_list():
    """Test validation error when 'notes' is not a list."""
    data = {"writes": {"project.md": "# Project"}, "notes": "invalid"}

    errors = validate_schema(data)

    assert len(errors) == 1
    assert errors[0].field == "notes"
    assert "must be a list" in errors[0].message


def test_open_questions_not_list():
    """Test validation error when 'open_questions' is not a list."""
    data = {"writes": {"project.md": "# Project"}, "open_questions": "invalid"}

    errors = validate_schema(data)

    assert len(errors) == 1
    assert errors[0].field == "open_questions"
    assert "must be a list" in errors[0].message
