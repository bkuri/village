# ACP Integration Overview

**Agent Client Protocol (ACP)** integration enables Village to work with ecosystem tools while preserving its core coordination model.

---

## What is ACP?

ACP (Agent Client Protocol) is an open protocol that standardizes communication between AI agents and clients (editors, IDEs, orchestrators). It provides:

- **Standard interface** for agent-client communication
- **Session lifecycle** management (new, load, prompt, cancel)
- **File system** and **terminal** APIs
- **Real-time notifications** for state changes
- **Capability negotiation** between agents and clients

**Official SDK**: Village uses the official `agent-client-protocol` Python SDK.

---

## Village's Hybrid Architecture

Village uses a **hybrid approach** that adds ACP compatibility without changing Village core:

```
┌─────────────────────────────────────────┐
│         ACP Interface Layer             │
│  (village/acp/agent.py, bridge.py)      │
└────────────────┬────────────────────────┘
                 │ Protocol Translation
┌────────────────┴────────────────────────┐
│         Village Core (unchanged)        │
│  - Lock system                          │
│  - Worktree management                  │
│  - Task coordination                    │
│  - State machine                        │
└─────────────────────────────────────────┘
```

### Why Hybrid?

1. **Preserves Village's strengths** - Lock-based coordination, tmux truth, git worktrees
2. **Ecosystem compatibility** - Works with ACP-compliant editors and agents
3. **No core changes** - ACP is an interface layer, not a replacement
4. **Incremental adoption** - Use ACP features only when needed

---

## Two Modes of Operation

### 1. Village as ACP Server

Village exposes its coordination capabilities to ACP-compatible editors.

**Use when:**
- You want to use Village from Zed, JetBrains, or other ACP editors
- You want editor integration for task management
- You want to trigger Village operations from your IDE

**How it works:**
```
Editor (Zed/JetBrains) → ACP → Village Server → Village Core
                                              ↓
                                          tmux/git/locks
```

**Example:**
```bash
# Start Village as ACP server
village acp --server start

# Configure your editor to connect to localhost:9876
```

### 2. Village as ACP Client

Village spawns and orchestrates external ACP-compliant agents.

**Use when:**
- You want to use Claude Code, Gemini CLI, or other ACP agents
- You want Village to coordinate multiple external agents
- You want specialized agents for specific tasks

**How it works:**
```
Village Core → ACP Client → External Agent (Claude Code)
     ↓                           ↓
 tmux/git                  Agent's tools/models
```

**Example:**
```bash
# Spawn an external ACP agent
village acp --client spawn claude

# List configured agents
village acp --client list
```

---

## Architecture Components

### 1. ACP Server (`village/acp/agent.py`)

Implements the ACP Agent protocol to expose Village to editors.

**Key responsibilities:**
- Initialize handshake with editors
- Create/load ACP sessions (maps to Village tasks)
- Handle prompt requests (maps to Village resume)
- Stream notifications to editors

**Implementation:**
```python
class VillageACPAgent:
    """Village as an ACP-compliant agent."""
    
    async def initialize(...)  # Protocol handshake
    async def new_session(...)  # Create Village task
    async def load_session(...)  # Load existing task
    async def prompt(...)       # Execute Village resume
    async def cancel(...)       # Pause/cancel task
```

### 2. ACP Client (`village/acp/external_client.py`)

Connects to external ACP agents for Village to orchestrate.

**Key responsibilities:**
- Spawn external agent processes
- Manage agent lifecycle
- Forward Village operations to agents
- Handle agent responses

**Implementation:**
```python
class VillageACPClient(Client):
    """Village's ACP client for external agents."""
    
    async def request_permission(...)  # Auto-approve or prompt
    async def session_update(...)      # Handle agent notifications
```

### 3. ACP Bridge (`village/acp/bridge.py`)

The critical integration layer that translates between ACP and Village.

**Key responsibilities:**
- Map ACP sessions to Village tasks
- Bridge ACP methods to Village operations
- Convert Village events to ACP notifications
- Handle state transitions and error translation

**Implementation:**
```python
class ACPBridge:
    """Bridge ACP protocol to Village core."""
    
    # Session lifecycle
    async def session_new(...)
    async def session_load(...)
    async def session_prompt(...)
    async def session_cancel(...)
    
    # File system
    async def fs_read_text_file(...)
    async def fs_write_text_file(...)
    
    # Terminal
    async def terminal_create(...)
    async def terminal_output(...)
    async def terminal_kill(...)
    
    # Notifications
    async def stream_notifications(...)
```

---

## Protocol Mapping

### ACP Sessions → Village Tasks

| ACP Concept | Village Concept | Notes |
|-------------|-----------------|-------|
| Session | Task | 1:1 mapping |
| Session ID | Task ID | Same identifier |
| New session | Task creation (QUEUED) | Via state machine |
| Load session | Task lookup | Read state + lock |
| Prompt | Resume execution | Spawns agent in tmux |
| Cancel | Pause or fail | State-dependent |

### ACP Methods → Village Operations

| ACP Method | Village Operation | Implementation |
|------------|-------------------|----------------|
| `session/new` | Create task | `state_machine.initialize_state()` |
| `session/load` | Load task | `state_machine.get_state()` + lock lookup |
| `session/prompt` | Execute task | `execute_resume()` |
| `session/cancel` | Pause/fail task | `state_machine.transition()` |
| `fs/read_text_file` | Read from worktree | Path validation + file read |
| `fs/write_text_file` | Write to worktree | Atomic write + validation |
| `terminal/create` | Create tmux pane | `create_window()` |
| `terminal/output` | Capture pane output | `capture_pane()` |
| `terminal/kill` | Kill tmux pane | `kill_session()` |

### Village Events → ACP Notifications

| Village Event | ACP Notification | Type |
|---------------|------------------|------|
| State transition | `session/update` | `state_change` |
| File modified | `session/update` | `file_change` |
| Conflict detected | `session/update` | `conflict` |
| Task queued | `session/update` | `lifecycle` |
| Error | `session/update` | `error` |

---

## Benefits for Village Users

### 1. Editor Integration

**Before ACP:** Village only accessible via CLI
```bash
village queue --n 3
village resume bd-a3f8
```

**After ACP:** Use Village from your favorite editor
```
[Zed Editor]
├── Assistant Panel
│   └── Village (ACP)
│       ├── Start task: bd-a3f8
│       ├── View status
│       └── Stream notifications
```

### 2. Multi-Agent Orchestration

**Before ACP:** Only OpenCode agents
```ini
[agent.worker]
type = opencode
```

**After ACP:** Mix OpenCode + Claude Code + Gemini CLI
```ini
[agent.worker]
type = opencode

[agent.claude]
type = acp
acp_command = claude-code

[agent.gemini]
type = acp
acp_command = gemini-cli
```

### 3. Ecosystem Compatibility

- **Zed Editor**: Built-in ACP support
- **JetBrains IDEs**: ACP plugin available
- **Claude Code**: ACP-compliant agent
- **Gemini CLI**: ACP-compliant agent
- **Custom agents**: Any ACP-compliant agent

### 4. Real-Time Notifications

**Before ACP:** Poll-based status checks
```bash
watch -n 5 'village status --workers'
```

**After ACP:** Real-time event streaming
```python
async for notification in bridge.stream_notifications(session_id):
    # React to state changes instantly
    handle_notification(notification)
```

---

## Supported Editors

### Zed Editor

**Status:** ✅ Supported (native ACP support)

**Setup:**
1. Install Zed (0.120+)
2. Configure ACP agent in Zed settings:
   ```json
   {
     "assistant": {
       "default_model": {
         "provider": "custom",
         "name": "village",
         "url": "http://localhost:9876"
       }
     }
   }
   ```
3. Start Village ACP server: `village acp --server start`
4. Open Zed, use Assistant panel

### JetBrains IDEs

**Status:** ✅ Supported (via ACP plugin)

**Setup:**
1. Install ACP plugin for JetBrains
2. Configure plugin to connect to `localhost:9876`
3. Start Village ACP server: `village acp --server start`
4. Use AI assistant panel in IDE

### VS Code

**Status:** 🔄 Planned (community plugin needed)

**Setup:** Requires ACP extension development

### Other Editors

Any editor with ACP support can connect to Village. Check your editor's documentation for ACP integration.

---

## Supported External Agents

### Claude Code (Anthropic)

**Status:** ✅ Supported

**Configuration:**
```ini
[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal,web
```

**Usage:**
```bash
village acp --client spawn claude
```

### Gemini CLI (Google)

**Status:** ✅ Supported

**Configuration:**
```ini
[agent.gemini]
type = acp
acp_command = gemini-cli
acp_capabilities = filesystem,terminal
```

**Usage:**
```bash
village acp --client spawn gemini
```

### Custom ACP Agents

Any ACP-compliant agent can be integrated:

```ini
[agent.custom]
type = acp
acp_command = /path/to/your/agent
acp_capabilities = filesystem,terminal
```

---

## Comparison: Native vs ACP Agents

### Native Village Agents (OpenCode)

**Pros:**
- ✅ Tight integration with Village
- ✅ Direct access to Village APIs
- ✅ No protocol overhead
- ✅ Full control over execution

**Cons:**
- ❌ Limited to OpenCode
- ❌ No editor integration
- ❌ Custom tool integration requires code changes

**Best for:**
- Production workloads
- Maximum performance
- Deep Village integration

### ACP External Agents

**Pros:**
- ✅ Use any ACP-compliant agent
- ✅ Editor integration
- ✅ Standardized interface
- ✅ Ecosystem compatibility

**Cons:**
- ❌ Protocol overhead
- ❌ Limited to ACP capabilities
- ❌ Dependency on external agent

**Best for:**
- Editor-based workflows
- Multi-agent scenarios
- Specialized capabilities (Claude, Gemini)

---

## Hybrid Workflows

### Workflow 1: Editor + CLI

```
Morning: Start tasks from Zed
  ↓
[Editor] → Village ACP Server → Queue 3 tasks
  ↓
Afternoon: Monitor from CLI
  ↓
[CLI] village status --workers
  ↓
[CLI] village resume bd-a3f8
```

### Workflow 2: Mixed Agents

```
Backend tasks → OpenCode (native)
  ↓
[agent.build]
type = opencode
  ↓
Frontend tasks → Claude Code (ACP)
  ↓
[agent.frontend]
type = acp
acp_command = claude-code
  ↓
Research tasks → Gemini CLI (ACP)
  ↓
[agent.research]
type = acp
acp_command = gemini-cli
```

### Workflow 3: Real-Time Monitoring

```
Start ACP server
  ↓
village acp --server start
  ↓
Connect monitoring dashboard
  ↓
Dashboard → ACP → stream_notifications()
  ↓
Real-time task updates
```

---

## Security Considerations

### File System Access

- ✅ ACP agents can only access files in worktrees
- ✅ Path validation prevents directory traversal
- ✅ Atomic writes prevent corruption

### Terminal Access

- ✅ ACP agents can create terminals in Village session
- ✅ Terminal IDs are scoped to sessions
- ✅ Kill/release operations are session-scoped

### Permission Model

**Current:** Auto-approve (development mode)

**Planned:**
- Configurable permission policies
- Per-agent permission profiles
- Interactive approval prompts

---

## Performance

### Protocol Overhead

| Operation | Native | ACP | Overhead |
|-----------|--------|-----|----------|
| Session new | ~10ms | ~15ms | +50% |
| Prompt | ~100ms | ~120ms | +20% |
| File read | ~5ms | ~8ms | +60% |
| Notification | ~1ms | ~2ms | +100% |

**Recommendation:** Use native agents for high-frequency operations.

### Scalability

- **Server mode:** Supports multiple editor connections
- **Client mode:** Spawns agents on-demand
- **Bridge:** Stateless, horizontally scalable

---

## Limitations

### Current Limitations

1. **No daemon mode** - ACP server runs in foreground
2. **Auto-approve permissions** - No interactive approval yet
3. **No session forking** - ACP fork not implemented
4. **Limited model selection** - Uses agent's default model

### Planned Improvements

1. **Daemon mode** - Background ACP server with PID file
2. **Permission policies** - Configurable approval workflows
3. **Session forking** - Clone task state
4. **Model selection** - Override agent models

---

## Getting Started

### Quick Start: Server Mode

```bash
# 1. Enable ACP in config
cat >> .village/config <<EOF
[acp]
enabled = true
host = localhost
port = 9876
EOF

# 2. Start ACP server
village acp --server start

# 3. Configure your editor to connect to localhost:9876
```

### Quick Start: Client Mode

```bash
# 1. Define an ACP agent
cat >> .village/config <<EOF
[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal
EOF

# 2. List available agents
village acp --client list

# 3. Spawn an agent
village acp --client spawn claude
```

---

## Next Steps

- **[Configuration Guide](ACP_CONFIGURATION.md)** - Detailed config reference
- **[Examples](ACP_EXAMPLES.md)** - Real-world usage examples
- **[API Reference](ACP_API_REFERENCE.md)** - Complete API documentation

---

## Troubleshooting

### "ACP server is disabled"

**Fix:** Enable ACP in config:
```ini
[acp]
enabled = true
```

### "Agent not found"

**Fix:** Check agent configuration:
```bash
village acp --client list
cat .village/config
```

### "Connection refused"

**Fix:** Ensure server is running:
```bash
village acp --server status
village acp --server start
```

### "Permission denied"

**Fix:** Check agent command is executable:
```bash
which claude-code
chmod +x /path/to/agent
```

---

## References

- **ACP Specification**: https://agent-client-protocol.dev
- **Official SDK**: `pip install agent-client-protocol`
- **Village ACP Code**: `village/acp/`
- **Task Breakdown**: [docs/ACP_INTEGRATION_TASKS.md](ACP_INTEGRATION_TASKS.md)
