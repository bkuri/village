"""Village Chat - Conversational interface for project knowledge."""

from village.chat.errors import ChatError
from village.chat.prompts import generate_initial_prompt

__all__ = ["ChatError", "generate_initial_prompt"]
