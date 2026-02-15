"""Bootstrap function for research extensions."""

from examples.research.chat.beads_integrators import ResearchBeadsIntegrator
from examples.research.chat.context import ResearchChatContext
from examples.research.chat.processors import ResearchChatProcessor
from examples.research.chat.thinking_refiners import ResearchThinkingRefiner
from examples.research.chat.tool_invokers import ResearchToolInvoker
from village.extensibility import ExtensionRegistry


def bootstrap_research_extensions() -> ExtensionRegistry:
    """Bootstrap and register all research extensions.

    Creates an ExtensionRegistry and registers all research domain
    extensions for use with Village's chat loop.

    Returns:
        ExtensionRegistry with all research extensions registered
    """
    registry = ExtensionRegistry()

    registry.register_processor(ResearchChatProcessor())
    registry.register_thinking_refiner(ResearchThinkingRefiner())
    registry.register_tool_invoker(ResearchToolInvoker())
    registry.register_chat_context(ResearchChatContext())
    registry.register_beads_integrator(ResearchBeadsIntegrator())

    return registry
