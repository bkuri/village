# Chat Transport Abstraction

Status: incomplete

## Problem

Village's interactive chat (greeter) only works in a local terminal via
`click.prompt`. Users cannot interact with Village from other interfaces like
Telegram. The old `village chat` command had no transport abstraction either --
it was hardcoded to CLI.

A transport layer would allow the same chat logic to work across multiple
interfaces: CLI, Telegram, and future transports (Discord, Slack, etc.).

## Solution

Extract message I/O into an async `Transport` abstraction. The greeter loop
becomes transport-agnostic: it calls `transport.receive()` for input and
`transport.send()` for output, regardless of whether the transport is CLI or
Telegram.

For Telegram persistence, leverage Telegram's native message history instead of
storing session state locally. A single pinned message in DMs tracks session
state using a simple key-value format. Milestone compaction keeps context
manageable.

## Transport Interface

All transports implement the same async interface:

```python
class AsyncTransport(ABC):
    @abstractmethod
    async def start(self) -> None:
        """Initialize transport (connect, start polling, etc.)."""

    @abstractmethod
    async def stop(self) -> None:
        """Shutdown transport cleanly."""

    @abstractmethod
    async def send(self, message: str) -> None:
        """Send message to user."""

    @abstractmethod
    async def receive(self) -> str:
        """Block until user sends a message. Return text content."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Transport identifier (e.g. 'cli', 'telegram')."""
```

## Transport Implementations

### CLI Transport

Wraps existing `click.prompt` behavior in async interface.

- `start()`: Print welcome banner
- `receive()`: Read from stdin via `asyncio.get_event_loop().run_in_executor(None, ...)`
- `send()`: Write to stdout via `click.echo()`
- `stop()`: Print exit message

No new behavior. Existing greeter works identically.

### Telegram Transport

Uses `python-telegram-bot` library with long polling.

- `start()`: Validate bot token, start polling, find or create pinned state message
- `receive()`: Await next message from polling queue
- `send()`: Send message via Bot API (MarkdownV2 formatted)
- `stop()`: Stop polling gracefully

The transport receives a `summarize_fn: Callable[[str], Awaitable[str]]`
callback for milestone compaction. It does NOT create its own LLM client.
The greeter passes its existing LLM summarize function.

```python
class TelegramTransport(AsyncTransport):
    def __init__(
        self,
        config: TelegramConfig,
        summarize_fn: Callable[[str], Awaitable[str]] | None = None,
    ): ...
```

DMs only. No group support.

## Telegram Persistence Model

### Source of Truth

Telegram message history IS the conversation history. No local session state
file.

On startup and after each milestone compaction:

1. Find pinned message from bot starting with `[VILLAGE SESSION]`
2. Parse state from pinned message body
3. Count messages after pinned message to set counter
4. Resume from there

### Pinned Message Format

Simple key-value. Human-readable, editable in Telegram.

The transport does not track Village task internals. Task context is
captured in the milestone summary, keeping the transport a dumb pipe.

```
[VILLAGE SESSION]
Counter: 42/50

Milestone:
Added Redis caching to user service.
Next step: auth token refresh.
```

### Parsing Rules

| Field | Pattern | Fallback |
|-------|---------|----------|
| Counter | `Counter: (\d+)/(\d+)` | `0/50` |
| Milestone | Text after `Milestone:\n` to end of message | `Session started.` |

### State Machine

```
NEW ──► No pinned message exists
 │        Create pinned message with counter=0, milestone="Session started."
 │
ACTIVE ──► Pinned message exists, counter < interval
 │          Increment counter on each user message
 │          Context = [milestone] + [messages since pinned]
 │
MILESTONE ──► counter >= interval
 │             1. Read all messages since pinned
 │             2. Generate summary via LLM
 │             3. Edit pinned message: new milestone, counter=0
 │             4. Context refreshes from new pinned message
 │
RECOVER ──► Bot restarts
             1. Find pinned message via bot history
             2. Parse state, count messages after it
             3. Resume counter from actual count
             4. If parsing fails: treat as NEW session
```

### Milestone Compaction

Triggered when `counter >= interval` (default: 50).

1. Collect all messages since pinned message
2. Format as conversation: "User: ...\nAssistant: ..."
3. Call `summarize_fn(conversation_text)` — callback provided by greeter
4. If no `summarize_fn` provided, use last user message as milestone
5. Edit pinned message with new milestone summary
6. Counter resets to 0

The greeter provides the summarize callback using its existing LLM client:

```python
async def summarize(text: str) -> str:
    return await llm_chat.handle_message(
        f"Summarize this conversation in 2-3 sentences. "
        f"Preserve: active goals, recent decisions, next steps.\n\n{text}"
    )

transport = TelegramTransport(config.telegram, summarize_fn=summarize)
```

### Context Building

For each LLM call, context is assembled from:

1. Pinned message (milestone + tasks)
2. Last N messages from Telegram history (default: 10)
3. Current user message

```
[System: You are Village, a development assistant]
[Milestone: Added Redis caching...]
[History: User: X, Assistant: Y, ...]
[User: current message]
```

## Configuration

### Config Section

```ini
[telegram]
bot_token_env = VILLAGE_TELEGRAM_BOT_TOKEN
milestone_interval = 50
max_context_messages = 10
```

### Config Dataclass

```python
@dataclass
class TelegramConfig:
    bot_token_env: str = "VILLAGE_TELEGRAM_BOT_TOKEN"
    milestone_interval: int = 50
    max_context_messages: int = 10
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `VILLAGE_TELEGRAM_BOT_TOKEN` | Yes (telegram transport) | Bot token from @BotFather |

## CLI Changes

### Greeter Command

```bash
village greeter                           # CLI transport (default)
village greeter --transport cli           # Explicit CLI
village greeter --transport telegram      # Telegram transport
village chat --transport telegram         # Same (chat is alias for greeter)
```

### Flag

```python
@click.option(
    "--transport",
    type=click.Choice(["cli", "telegram"]),
    default="cli",
    help="Chat transport interface",
)
```

## Role Routing

The current CLI greeter detects cross-role routing (`run_role_chat()`) and
can hand off to another role interactively. Telegram cannot spawn CLI
subprocesses for role handoff.

**Telegram behavior**: Routing suggestions are shown as text messages.

```
Bot: That sounds like a job for the planner.
     Run `village planner` to get started.
```

The greeter detects `RoutingAction.ROUTE` and `RoutingAction.ADVISE`
as before, but the transport determines how to present it:
- **CLI**: Runs `run_role_chat()` directly (existing behavior)
- **Telegram**: Sends suggestion as text message

The transport interface gains an optional method:

```python
class AsyncTransport(ABC):
    # ... existing methods ...

    async def route(self, target_role: str, context: str | None = None) -> None:
        """Handle cross-role routing. Default: send as text message."""
        msg = f"Routing to {target_role}."
        if context:
            msg += f"\nContext: {context}"
        await self.send(msg)
```

CLI transport overrides this to run `run_role_chat()` directly.

## Error Handling

| Scenario | CLI Transport | Telegram Transport |
|----------|---------------|-------------------|
| Invalid bot token | N/A | Raise `ClickException` at startup |
| Network drop | N/A | Auto-reconnect (built into `python-telegram-bot`) |
| Rate limit (Telegram API) | N/A | Built-in retry with exponential backoff |
| Rate limit (LLM API) | Surface error text | Surface error text via `send()` |
| LLM call failure | Print error, continue | Send error message, continue |
| Pinned message parse failure | N/A | Create new session (log warning) |
| User sends non-text (photo, sticker) | N/A | Send "Text only, please." response |
| `/exit` command | Break loop, exit | Break loop, stop polling, unpin message |

### Error Surface Pattern

All errors are surfaced to the user as plain text messages, not exceptions:

```python
try:
    response = await llm_chat.handle_message(user_input)
    await transport.send(response)
except Exception as e:
    await transport.send(f"Error: {e}")
    logger.error(f"Chat error: {e}")
    continue  # Never crash the loop
```

## Architecture

```
village/chat/transports/
├── __init__.py       # AsyncTransport ABC + create_transport() factory
├── cli.py            # CLITransport
└── telegram.py       # TelegramTransport + TelegramStateManager

village/config.py               # + TelegramConfig dataclass
village/cli/greeter.py          # Refactored to use transport
```

### Factory

```python
def create_transport(name: str, config: Config) -> AsyncTransport:
    if name == "cli":
        return CLITransport()
    elif name == "telegram":
        return TelegramTransport(config.telegram)
    raise ValueError(f"Unknown transport: {name}")
```

### Greeter Refactor

**Behavioral change**: The current greeter calls `asyncio.run()` per message.
The refactored greeter becomes a single async entry point, calling
`asyncio.run()` once at the top level.

Current greeter loop:

```python
while True:
    user_input = click.prompt("", prompt_suffix="> ")  # CLI-specific
    response = asyncio.run(llm_chat.handle_message(user_input))
    click.echo("\n" + response + "\n")  # CLI-specific
```

Refactored:

```python
transport = create_transport(transport_name, config)
await transport.start()
try:
    while True:
        user_input = await transport.receive()
        if should_exit(user_input):
            break
        response = await llm_chat.handle_message(user_input)
        await transport.send(response)
finally:
    await transport.stop()
```

The click command handler becomes:

```python
asyncio.run(run_greeter(config, transport_name))
```

Extensions and MCP servers initialize inside the async context
(no separate `asyncio.run()` for setup):

```python
async def run_greeter(config, transport_name):
    extensions, discovered_servers = await _initialize_extensions_and_mcp(config)
    await llm_chat.set_extensions(extensions)
    # ... transport loop
```

## Acceptance Criteria

1. `village greeter` works identically to current behavior (CLI transport)
2. `village greeter --transport cli` is explicit equivalent of default
3. `village greeter --transport telegram` starts Telegram long polling
4. Bot responds to DMs with LLM-generated responses
5. First message creates pinned `[VILLAGE SESSION]` message in DM
6. Pinned message tracks counter and milestone
7. Milestone compaction triggers at configured interval
8. Bot restarts recover state from pinned message (no data loss)
9. Context for LLM is milestone + last N messages + current message
10. `/exit` command stops the bot gracefully
11. Parsing handles edge cases: emojis, long messages, edited pinned messages
12. Failed parse of pinned message creates new session (no crash)

## Testing

### Unit Tests

| Test File | Tests |
|-----------|-------|
| `tests/test_transports/test_cli.py` | CLITransport send/receive with mock stdin/stdout |
| `tests/test_transports/test_telegram.py` | TelegramTransport with mocked Bot API |
| `tests/test_transports/test_state.py` | Pinned message parsing (valid, malformed, empty, emoji, long) |
| `tests/test_transports/test_factory.py` | `create_transport()` for each name + unknown raises ValueError |

### Key Test Cases

**Pinned message parsing** (most critical):
- Valid format parses correctly
- Missing `Counter:` line defaults to `0/50`
- Missing `Milestone:` section defaults to `"Session started."`
- Emoji in milestone text does not break parsing
- Very long milestone text (1000+ chars) parses correctly
- Empty message body creates new session
- Random non-Village pinned message creates new session
- Edited pinned message with slight formatting drift still parses

**Milestone compaction**:
- Counter increments on each user message
- Compaction triggers at interval boundary
- Compaction resets counter to 0
- Compaction edits pinned message with new summary
- No `summarize_fn` falls back to last user message

**Transport lifecycle**:
- `start()` then `stop()` completes cleanly
- `send()` after `stop()` raises or no-ops
- `receive()` can be cancelled via `stop()`

### Integration Test

- Greeter with `MockTransport` (in-memory send/receive) processes messages end-to-end

## Out of Scope

- Group chat support
- Multiple concurrent users (one DM session per bot)
- Message formatting beyond basic MarkdownV2
- Images, files, voice messages
- Discord, Slack transports
- Webhook mode (long polling only)
- Telegram inline keyboards / menus

## Dependencies

- `python-telegram-bot` (new, add to pyproject.toml)
- Existing LLM infrastructure (`village.chat.llm_chat.LLMChat`)
- Existing config system (`village.config`)

## Files to Create

```
village/chat/transports/__init__.py    # AsyncTransport ABC + factory (~40 lines)
village/chat/transports/cli.py         # CLITransport (~30 lines)
village/chat/transports/telegram.py    # TelegramTransport + StateManager (~200 lines)
```

## Files to Modify

```
village/config.py                      # + TelegramConfig dataclass (~20 lines)
village/cli/greeter.py                 # Refactored to use transport (~60 lines)
pyproject.toml                         # + python-telegram-bot dependency
```

## Future Extensions

- `--transport discord` via Discord.py
- `--transport slack` via Slack Bolt
- Group chat with `/village` command prefix
- Inline keyboards for task actions
- File/photo support for code snippets
- Multi-user with per-chat session isolation
- Webhook mode for production deployments
