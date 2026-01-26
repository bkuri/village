"""Tool definitions for LLM providers."""

from village.llm.client import ToolDefinition

SEQUENTIAL_THINKING_TOOL = ToolDefinition(
    name="sequential_thinking",
    description="Use Sequential Thinking to break down complex tasks into substeps",
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The prompt to analyze using Sequential Thinking",
            },
            "total_thoughts": {
                "type": "integer",
                "description": "Estimated number of thinking steps",
                "default": 5,
            },
        },
        "required": ["prompt"],
    },
)
