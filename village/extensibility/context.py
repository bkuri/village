"""Chat context hooks for session state management."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class SessionContext:
    """Session context data."""

    session_id: str
    user_data: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get user data value."""
        return self.user_data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set user data value."""
        self.user_data[key] = value


class ChatContext(ABC):
    """Base class for session context management.

    Allows domains to maintain and enrich session state, including
    loading historical data, enriching with market data, etc.

    Example:
        class TradingChatContext(ChatContext):
            async def load_context(self, session_id: str) -> SessionContext:
                # Load recent trading tasks and market data
                return SessionContext(
                    session_id=session_id,
                    user_data={
                        "recent_tasks": [...],
                        "market_data": {...},
                        "portfolio_value": 100000
                    }
                )
    """

    @abstractmethod
    async def load_context(self, session_id: str) -> SessionContext:
        """Load context for session.

        Args:
            session_id: Session identifier

        Returns:
            SessionContext with session data
        """
        pass

    @abstractmethod
    async def save_context(self, context: SessionContext) -> None:
        """Save context for session.

        Args:
            context: SessionContext to save
        """
        pass

    @abstractmethod
    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Enrich context with domain-specific data.

        Args:
            context: SessionContext to enrich

        Returns:
            Enriched SessionContext
        """
        pass


class DefaultChatContext(ChatContext):
    """Default minimal chat context."""

    async def load_context(self, session_id: str) -> SessionContext:
        """Return empty context."""
        return SessionContext(session_id=session_id)

    async def save_context(self, context: SessionContext) -> None:
        """Do nothing."""
        pass

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Return context unchanged."""
        return context
