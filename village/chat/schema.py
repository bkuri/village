"""JSON schema validation for LLM responses."""

from dataclasses import dataclass
from typing import Any

ALLOWED_FILES = {
    "project.md",
    "goals.md",
    "constraints.md",
    "assumptions.md",
    "decisions.md",
    "open-questions.md",
}


@dataclass
class ValidationError:
    """JSON schema validation error."""

    field: str
    message: str


def validate_schema(data: dict[str, Any]) -> list[ValidationError]:
    """
    Validate LLM JSON response against schema.

    Args:
        data: Parsed JSON from LLM response

    Returns:
        List of validation errors (empty if valid)
    """
    errors = []

    if "writes" not in data:
        errors.append(ValidationError("writes", "Missing required field 'writes'"))
        return errors

    if not isinstance(data["writes"], dict):
        errors.append(ValidationError("writes", "Field 'writes' must be a dict"))
        return errors

    for key in data["writes"].keys():
        if key not in ALLOWED_FILES:
            errors.append(
                ValidationError(
                    f"writes.{key}",
                    f"Unknown file name '{key}'. Allowed: {ALLOWED_FILES}",
                )
            )

    for key, value in data["writes"].items():
        if not isinstance(value, str):
            errors.append(
                ValidationError(
                    f"writes.{key}", f"Value must be string, got {type(value).__name__}"
                )
            )

    if "notes" in data and not isinstance(data["notes"], list):
        errors.append(ValidationError("notes", "Field 'notes' must be a list"))

    if "open_questions" in data and not isinstance(data["open_questions"], list):
        errors.append(ValidationError("open_questions", "Field 'open_questions' must be a list"))

    return errors
