"""Chat message processors for pre/post processing hooks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProcessingResult:
    """Result of message processing."""

    content: str
    metadata: dict[str, object] | None = None

    def __post_init__(self) -> None:
        """Initialize metadata if not provided."""
        if self.metadata is None:
            self.metadata = {}


class ChatProcessor(ABC):
    """Base class for chat message processors.

    Allows domains to customize pre and post-processing of chat messages
    without modifying Village's core chat loop.

    Example:
        class TradingChatProcessor(ChatProcessor):
            async def pre_process(self, user_input: str) -> str:
                # Extract and normalize trading pairs
                return normalize_trading_pairs(user_input)

            async def post_process(self, response: str) -> str:
                # Format trading-specific output
                return format_trading_response(response)
    """

    @abstractmethod
    async def pre_process(self, user_input: str) -> str:
        """Process user input before LLM.

        Args:
            user_input: Raw user input from chat

        Returns:
            Processed input to send to LLM
        """
        pass

    @abstractmethod
    async def post_process(self, response: str) -> str:
        """Process LLM response before returning to user.

        Args:
            response: Raw response from LLM

        Returns:
            Processed response to return to user
        """
        pass


class DefaultChatProcessor(ChatProcessor):
    """Default no-op chat processor."""

    async def pre_process(self, user_input: str) -> str:
        """Return input unchanged."""
        return user_input

    async def post_process(self, response: str) -> str:
        """Return response unchanged."""
        return response
