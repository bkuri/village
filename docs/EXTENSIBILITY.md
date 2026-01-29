# Village Extensibility Framework (PRD)

**Status**: Design Document (Ready for Implementation)  
**Date**: 2026-01-28  
**Vision**: Make Village a platform for AI-powered domain applications

---

## 1. Overview

Village is evolving from a **task decomposition tool** into a **platform for domain-specific AI applications**. This PRD defines the extensibility hooks that allow specialized domains (trading, research, planning, etc.) to customize Village's behavior without tight coupling.

### **Core Principle**
- **Village provides the infrastructure**: chat loop, sequential thinking, MCP tool invocation, beads integration
- **Domains provide the logic**: how to process messages, invoke tools, refine queries, manage state

### **Design Philosophy**
- **Thin abstractions**: Keep hooks simple and composable
- **Loose contracts**: Domains override what they need, inherit sensible defaults
- **Multi-domain support**: Any domain can use the same hooks
- **Iterative rollout**: Start with core hooks, add more as needed

---

## 2. Extension Points

### **2.1 Chat Message Processing** (`ChatProcessor`)

**Purpose**: Modify messages before/after LLM processing with domain-specific logic.

**Use Cases**:
- Trading: Extract pair symbols, risk styles from user input
- Research: Route queries to specialized research paths
- Planning: Parse domain-specific task syntax

**Abstract Class**:
```python
from abc import ABC, abstractmethod
from typing import Dict, Any

class ChatProcessor(ABC):
    """Hook for processing chat messages before/after LLM."""
    
    async def pre_process(self, message: str, context: Dict[str, Any]) -> str:
        """
        Modify message before sending to LLM.
        
        Args:
            message: User input
            context: Session context (task_id, domain config, etc.)
        
        Returns:
            Modified message for LLM
        
        Raises:
            ValueError: If message violates domain constraints
        """
        return message  # Default: no modification
    
    async def post_process(self, response: str, context: Dict[str, Any]) -> str:
        """
        Modify LLM response before returning to user.
        
        Args:
            response: LLM output
            context: Session context
        
        Returns:
            Modified response for user
        """
        return response  # Default: no modification
```

**Implementation Example (MaxiTrader)**:
```python
class TradingChatProcessor(ChatProcessor):
    async def pre_process(self, message: str, context: Dict) -> str:
        # Extract trading entities: pairs, risk styles, timeframes
        # Query knowledge store for context
        # Enhance system prompt with trading data
        return enhanced_message
    
    async def post_process(self, response: str, context: Dict) -> str:
        # Format with Rich panels
        # Add trading-specific metadata
        return formatted_response
```

---

### **2.2 MCP Tool Invocation** (`ToolInvoker`)

**Purpose**: Customize how MCP tools are invoked with domain-specific logic.

**Use Cases**:
- Trading: Cache Jesse backtest results in knowledge store
- Trading: Decide whether to run tool based on trading rules
- Research: Log tool calls for audit trail
- Any: Add domain-specific error handling

**Abstract Class**:
```python
class ToolInvoker(ABC):
    """Hook for MCP tool invocation with domain logic."""
    
    async def should_invoke(
        self,
        server_name: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> bool:
        """
        Decide if tool should be invoked.
        
        Args:
            server_name: MCP server (e.g., "perplexity", "jesse")
            tool_name: Tool name (e.g., "search", "backtest")
            tool_input: Tool parameters
            context: Session context
        
        Returns:
            True if tool should be invoked
        """
        return True  # Default: always invoke
    
    async def invoke(
        self,
        server_name: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Any:
        """
        Invoke MCP tool with domain-specific logic.
        
        Args:
            server_name: MCP server
            tool_name: Tool name
            tool_input: Tool parameters
            context: Session context
        
        Returns:
            Tool result
        
        Raises:
            RuntimeError: If tool invocation fails
        """
        # Default: call MCPUseClient directly
        return await self.mcp_client.invoke_tool(
            server_name, tool_name, tool_input
        )
    
    async def post_invoke(
        self,
        result: Any,
        server_name: str,
        tool_name: str,
        context: Dict[str, Any]
    ) -> Any:
        """
        Process tool result after invocation.
        
        Args:
            result: Raw tool result
            server_name: MCP server
            tool_name: Tool name
            context: Session context
        
        Returns:
            Processed result
        """
        return result  # Default: no modification
```

**Implementation Example (MaxiTrader)**:
```python
class TradingToolInvoker(ToolInvoker):
    async def should_invoke(self, server, tool, input, context):
        # Don't backtest if already cached
        if tool == "backtest":
            cached = await self.knowledge_store.find_similar(input)
            if cached:
                return False  # Use cached result instead
        return True
    
    async def post_invoke(self, result, server, tool, context):
        # Extract metrics and save to knowledge store
        if tool == "backtest":
            metrics = extract_metrics(result)
            await self.knowledge_store.save(context["task_id"], metrics)
        return result
```

---

### **2.3 Query Refinement** (`ThinkingRefiner`)

**Purpose**: Domain-specific query refinement before sequential thinking.

**Use Cases**:
- Trading: Break down "was aggressive better?" into specific analysis steps
- Research: Route research queries to appropriate data sources
- Planning: Parse domain-specific task notation

**Abstract Class**:
```python
@dataclass
class RefinedQuery:
    """Result of query refinement."""
    original_query: str
    refined_query: str
    analysis_steps: List[str]
    required_data_sources: List[str]  # ["knowledge_store", "jesse", "perplexity"]
    domain_context: Dict[str, Any]

class ThinkingRefiner(ABC):
    """Hook for domain-specific query refinement."""
    
    async def should_refine(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> bool:
        """
        Decide if query needs domain-specific refinement.
        
        Args:
            query: User query
            context: Session context
        
        Returns:
            True if domain-specific refinement needed
        """
        return True  # Default: always refine
    
    async def refine_query(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> RefinedQuery:
        """
        Refine query with domain-specific logic.
        
        Args:
            query: User query
            context: Session context
        
        Returns:
            RefinedQuery with analysis steps and data sources
        """
        # Default: just pass through to sequential thinking
        return RefinedQuery(
            original_query=query,
            refined_query=query,
            analysis_steps=[query],
            required_data_sources=["sequential_thinking"],
            domain_context={}
        )
```

**Implementation Example (MaxiTrader)**:
```python
class TradingThinkingRefiner(ThinkingRefiner):
    async def should_refine(self, query: str, context):
        # Only refine if task_id is present (trading context)
        return "task_id" in context
    
    async def refine_query(self, query: str, context):
        # "Was aggressive better?" becomes:
        # 1. Query knowledge store for aggressive strategies
        # 2. Query knowledge store for balanced strategies
        # 3. Run counterfactual analysis via Jesse
        # 4. Compare metrics
        return RefinedQuery(
            original_query=query,
            refined_query="Compare performance: aggressive vs balanced",
            analysis_steps=[
                "Query knowledge store for similar strategies",
                "Identify risk style variations",
                "Run counterfactual backtests",
                "Calculate performance deltas"
            ],
            required_data_sources=["knowledge_store", "jesse"],
            domain_context={"task_id": context["task_id"]}
        )
```

---

### **2.4 State/Context Management** (`ChatContext`)

**Purpose**: Domain-specific session state and context management.

**Use Cases**:
- Trading: Load/save knowledge store summaries, market snapshots
- Research: Maintain research session state, source tracking
- Planning: Track project context across messages

**Abstract Class**:
```python
class ChatContext(ABC):
    """Hook for session context management."""
    
    async def load(self, session_id: str) -> Dict[str, Any]:
        """
        Load session context.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Context dictionary
        """
        return {}  # Default: empty context
    
    async def save(self, session_id: str, context: Dict[str, Any]) -> None:
        """
        Save session context.
        
        Args:
            session_id: Session identifier
            context: Context to save
        """
        pass  # Default: no persistence
    
    async def enrich(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich context with domain-specific data.
        
        Args:
            context: Base context
        
        Returns:
            Enriched context
        """
        return context  # Default: no enrichment
```

**Implementation Example (MaxiTrader)**:
```python
class TradingChatContext(ChatContext):
    async def load(self, session_id: str):
        # Load recent tasks, knowledge summaries
        recent_tasks = await self.knowledge_store.get_recent(session_id, limit=5)
        return {
            "recent_tasks": recent_tasks,
            "knowledge_available": True
        }
    
    async def save(self, session_id: str, context):
        # Persist task references, analysis results
        await self.knowledge_store.save_session(session_id, context)
    
    async def enrich(self, context):
        # Add market data snapshots, safety scores
        market_data = await self.perplexity.get_latest("BTC ETH market")
        context["market_snapshot"] = market_data
        return context
```

---

### **2.5 Beads Integration** (`BeadsIntegrator`)

**Purpose**: Customize how domain creates/updates beads.

**Use Cases**:
- Trading: Create beads for tasks, link to knowledge store
- Research: Create research project beads
- Planning: Integrate with planning workflows

**Abstract Class**:
```python
class BeadsIntegrator(ABC):
    """Hook for beads integration."""
    
    async def should_create_bead(
        self,
        session_context: Dict[str, Any]
    ) -> bool:
        """Decide if bead should be created."""
        return False  # Default: don't create bead
    
    async def create_bead(
        self,
        title: str,
        description: str,
        session_context: Dict[str, Any]
    ) -> str:
        """Create bead and return ID."""
        pass
    
    async def update_bead(
        self,
        bead_id: str,
        status: str,
        session_context: Dict[str, Any]
    ) -> None:
        """Update bead status."""
        pass
```

---

### **2.6 MCP Server Discovery** (`ServerDiscovery`)

**Purpose**: Dynamically determine which MCP servers are available.

**Use Cases**:
- Trading: Only load Jesse if available, fall back to simulation
- Research: Discover available research APIs
- Multi-domain: Different servers per domain

**Abstract Class**:
```python
class ServerDiscovery(ABC):
    """Hook for MCP server discovery."""
    
    async def discover_servers(self) -> Dict[str, str]:
        """
        Discover available MCP servers.
        
        Returns:
            Dict of server_name -> server_url
        """
        return {}  # Default: no servers
```

---

### **2.7 LLM Provider Customization** (`LLMProviderAdapter`)

**Purpose**: Allow domains to customize LLM provider configuration.

**Use Cases**:
- Trading: Use specific Claude model for strategy analysis
- Research: Use different provider for research queries
- Cost optimization: Route to different providers based on query type

**Abstract Class**:
```python
class LLMProviderAdapter(ABC):
    """Hook for LLM provider customization."""
    
    async def get_provider_config(
        self,
        query_type: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Get LLM provider config for query."""
        return {}  # Use default config
    
    async def should_use_tools(
        self,
        query: str,
        context: Dict[str, Any]
    ) -> bool:
        """Decide if tools should be available for this query."""
        return True  # Default: enable tools
```

---

## 3. Registration & Bootstrap

### **Plugin Registration System**

```python
# village/extensibility/registry.py

class ExtensionRegistry:
    """Registry for domain extensions."""
    
    _chat_processors: List[ChatProcessor] = []
    _tool_invokers: List[ToolInvoker] = []
    _thinking_refiners: List[ThinkingRefiner] = []
    _chat_contexts: List[ChatContext] = []
    _beads_integrators: List[BeadsIntegrator] = []
    _server_discoveries: List[ServerDiscovery] = []
    _llm_adapters: List[LLMProviderAdapter] = []
    
    @classmethod
    def register_chat_processor(cls, processor: ChatProcessor) -> None:
        cls._chat_processors.append(processor)
    
    @classmethod
    def register_tool_invoker(cls, invoker: ToolInvoker) -> None:
        cls._tool_invokers.append(invoker)
    
    # ... similar for other extensions
    
    @classmethod
    def get_chat_processors(cls) -> List[ChatProcessor]:
        return cls._chat_processors
    
    # ... similar for other extensions
```

### **Bootstrap Pattern** (for domains)

```python
# maxitrader/chat/bootstrap.py

from village.extensibility import ExtensionRegistry

def bootstrap_trading_extensions():
    """Register all MaxiTrader extensions."""
    ExtensionRegistry.register_chat_processor(TradingChatProcessor())
    ExtensionRegistry.register_tool_invoker(TradingToolInvoker())
    ExtensionRegistry.register_thinking_refiner(TradingThinkingRefiner())
    ExtensionRegistry.register_chat_context(TradingChatContext())
    ExtensionRegistry.register_beads_integrator(TradingBeadsIntegrator())
    ExtensionRegistry.register_server_discovery(TradingServerDiscovery())
```

---

## 4. Configuration

### **Extended VillageConfig**

```python
# village/config.py

@dataclass
class VillageConfig:
    # Core village settings (unchanged)
    llm_provider: str
    mcp_use_path: str
    
    # Extension settings
    extensions_enabled: bool = True
    domain_config: Dict[str, Any] = field(default_factory=dict)
    
    # Registered extensions (populated at runtime)
    extensions: Dict[str, List[Any]] = field(default_factory=dict)
```

### **Example Configuration (MaxiTrader)**

```toml
# config/maxitrader.toml

[village]
llm_provider = "anthropic"
mcp_use_path = "mcp-use"
extensions_enabled = true

[domain]
log_dir = "$HOME/.maxitrader/logs"
knowledge_dir = "$HOME/.maxitrader/knowledge"
risk_style = "balanced"

[domain.enabled_servers]
jesse = true
perplexity = true
sequential_thinking = true
```

---

## 5. Implementation Phases

### **Phase 1: Core Extensibility** (Village)
- Create extensibility ABCs (all 7 hooks)
- Implement ExtensionRegistry
- Update VillageConfig with extension support
- Update chat loop to call hooks at appropriate points
- Documentation: extension points, how to implement hooks

### **Phase 2: Default Implementations** (Village)
- Default ChatProcessor (no-op)
- Default ToolInvoker (MCPUseClient wrapper)
- Default ThinkingRefiner (pass-through)
- Default ChatContext (in-memory only)
- Default BeadsIntegrator (no-op)
- Default ServerDiscovery (static config)
- Default LLMProviderAdapter (use config)

### **Phase 3: MaxiTrader Integration**
- Implement all 7 extensions for trading domain
- Create bootstrap.py to register extensions
- Integrate with chat command
- Document trading extensions

### **Phase 4: Documentation & Examples**
- Extension development guide
- Example: simple research domain
- Example: planning domain adapter
- API reference for each extension point

---

## 6. Design Principles

### **Kept Loose**
- Extensions override what they need, inherit defaults
- Minimal required methods (most have defaults)
- Domains compose multiple extensions as needed
- No global state or coupling between extensions

### **Kept Thin**
- Each hook has single responsibility
- Pass context dict instead of tight coupling to specific data
- No domain logic in Village core
- Village provides infrastructure, domains provide logic

### **Multi-Domain Ready**
- Same hooks work for trading, research, planning, etc.
- Registry allows multiple domains to coexist if needed
- No hardcoding of "what is a task" - domains define this

---

## 7. Migration Path

### **For Existing Village Code**
- No breaking changes
- Hooks are optional (all have sensible defaults)
- Existing behavior unchanged if no extensions registered

### **For Future Domains**
- Implement only needed extensions
- Inherit defaults for others
- Bootstrap and register in domain code

---

## 8. Success Criteria

- ✅ Village core remains <5000 lines (thin)
- ✅ All extension ABCs total <500 lines
- ✅ MaxiTrader can fully customize chat behavior via hooks
- ✅ No tight coupling between Village and MaxiTrader
- ✅ Third domain (e.g., research) can add extensions without Village changes
- ✅ Registry system is simple and testable
- ✅ Documentation enables domain devs to add extensions in <2 hours

---

## 9. Future Expansion Points

- **Hook lifecycle**: on_init, on_shutdown per extension
- **Extension priorities/ordering**: if multiple domains loaded
- **Hook composition**: chains of processors
- **Telemetry hooks**: observe Village behavior without modifying it
- **Custom message types**: beyond text (structured data, media)

---

## 10. Questions & Decisions

**Q: Loose contracts - how do we prevent undefined behavior?**
A: Type hints + docstrings. Domains responsible for correct implementation. Testing catches bugs. Falls in line with Python philosophy.

**Q: Multiple domains at once?**
A: ExtensionRegistry supports it. All extensions called in order. Domains responsible for not conflicting.

**Q: How to share state between extensions?**
A: Via context dict passed through call chain. Or domain-specific storage (knowledge store, beads, etc.).

**Q: Version compatibility?**
A: Hook ABCs are stable contracts. Minor changes backward compatible. Major changes = new hook version.

---

End of PRD
