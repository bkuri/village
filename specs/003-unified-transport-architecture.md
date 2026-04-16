# Unified Transport Architecture

Status: incomplete

## Problem

Village commands are hardcoded to CLI interaction via `click.prompt()` and
`click.confirm()`. This means:

1. **Agents cannot use Village interactively.** An agent cannot run
   `village greeter` or `village new` and answer follow-up questions because
   those questions go to stdin, not to the agent.

2. **Transports are command-specific.** The current transport abstraction
   (spec 002) only wraps the greeter loop. Other commands with prompts
   (planner, lifecycle, watcher, baseline) are not transport-aware.

3. **No interchangeability.** A human using Telegram and an agent using ACP
   cannot access the same commands through the same interface. Each transport
   would need custom integration per command.

## Solution

Create a **PromptResolver** that intercepts all interactive prompts and routes
them through the active transport. Any Village command (greeter, new, planner,
etc.) becomes transport-agnostic without per-command customization.

Transports are interchangeable: CLI, Telegram, ACP, or future transports
all use the same interface. An agent using ACP can go through the exact same
onboarding interview as a human using CLI.

```
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│   CLI    │  │ Telegram  │  │   ACP    │  │  Stdio   │
│ (human)  │  │ (human)  │  │ (agent)  │  │ (agent)  │
└────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
     │             │             │             │
     └─────────────┴─────────────┴─────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   AsyncTransport    │
              │  send/receive/route │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  PromptResolver     │
              │  intercepts prompts │
              └──────────┬──────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │  Village Commands   │
              │  greeter, new, etc. │
              └─────────────────────┘
```

## Transport Interface

All transports implement the same async interface (already exists from spec 002):

```python
class AsyncTransport(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def send(self, message: str) -> None: ...

    @abstractmethod
    async def receive(self) -> str: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def capabilities(self) -> TransportCapabilities: ...

    async def route(self, target_role: str, context: str | None = None) -> None: ...
```

### Transport Capabilities

Not all transports support all features. Commands check capabilities and
degrade gracefully.

```python
@dataclass(frozen=True)
class TransportCapabilities:
    streaming: bool = False
    files: bool = False
    terminal: bool = False
    markdown: bool = False
    menus: bool = False
    persistence: bool = False
```

| Capability  | CLI | Telegram | ACP | Stdio |
|-------------|-----|----------|-----|-------|
| streaming   | ✓   | ✗        | ✓   | ✓     |
| files       | ✓   | ✗        | ✓   | ✓     |
| terminal    | ✓   | ✗        | ✓   | ✗     |
| markdown    | ✗   | ✓        | ✗   | ✗     |
| menus       | ✗   | ✓        | ✗   | ✗     |
| persistence | ✗   | ✓        | ✓   | ✗     |

## PromptResolver

The key architectural component. A module-level singleton that intercepts
interactive prompts and routes them through the active transport.

### Interface

```python
class PromptResolver:
    def __init__(self) -> None:
        self._transport: AsyncTransport | None = None

    def set_transport(self, transport: AsyncTransport) -> None:
        self._transport = transport

    def clear_transport(self) -> None:
        self._transport = None

    async def prompt(
        self,
        text: str = "",
        default: str = "",
        show_default: bool = True,
        type: type | None = None,
    ) -> str:
        if self._transport:
            display = text
            if show_default and default:
                display += f" [{default}]"
            await self._transport.send(display)
            response = await self._transport.receive()
            if not response and default:
                return default
            if type is int:
                return str(int(response))
            return response
        # No transport — fall back to click.prompt (normal CLI)
        return click.prompt(text, default=default, show_default=show_default)

    async def confirm(
        self,
        text: str,
        default: bool = True,
    ) -> bool:
        if self._transport:
            suffix = " [Y/n]" if default else " [y/N]"
            await self._transport.send(text + suffix)
            response = (await self._transport.receive()).strip().lower()
            if not response:
                return default
            return response in ("y", "yes")
        return click.confirm(text, default=default)
```

### Module-Level Singleton

```python
# village/prompt.py

_resolver = PromptResolver()

def get_resolver() -> PromptResolver:
    return _resolver

def set_transport(transport: AsyncTransport) -> None:
    _resolver.set_transport(transport)

def clear_transport() -> None:
    _resolver.clear_transport()
```

### Migration Strategy

Incremental migration of `click.prompt` calls to `resolver.prompt()`:

**Phase 1 — Core commands** (13 click.prompt + 2 click.confirm):
| File | Calls | Priority |
|------|-------|----------|
| `cli/greeter.py` | 0 (already transport-aware) | Done |
| `cli/lifecycle.py` | 1 prompt | P1 |
| `roles.py` | 2 prompts | P1 |
| `chat/baseline.py` | 4 prompts | P1 |
| `cli/planner.py` | 4 prompts | P2 |
| `cli/watcher.py` | 1 prompt | P2 |
| `onboard/interview.py` | 1 confirm | P2 |
| `cli/builder.py` | 1 confirm | P3 |

**Phase 2 — Full migration**: Replace all remaining direct `click.prompt`
calls with `resolver.prompt()`.

No behavioral change for CLI — when no transport is set, resolver falls back
to `click.prompt` directly.

## Command Dispatch

The transport layer needs a command dispatcher for non-greeter commands.

### How It Works

1. User/agent sends a message to the transport
2. Transport passes message to command dispatcher
3. Dispatcher parses command name and arguments
4. Dispatcher invokes the Click command programmatically
5. Command prompts go through PromptResolver → transport
6. Command output goes through transport.send()

### Command Registry

```python
@dataclass
class CommandEntry:
    name: str
    description: str
    handler: Callable[..., Awaitable[None]]
    interactive: bool = True

COMMAND_REGISTRY: dict[str, CommandEntry] = {
    "greeter": CommandEntry(
        name="greeter",
        description="Interactive Q&A session",
        handler=run_greeter,
    ),
    "new": CommandEntry(
        name="new",
        description="Create new project with interview",
        handler=run_new,
    ),
    "planner design": CommandEntry(
        name="planner design",
        description="Design a workflow",
        handler=run_planner_design,
    ),
    "tasks list": CommandEntry(
        name="tasks list",
        description="List tasks",
        handler=run_tasks_list,
        interactive=False,
    ),
    "tasks ready": CommandEntry(
        name="tasks ready",
        description="Show ready tasks",
        handler=run_tasks_ready,
        interactive=False,
    ),
    # ... more commands
}
```

### Dispatcher Flow

```python
async def dispatch(transport: AsyncTransport, message: str, config: Config) -> None:
    parts = message.strip().split()
    cmd_name = parts[0] if parts else ""

    # Check for slash commands (Telegram style)
    if cmd_name.startswith("/"):
        cmd_name = cmd_name[1:]

    # Find command
    entry = COMMAND_REGISTRY.get(cmd_name)
    if not entry:
        # Try greeter as fallback (natural language)
        entry = COMMAND_REGISTRY["greeter"]
        await entry.handler(transport, message, config)
        return

    # Set transport as active for prompt routing
    set_transport(transport)
    try:
        args = " ".join(parts[1:])
        await entry.handler(transport, args, config)
    finally:
        clear_transport()
```

### Telegram Command Mapping

Telegram users interact via slash commands and natural language:

| Input | Dispatches To |
|-------|--------------|
| `/start` | Start session, show help |
| `/help` | List available commands |
| `/tasks` | `tasks list` |
| `/tasks ready` | `tasks ready` |
| `/planner design <goal>` | `planner design` with goal |
| `/new <name>` | `village new` with name |
| Any other text | `greeter` (natural language) |

### ACP Agent Interaction

ACP agents interact via structured method calls:

```json
{"method": "session/prompt", "params": {"message": "/tasks ready"}}
{"method": "session/prompt", "params": {"message": "I want to create a new project"}}
```

Both route through the same dispatcher.

## Transport Implementations

### CLI Transport (existing, updated)

- `capabilities()`: streaming=True, files=True, terminal=True
- `receive()`: wraps `click.prompt` via executor (existing)
- `send()`: writes to stdout (existing)
- No command dispatch needed (Click handles it directly)

### Telegram Transport (existing, updated)

- `capabilities()`: markdown=True, menus=True, persistence=True
- Add command dispatch loop:
  1. `/start` → welcome + help
  2. Slash commands → dispatch to handler
  3. Plain text → dispatch to greeter
- Pinned message state management (existing from spec 002)
- Milestone compaction (existing from spec 002)

### ACP Transport (new)

- `capabilities()`: streaming=True, files=True, terminal=True, persistence=True
- Uses existing ACP session model
- `start()`: connect to ACP server or start one
- `receive()`: await next message from ACP session
- `send()`: send via ACP session
- Session maps to transport session (session_id = chat context)

### Stdio Transport (new)

For agents that spawn Village as a subprocess:

- `capabilities()`: streaming=True, files=True
- `start()`: no-op (stdin/stdout already connected)
- `receive()`: read JSON line from stdin
- `send()`: write JSON line to stdout
- Protocol:

```json
{"type": "prompt", "text": "Project name?"}
{"type": "response", "text": "my-project"}
{"type": "output", "text": "Created project my-project"}
```

## Telegram Session Flow (Example)

```
User: /start
Bot: Welcome to Village! Commands: /tasks, /planner, /new, /greeter
     Or just type naturally and I'll figure it out.

User: /tasks ready
Bot: 📋 Ready tasks:
     - village-abc: Add user auth (P1)
     - village-def: Fix login bug (P0)

User: I want to create a new project called "myapp"
Bot: [dispatches to greeter → planner → new]
Bot: What framework are you using?
User: FastAPI
Bot: Any database requirements?
User: PostgreSQL
Bot: ✅ Created project "myapp" with FastAPI + PostgreSQL
```

## ACP Agent Session Flow (Example)

```
Agent: {"method": "session/new", "params": {"cwd": "/tmp"}}
ACP:  {"sessionId": "sess-123"}

Agent: {"method": "session/prompt", "params": {"sessionId": "sess-123", "message": "/new myapp"}}
ACP:  {"prompt": "What framework are you using?"}

Agent: {"method": "session/prompt", "params": {"sessionId": "sess-123", "message": "FastAPI"}}
ACP:  {"prompt": "Any database requirements?"}

Agent: {"method": "session/prompt", "params": {"sessionId": "sess-123", "message": "PostgreSQL"}}
ACP:  {"output": "Created project myapp with FastAPI + PostgreSQL"}
```

## CLI Entry Point

New unified entry point for transport-based interaction:

```bash
# Existing CLI (unchanged, direct Click commands)
village greeter
village new myapp
village tasks list

# Transport mode (routes all commands through transport layer)
village greeter --transport telegram
village greeter --transport acp
village greeter --transport stdio

# Future: dedicated transport command
village transport telegram    # Full interactive session via Telegram
village transport acp         # Full interactive session via ACP
```

## Acceptance Criteria

1. `village greeter --transport telegram` works (already done in spec 002)
2. `village greeter --transport acp` starts ACP session for agent interaction
3. PromptResolver intercepts `click.prompt` and routes through active transport
4. When no transport is set, PromptResolver falls back to `click.prompt` (zero behavioral change)
5. Telegram transport supports slash commands (`/tasks`, `/planner`, etc.)
6. Telegram transport falls back to greeter for unrecognized messages
7. ACP transport supports full command dispatch
8. `village new` works via Telegram (answers prompts through transport)
9. `village planner design` works via ACP (agent answers prompts)
10. All 13 `click.prompt` calls migrated to `resolver.prompt()`
11. Both `click.confirm` calls migrated to `resolver.confirm()`
12. Transport capabilities correctly declared and checked
13. Session state persists across Telegram restarts (existing from spec 002)
14. Agent can complete full onboarding interview via ACP

## Out of Scope

- WebSocket transport (future)
- IRC/Slack/Discord transports (future)
- Voice/video messages
- Multi-user concurrent sessions per transport
- Transport-level authentication/authorization
- Streaming output (partial responses)
- File upload/download through transports

## Implementation Order

| Step | Description | Depends On |
|------|-------------|------------|
| 1 | Create `village/prompt.py` with PromptResolver | — |
| 2 | Add `TransportCapabilities` to AsyncTransport | — |
| 3 | Update CLITransport and TelegramTransport with capabilities | Step 2 |
| 4 | Migrate `cli/lifecycle.py` prompts to resolver | Step 1 |
| 5 | Migrate `roles.py` prompts to resolver | Step 1 |
| 6 | Migrate `chat/baseline.py` prompts to resolver | Step 1 |
| 7 | Add command registry and dispatcher | Step 1 |
| 8 | Update Telegram transport with command dispatch | Steps 3, 7 |
| 9 | Create ACP transport | Steps 2, 7 |
| 10 | Migrate remaining prompts (planner, watcher, builder) | Step 1 |
| 11 | Create stdio transport | Steps 2, 7 |
| 12 | Integration tests | All above |

## Files to Create

```
village/prompt.py                    # PromptResolver singleton (~80 lines)
village/chat/transports/acp.py       # ACP transport (~150 lines)
village/chat/transports/stdio.py     # Stdio transport (~60 lines)
village/dispatch.py                  # Command registry + dispatcher (~120 lines)
tests/test_prompt.py                 # PromptResolver tests
tests/test_dispatch.py               # Dispatcher tests
tests/test_transports/test_acp.py    # ACP transport tests
tests/test_transports/test_stdio.py  # Stdio transport tests
```

## Files to Modify

```
village/chat/transports/__init__.py  # Add capabilities, ACP/stdio to factory
village/chat/transports/cli.py       # Add capabilities
village/chat/transports/telegram.py  # Add capabilities, command dispatch
village/cli/lifecycle.py             # Migrate prompts (1 call)
village/roles.py                     # Migrate prompts (2 calls)
village/chat/baseline.py            # Migrate prompts (4 calls)
village/cli/planner.py              # Migrate prompts (4 calls)
village/cli/watcher.py              # Migrate prompts (1 call)
village/onboard/interview.py        # Migrate confirm (1 call)
village/cli/builder.py              # Migrate confirm (1 call)
```

## Dependencies

- Existing ACP SDK (`agent-client-protocol`)
- Existing `python-telegram-bot`
- No new external dependencies
