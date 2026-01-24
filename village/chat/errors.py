"""Exit codes and error definitions for Village Chat."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChatExitCode(Enum):
    """Exit codes for Village Chat operations."""

    # Success
    SUCCESS = 0

    # Draft not found errors
    DRAFT_NOT_FOUND = 1001
    DRAFT_NOT_FOUND_ON_ENABLE = 1002
    DRAFT_NOT_FOUND_ON_EDIT = 1003
    DRAFT_NOT_FOUND_ON_DISCARD = 1004

    # Submission errors
    NO_DRAFTS_ENABLED = 2001
    BATCH_SUBMISSION_FAILED = 2002
    INVALID_DRAFT_JSON = 2003

    # Reset errors
    NO_CREATED_TASKS = 3001
    RESET_FAILED = 3002

    # Mode errors
    MODE_CONFLICT = 4001

    # Generic errors
    INVALID_STATE = 5001
    OPERATION_FAILED = 5002

    # Prompt generation errors
    PROMPT_GENERATION_FAILED = 6001
    PPC_COMPILATION_FAILED = 6002
    PATTERN_FILE_NOT_FOUND = 6003


class PromptGenerationError(Exception):
    """Raised when prompt generation fails."""


@dataclass
class ChatError:
    """Structured error with code and message."""

    code: ChatExitCode
    message: str
    details: dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        return self.message
