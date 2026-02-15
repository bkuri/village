"""Research domain example demonstrating extensibility framework.

This example shows how to extend Village's chat loop for academic research
use cases, including:
- Query preprocessing for research topics
- Research methodology breakdown
- Citation formatting
- Task tracking via Beads

Example usage:
    from examples.research.chat import bootstrap_research_extensions
    from village.extensibility import initialize_extensions

    registry = bootstrap_research_extensions()
    initialize_extensions(registry, "examples/research/config.example.toml")
"""

from examples.research.chat.bootstrap import bootstrap_research_extensions

__all__ = ["bootstrap_research_extensions"]
