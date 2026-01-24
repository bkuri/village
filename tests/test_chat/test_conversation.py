"""Test conversation orchestrator."""

from village.chat.conversation import (
    should_exit,
    start_conversation,
)


def test_start_conversation(mock_config):
    """Test conversation initialization."""
    from unittest.mock import patch

    # Mock prompt generation to avoid file system dependency
    with patch("village.chat.conversation.generate_initial_prompt") as mock_gen:
        mock_gen.return_value = ("Village Chat system prompt", "embedded")

        state = start_conversation(mock_config)

        assert len(state.messages) == 1
        assert state.messages[0].role == "system"
        assert "Village Chat system prompt" in state.messages[0].content


def test_parse_llm_response_valid():
    """Test parsing valid JSON response."""
    from village.chat.conversation import _parse_llm_response

    json_response = """```json
{
  "writes": {
    "project.md": "# Project\\n\\nSummary..."
  },
  "notes": ["Some notes"],
  "open_questions": ["Question 1"]
}
```"""

    update = _parse_llm_response(json_response)

    assert update.error is None
    assert "project.md" in update.writes
    assert update.notes == ["Some notes"]
    assert update.open_questions == ["Question 1"]


def test_parse_llm_response_invalid_json():
    """Test parsing invalid JSON response."""
    from village.chat.conversation import _parse_llm_response

    invalid_response = "Not JSON at all"

    update = _parse_llm_response(invalid_response)

    assert update.error is not None
    assert "value" in update.error.lower()
    assert update.writes == {}


def test_parse_llm_response_schema_error():
    """Test parsing JSON with schema errors."""
    from village.chat.conversation import _parse_llm_response

    invalid_response = '{"writes": {"invalid.md": "..."}}'

    update = _parse_llm_response(invalid_response)

    assert update.error is not None
    assert "Unknown file name" in update.error
    assert update.writes == {}


def test_should_exit():
    """Test exit command detection."""
    assert should_exit("/exit") is True
    assert should_exit("/quit") is True
    assert should_exit("/bye") is True
    assert should_exit("hello") is False
    assert should_exit("/tasks") is False
