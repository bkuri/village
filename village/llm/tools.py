"""Tool definitions for LLM providers."""

from dataclasses import dataclass
from typing import Optional

from village.config import Config
from village.llm.client import ToolDefinition


@dataclass
class MCPToolMapping:
    """Mapping of MCP server and tool names to tool name patterns."""

    server: str
    tool: str

    def format(self, pattern: str) -> str:
        """Format tool name using pattern.

        Args:
            pattern: Pattern with {server} and {tool} placeholders

        Returns:
            Formatted tool name
        """
        return pattern.format(server=self.server, tool=self.tool)


SEQUENTIAL_THINKING = MCPToolMapping(
    server="sequential_thinking",
    tool="sequentialthinking",
)

PERPLEXITY_SEARCH = MCPToolMapping(
    server="perplexity_sonar",
    tool="perplexity_search_web",
)

WIKIPEDIA_SEARCH = MCPToolMapping(
    server="wikipedia",
    tool="search",
)

WIKIPEDIA_READ_ARTICLE = MCPToolMapping(
    server="wikipedia",
    tool="readArticle",
)

YOUTUBE_DOWNLOAD = MCPToolMapping(
    server="youtube",
    tool="download_youtube_url",
)

PLAYWRIGHT_NAVIGATE = MCPToolMapping(
    server="playwright",
    tool="playwright_navigate",
)

PLAYWRIGHT_SCREENSHOT = MCPToolMapping(
    server="playwright",
    tool="playwright_screenshot",
)

PLAYWRIGHT_CLICK = MCPToolMapping(
    server="playwright",
    tool="playwright_click",
)

PLAYWRIGHT_FILL = MCPToolMapping(
    server="playwright",
    tool="playwright_fill",
)

PLAYWRIGHT_GET_TEXT = MCPToolMapping(
    server="playwright",
    tool="playwright_get_visible_text",
)

PLAYWRIGHT_CLOSE = MCPToolMapping(
    server="playwright",
    tool="playwright_close",
)

COINSTATS_GET_COINS = MCPToolMapping(
    server="coinstats",
    tool="get-coins",
)

COINSTATS_GET_COIN_BY_ID = MCPToolMapping(
    server="coinstats",
    tool="get-coin-by-id",
)

COINSTATS_GET_MARKET_CAP = MCPToolMapping(
    server="coinstats",
    tool="get-market-cap",
)

FEAR_GREED_INDEX = MCPToolMapping(
    server="fear_greed_index",
    tool="get_fear_greed_index",
)

ATOM_OF_THOUGHTS = MCPToolMapping(
    server="atom_of_thoughts",
    tool="AoT-light",
)

THINK = MCPToolMapping(
    server="think_tool",
    tool="think",
)


def get_tool_name_pattern(config: Optional[Config] = None) -> str:
    """Get tool name pattern from config.

    Args:
        config: Village config (optional)

    Returns:
        Tool name pattern string
    """
    if config is None:
        from village.config import get_config

        config = get_config()

    return config.mcp.tool_name_pattern


def format_mcp_tool_name(
    mapping: MCPToolMapping,
    config: Optional[Config] = None,
) -> str:
    """Format MCP tool name using pattern from config.

    Args:
        mapping: Tool mapping with server and tool names
        config: Village config (optional)

    Returns:
        Formatted tool name string
    """
    pattern = get_tool_name_pattern(config)
    return mapping.format(pattern)


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

PERPLEXITY_SEARCH_TOOL = ToolDefinition(
    name="perplexity_search",
    description="Search the web using Perplexity AI with recency filtering",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search query",
            },
            "recency": {
                "type": "string",
                "description": "Time filter for results (day, week, month, year)",
                "default": "month",
                "enum": ["day", "week", "month", "year"],
            },
        },
        "required": ["query"],
    },
)

WIKIPEDIA_SEARCH_TOOL = ToolDefinition(
    name="wikipedia_search",
    description="Search Wikipedia for articles on any topic",
    input_schema={
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Search term for Wikipedia",
            },
        },
        "required": ["query"],
    },
)

WIKIPEDIA_READ_ARTICLE_TOOL = ToolDefinition(
    name="wikipedia_read_article",
    description="Read a Wikipedia article by title or page ID",
    input_schema={
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "The title of the Wikipedia article to read",
            },
            "pageId": {
                "type": "integer",
                "description": "The page ID of the Wikipedia article to read",
            },
        },
    },
)

YOUTUBE_DOWNLOAD_TOOL = ToolDefinition(
    name="youtube_download",
    description="Download and read YouTube video subtitles",
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL of the YouTube video",
            },
        },
        "required": ["url"],
    },
)

PLAYWRIGHT_NAVIGATE_TOOL = ToolDefinition(
    name="playwright_navigate",
    description="Navigate to a URL in a browser",
    input_schema={
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "URL to navigate to",
            },
            "headless": {
                "type": "boolean",
                "description": "Run browser in headless mode (default: false)",
            },
            "browserType": {
                "type": "string",
                "description": "Browser type (chromium, firefox, webkit)",
                "default": "chromium",
                "enum": ["chromium", "firefox", "webkit"],
            },
            "width": {
                "type": "integer",
                "description": "Viewport width in pixels (default: 1280)",
            },
            "height": {
                "type": "integer",
                "description": "Viewport height in pixels (default: 720)",
            },
        },
        "required": ["url"],
    },
)

PLAYWRIGHT_SCREENSHOT_TOOL = ToolDefinition(
    name="playwright_screenshot",
    description="Take a screenshot of the current page or specific element",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name for the screenshot",
            },
            "fullPage": {
                "type": "boolean",
                "description": "Screenshot of entire page (default: false)",
            },
            "selector": {
                "type": "string",
                "description": "CSS selector for element to screenshot",
            },
        },
        "required": ["name"],
    },
)

PLAYWRIGHT_CLICK_TOOL = ToolDefinition(
    name="playwright_click",
    description="Click an element on the page",
    input_schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for element to click",
            },
        },
        "required": ["selector"],
    },
)

PLAYWRIGHT_FILL_TOOL = ToolDefinition(
    name="playwright_fill",
    description="Fill out an input field",
    input_schema={
        "type": "object",
        "properties": {
            "selector": {
                "type": "string",
                "description": "CSS selector for input field",
            },
            "value": {
                "type": "string",
                "description": "Value to fill",
            },
        },
        "required": ["selector", "value"],
    },
)

PLAYWRIGHT_GET_TEXT_TOOL = ToolDefinition(
    name="playwright_get_text",
    description="Get visible text content of the current page",
    input_schema={
        "type": "object",
        "properties": {},
    },
)

PLAYWRIGHT_CLOSE_TOOL = ToolDefinition(
    name="playwright_close",
    description="Close browser and release all resources",
    input_schema={
        "type": "object",
        "properties": {},
    },
)

COINSTATS_GET_COINS_TOOL = ToolDefinition(
    name="coinstats_get_coins",
    description="Get comprehensive cryptocurrency data (price, market cap, volume)",
    input_schema={
        "type": "object",
        "properties": {
            "limit": {
                "type": "integer",
                "description": "Number of results per page (default: 20)",
                "default": 20,
            },
            "page": {
                "type": "integer",
                "description": "Page number (default: 1)",
                "default": 1,
            },
            "currency": {
                "type": "string",
                "description": "Currency for price data (default: USD)",
                "default": "USD",
            },
            "symbol": {
                "type": "string",
                "description": "Get coins by symbol",
            },
            "sortBy": {
                "type": "string",
                "description": "Field to sort by",
            },
        },
    },
)

COINSTATS_GET_COIN_BY_ID_TOOL = ToolDefinition(
    name="coinstats_get_coin_by_id",
    description="Get detailed information about a specific cryptocurrency",
    input_schema={
        "type": "object",
        "properties": {
            "coinId": {
                "type": "string",
                "description": "Coin identifier from /coins call",
            },
            "currency": {
                "type": "string",
                "description": "Currency for price data (default: USD)",
                "default": "USD",
            },
        },
        "required": ["coinId"],
    },
)

COINSTATS_GET_MARKET_CAP_TOOL = ToolDefinition(
    name="coinstats_get_market_cap",
    description="Get global cryptocurrency market data",
    input_schema={
        "type": "object",
        "properties": {},
    },
)

COINSTATS_FEAR_GREED_INDEX_TOOL = ToolDefinition(
    name="fear_greed_index",
    description="Get US stock market Fear & Greed Index with sentiment analysis",
    input_schema={
        "type": "object",
        "properties": {},
    },
)

ATOM_OF_THOUGHTS_TOOL = ToolDefinition(
    name="aot_light",
    description="Use Atom of Thoughts (AoT-light) for fast decomposition of tasks into atomic units",
    input_schema={
        "type": "object",
        "properties": {
            "prompt": {
                "type": "string",
                "description": "The prompt to decompose into atomic units using AoT-light",
            },
        },
        "required": ["prompt"],
    },
)

THINK_TOOL = ToolDefinition(
    name="think",
    description="Use Think tool for structured reasoning and problem-solving",
    input_schema={
        "type": "object",
        "properties": {
            "thought": {
                "type": "string",
                "description": "The thought or reasoning to process",
            },
        },
        "required": ["thought"],
    },
)
