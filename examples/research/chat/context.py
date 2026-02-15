"""Research chat context for session management."""

from datetime import datetime

from village.extensibility.context import ChatContext, SessionContext


class ResearchChatContext(ChatContext):
    """Chat context for research domain.

    Minimal implementation that adds timestamp and session info to context.
    """

    async def load_context(self, session_id: str) -> SessionContext:
        """Load context for session.

        Returns empty context for minimal implementation.

        Args:
            session_id: Session identifier

        Returns:
            Empty SessionContext
        """
        return SessionContext(session_id=session_id)

    async def save_context(self, context: SessionContext) -> None:
        """Save context for session.

        Minimal implementation: does nothing.

        Args:
            context: SessionContext to save
        """
        pass

    async def enrich_context(self, context: SessionContext) -> SessionContext:
        """Enrich context with timestamp and session info.

        Args:
            context: SessionContext to enrich

        Returns:
            Enriched SessionContext
        """
        context.metadata["timestamp"] = datetime.now().isoformat()
        context.metadata["session_info"] = {
            "session_id": context.session_id,
            "session_type": "research",
        }

        return context
