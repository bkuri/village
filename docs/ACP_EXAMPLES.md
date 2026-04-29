# ACP Integration Examples

Practical examples of using ACP integration with Village.

---

## Table of Contents

1. [Example 1: Using Village from Zed Editor](#example-1-using-village-from-zed-editor)
2. [Example 2: Using Village from JetBrains IDE](#example-2-using-village-from-jetbrains-ide)
3. [Example 3: Spawning Claude Code](#example-3-spawning-claude-code)
4. [Example 4: Spawning Gemini CLI](#example-4-spawning-gemini-cli)
5. [Example 5: Mixed Workflow (Native + ACP)](#example-5-mixed-workflow-native--acp)
6. [Example 6: Real-Time Monitoring](#example-6-real-time-monitoring)
7. [Example 7: Custom ACP Agent](#example-7-custom-acp-agent)

---

## Example 1: Using Village from Zed Editor

**Goal:** Start and monitor Village tasks from Zed editor.

### Prerequisites

- Zed editor 0.120+ installed
- Village configured with ACP enabled
- village tasks ready

### Step 1: Configure Village ACP Server

```bash
# Create .village/config
cat > .village/config <<EOF
[acp]
enabled = true
host = localhost
port = 9876

[DEFAULT]
DEFAULT_AGENT = worker
EOF

# Initialize Village
village up
```

### Step 2: Start ACP Server

```bash
# Start server in foreground
village acp --server start
```

**Output:**
```
Starting ACP server on localhost:9876
ACP server running...
```

### Step 3: Configure Zed

Open Zed settings (`Cmd+,` on macOS, `Ctrl+,` on Linux):

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

### Step 4: Use Village in Zed

1. Open Zed
2. Open Assistant panel (`Cmd+Shift+A` on macOS)
3. Select "village" as the assistant
4. Start a conversation:

```
You: Start task bd-a3f8
Village: ✓ Task bd-a3f8 started
         Agent: worker
         Worktree: .worktrees/bd-a3f8
         Window: worker-1-bd-a3f8

You: Show status
Village: Active workers: 1
         - bd-a3f8: ACTIVE (worker)
```

### Step 5: Stream Notifications

Real-time updates appear in the chat:

```
[Notification] Task bd-a3f8 state changed: QUEUED → IN_PROGRESS
[Notification] File modified: src/main.py
[Notification] Task bd-a3f8 state changed: IN_PROGRESS → COMPLETED
```

### Full Workflow

```bash
# Terminal 1: Start Village server
village up
village acp --server start

# Terminal 2: Create tasks
village tasks create "Implement user auth"
village tasks create "Add API endpoints"

# Zed: Use assistant panel to queue and monitor
```

### CLI Equivalent

```bash
# Same workflow via CLI
village queue --n 2
village status --workers
village builder resume --task bd-a3f8
```

---

## Example 2: Using Village from JetBrains IDE

**Goal:** Use Village from IntelliJ IDEA / PyCharm / WebStorm.

### Prerequisites

- JetBrains IDE (IntelliJ IDEA, PyCharm, WebStorm, etc.)
- ACP plugin for JetBrains installed
- Village configured with ACP enabled

### Step 1: Install ACP Plugin

1. Open JetBrains IDE
2. Go to `Settings/Preferences` → `Plugins`
3. Search for "Agent Client Protocol"
4. Install and restart IDE

### Step 2: Configure Village

```bash
# .village/config
cat > .village/config <<EOF
[acp]
enabled = true
host = localhost
port = 9876
capability_filesystem = Read/write worktree files
capability_terminal = Execute terminal commands
capability_notifications = Stream task updates

[agent.worker]
type = opencode
opencode_args = --mode patch
EOF
```

### Step 3: Start ACP Server

```bash
village up
village acp --server start
```

### Step 4: Configure JetBrains Plugin

1. Open `Settings/Preferences` → `Tools` → `Agent Client Protocol`
2. Add new agent:
   - **Name:** Village
   - **URL:** `http://localhost:9876`
   - **Protocol Version:** 1
3. Click "Test Connection"
4. Save settings

### Step 5: Use Village in IDE

1. Open AI Assistant panel (usually right sidebar)
2. Select "Village" from dropdown
3. Interact with Village:

```
You: Queue 3 tasks
Village: Starting 3 task(s)...
         
         Tasks started: 3
         Tasks failed: 0
         
         - bd-a3f8: ACTIVE (worker)
         - bd-b7c2: ACTIVE (worker)
         - bd-d9e4: ACTIVE (worker)

You: Read file src/main.py from task bd-a3f8
Village: File content:
         ```python
         # src/main.py
         def main():
             print("Hello, Village!")
         ```
```

### Step 6: Terminal Operations

Execute commands in task worktrees:

```
You: Run tests in task bd-a3f8
Village: Creating terminal in task bd-a3f8...
         Terminal ID: term-a1b2c3
         Executing: pytest tests/
         
         Output:
         ======== test session starts ========
         collected 10 items
         
         test_main.py ...           [100%]
         
         ======== 10 passed in 2.34s ========
```

### Full Workflow

```bash
# Terminal: Start Village
village acp --server start

# JetBrains: 
# - Open project
# - Use AI assistant to queue tasks
# - Monitor progress in real-time
# - Read/write files in worktrees
# - Execute terminal commands
```

---

## Example 3: Spawning Claude Code

**Goal:** Use Claude Code as an external ACP agent orchestrated by Village.

### Prerequisites

- Claude Code installed (`npm install -g @anthropic/claude-code`)
- Anthropic API key configured

### Step 1: Configure Claude Agent

```bash
# .village/config
cat >> .village/config <<EOF

[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal,web
EOF
```

### Step 2: Verify Configuration

```bash
# List ACP agents
village acp --client list
```

**Output:**
```
Configured ACP Agents (1):

  claude:
    Command: claude-code
    Capabilities: filesystem, terminal, web
```

### Step 3: Test Connection

```bash
# Test Claude Code agent
village acp --client test claude
```

**Output:**
```
Testing ACP agent: claude...
✓ Agent test successful
```

### Step 4: Spawn Claude Code

```bash
# Spawn agent interactively
village acp --client spawn claude
```

**Output:**
```
Spawning ACP agent: claude
  Command: claude-code

✓ Agent spawned successfully
  Connection: AgentConnection
  Process: subprocess.Popen

Note: Agent is running. Use the connection object to interact.
```

### Step 5: Use Claude in Workflow

```bash
# Create task for Claude
village tasks create "Research best practices for REST API design" --label research

# Assign to Claude agent
village builder resume --task bd-research --agent claude
```

**What happens:**
1. Village creates worktree for `bd-research`
2. Spawns Claude Code in tmux pane
3. Claude has access to worktree filesystem
4. Claude can execute terminal commands
5. Village tracks task state

### Step 6: Monitor Progress

```bash
# Check status
village status --workers
```

**Output:**
```
TASK_ID      STATUS    PANE     AGENT    WINDOW
bd-research  ACTIVE    %15      claude   claude-1-bd-research
```

### Full Workflow with Multiple Agents

```bash
# Configure multiple agents
cat >> .village/config <<EOF

[agent.worker]
type = opencode
opencode_args = --mode patch

[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal,web

[agent.gemini]
type = acp
acp_command = gemini-cli
acp_capabilities = filesystem,terminal
EOF

# Queue tasks with different agents
village builder queue --n 3 --agent worker    # OpenCode tasks
village builder resume --task bd-research --agent claude  # Claude task
village builder resume --task bd-analysis --agent gemini  # Gemini task
```

---

## Example 4: Spawning Gemini CLI

**Goal:** Use Gemini CLI as an external ACP agent.

### Prerequisites

- Gemini CLI installed
- Google API key configured

### Step 1: Install Gemini CLI

```bash
# Install Gemini CLI
npm install -g @google/gemini-cli

# Configure API key
export GOOGLE_API_KEY=your-api-key-here
```

### Step 2: Configure Gemini Agent

```bash
# .village/config
cat >> .village/config <<EOF

[agent.gemini]
type = acp
acp_command = GOOGLE_API_KEY=$GOOGLE_API_KEY gemini-cli
acp_capabilities = filesystem,terminal
EOF
```

### Step 3: Verify and Test

```bash
# List agents
village acp --client list

# Test connection
village acp --client test gemini
```

**Output:**
```
Testing ACP agent: gemini...
✓ Agent test successful
```

### Step 4: Use Gemini for Research

```bash
# Create research task
village tasks create "Analyze competitor pricing strategies" --label research

# Assign to Gemini
village builder resume --task bd-competitor-analysis --agent gemini
```

### Step 5: Monitor and Interact

```bash
# Attach to Gemini task
village builder resume --task bd-competitor-analysis

# Inside tmux pane, interact with Gemini
> Analyze the pricing data in data/pricing.csv
> Generate a summary report
> Save findings to reports/pricing-analysis.md
```

### Example Output

```
Gemini: I'll analyze the pricing data...

1. Reading data/pricing.csv (1,234 rows)
2. Computing statistics...
   - Average price: $49.99
   - Median price: $45.00
   - Price range: $19.99 - $99.99

3. Generating visualizations...
   - Price distribution chart saved to reports/price-dist.png
   - Competitor comparison saved to reports/competitor-comp.png

4. Summary report saved to reports/pricing-analysis.md

Analysis complete! Key findings:
- Our pricing is 15% below market average
- Premium tier has highest margins
- Competitor X offers similar features at 20% higher price
```

---

## Example 5: Mixed Workflow (Native + ACP)

**Goal:** Use both OpenCode (native) and ACP agents together.

### Scenario

- **Backend tasks** → OpenCode (fast, integrated)
- **Frontend tasks** → Claude Code (specialized UI knowledge)
- **Research tasks** → Gemini CLI (broad knowledge)

### Configuration

```ini
# .village/config
[DEFAULT]
DEFAULT_AGENT = worker
MAX_WORKERS = 6

[acp]
enabled = true

# Native agent for backend
[agent.backend]
type = opencode
opencode_args = --mode build
contract = contracts/backend.md

# ACP agent for frontend
[agent.frontend]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal

# ACP agent for research
[agent.research]
type = acp
acp_command = gemini-cli
acp_capabilities = filesystem,terminal,web

# Native agent for testing
[agent.test]
type = opencode
opencode_args = --mode test
contract = contracts/test.md
```

### Workflow

```bash
# 1. Create tasks with labels
village tasks create "Implement auth API" --label backend
village tasks create "Design login UI" --label frontend
village tasks create "Research auth best practices" --label research
village tasks create "Write auth tests" --label test

# 2. Queue backend tasks (OpenCode)
village queue --n 2 --agent backend

# 3. Start frontend task (Claude)
village builder resume --task bd-login-ui --agent frontend

# 4. Start research task (Gemini)
village builder resume --task bd-auth-research --agent research

# 5. Queue tests (OpenCode)
village queue --n 1 --agent test
```

### Monitoring Mixed Agents

```bash
# View all workers
village status --workers
```

**Output:**
```
TASK_ID          STATUS    PANE     AGENT     WINDOW
bd-auth-api      ACTIVE    %20      backend   backend-1-bd-auth-api
bd-login-ui      ACTIVE    %21      frontend  frontend-1-bd-login-ui
bd-auth-research ACTIVE    %22      research  research-1-bd-auth-research
bd-auth-tests    ACTIVE    %23      test      test-1-bd-auth-tests
```

### Dependency Management

```bash
# Tasks with dependencies
village tasks create "Design UI" --label frontend
village tasks create "Implement UI" --label frontend --depends-on village-design-ui

# Village respects dependencies across agent types
village queue --n 10

# Village will:
# 1. Start bd-design-ui (Claude)
# 2. Wait for completion
# 3. Start bd-implement-ui (Claude)
```

### Full Example

```bash
# Morning workflow
village up

# Start ACP server for editor access
village acp --server start &

# Queue mixed tasks
village queue --n 4 --agent backend    # OpenCode
village builder resume --task bd-frontend-1 --agent frontend  # Claude
village builder resume --task bd-research-1 --agent research  # Gemini

# Monitor from CLI
watch -n 10 'village status --workers'

# Or monitor from editor (Zed/JetBrains)
# ACP server streams notifications in real-time
```

---

## Example 6: Real-Time Monitoring

**Goal:** Build a custom monitoring dashboard using ACP notifications.

### Prerequisites

- Village ACP server running
- Python 3.11+
- `aiohttp` for HTTP client

### Step 1: Start ACP Server

```bash
village acp --server start
```

### Step 2: Create Monitoring Script

```python
#!/usr/bin/env python3
"""Real-time Village monitoring via ACP."""

import asyncio
import json
from datetime import datetime

from aiohttp import ClientSession, ClientWebSocketResponse


class VillageMonitor:
    """Monitor Village tasks via ACP notifications."""

    def __init__(self, url: str = "http://localhost:9876"):
        self.url = url
        self.session_id = None

    async def connect(self) -> None:
        """Initialize connection to Village ACP server."""
        async with ClientSession() as session:
            # Initialize
            async with session.post(
                f"{self.url}/initialize",
                json={"protocol_version": 1},
            ) as resp:
                result = await resp.json()
                print(f"Connected to Village: {result['agent_info']['name']}")

            # Create monitoring session
            async with session.post(
                f"{self.url}/session/new",
                json={"cwd": "."},
            ) as resp:
                result = await resp.json()
                self.session_id = result["session_id"]
                print(f"Monitoring session: {self.session_id}")

            # Stream notifications
            await self._stream_notifications(session)

    async def _stream_notifications(self, session: ClientSession) -> None:
        """Stream real-time notifications."""
        ws_url = self.url.replace("http", "ws") + f"/ws/{self.session_id}"

        async with session.ws_connect(ws_url) as ws:
            print("\n📊 Monitoring Village tasks...\n")
            print(f"{'Time':<20} {'Type':<15} {'Task':<15} {'Details'}")
            print("=" * 80)

            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    notification = json.loads(msg.data)
                    self._handle_notification(notification)

    def _handle_notification(self, notification: dict) -> None:
        """Process and display notification."""
        params = notification.get("params", {})
        update = params.get("update", {})

        timestamp = datetime.now().strftime("%H:%M:%S")
        notif_type = update.get("type", "unknown")
        task_id = params.get("sessionId", "N/A")

        details = []
        if "cmd" in update:
            details.append(f"cmd={update['cmd']}")
        if "result" in update:
            details.append(f"result={update['result']}")
        if "pane" in update:
            details.append(f"pane={update['pane']}")

        detail_str = ", ".join(details) if details else "-"

        # Color code by type
        if notif_type == "error":
            print(f"\033[91m{timestamp:<20} {notif_type:<15} {task_id:<15} {detail_str}\033[0m")
        elif notif_type == "state_change":
            print(f"\033[92m{timestamp:<20} {notif_type:<15} {task_id:<15} {detail_str}\033[0m")
        else:
            print(f"{timestamp:<20} {notif_type:<15} {task_id:<15} {detail_str}")


async def main():
    monitor = VillageMonitor()
    await monitor.connect()


if __name__ == "__main__":
    import aiohttp
    asyncio.run(main())
```

### Step 3: Run Monitor

```bash
chmod +x monitor.py
./monitor.py
```

**Output:**
```
Connected to Village: village
Monitoring session: sess-monitor-123

📊 Monitoring Village tasks...

Time                Type            Task            Details
================================================================================
10:30:45            state_change    bd-a3f8         cmd=state_transition, result=success
10:30:46            lifecycle       bd-a3f8         cmd=queue, result=success
10:30:47            state_change    bd-a3f8         cmd=state_transition, result=success
10:31:02            file_change     bd-a3f8         cmd=file_modified
10:31:15            state_change    bd-a3f8         cmd=state_transition, result=success
10:31:16            lifecycle       bd-b7c2         cmd=queue, result=success
10:31:45            error           bd-b7c2         cmd=resume, result=error
```

### Step 4: Advanced Dashboard

Create a web dashboard:

```python
#!/usr/bin/env python3
"""Web dashboard for Village monitoring."""

from aiohttp import web
import asyncio
import json

# ... (similar setup as above)

async def dashboard(request):
    """Serve dashboard HTML."""
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Village Dashboard</title>
        <script>
        const ws = new WebSocket('ws://localhost:8080/ws');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            const table = document.getElementById('tasks');
            const row = table.insertRow();
            row.innerHTML = `
                <td>${new Date().toLocaleTimeString()}</td>
                <td>${data.params.update.type}</td>
                <td>${data.params.sessionId}</td>
                <td>${JSON.stringify(data.params.update)}</td>
            `;
        };
        </script>
    </head>
    <body>
        <h1>Village Dashboard</h1>
        <table id="tasks" border="1">
            <tr><th>Time</th><th>Type</th><th>Task</th><th>Details</th></tr>
        </table>
    </body>
    </html>
    """
    return web.Response(text=html, content_type='text/html')

# ... (run web server)
```

---

## Example 7: Custom ACP Agent

**Goal:** Create and integrate a custom ACP-compliant agent.

### Step 1: Implement ACP Agent

```python
#!/usr/bin/env python3
"""Custom ACP agent for specialized tasks."""

import asyncio
import json
import sys
from typing import Any


class CustomACPAgent:
    """Custom agent implementing ACP protocol."""

    async def handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        return {
            "protocol_version": params.get("protocol_version", 1),
            "agent_capabilities": {
                "filesystem": True,
                "terminal": False,
            },
            "agent_info": {
                "name": "custom-agent",
                "version": "1.0.0",
            },
        }

    async def handle_new_session(self, params: dict) -> dict:
        """Handle session/new request."""
        return {
            "session_id": f"custom-{params.get('cwd', 'default')}",
        }

    async def handle_prompt(self, params: dict) -> dict:
        """Handle session/prompt request."""
        prompt = params.get("prompt", [])
        
        # Extract text from prompt blocks
        text = " ".join(
            block.get("text", "")
            for block in prompt
            if isinstance(block, dict)
        )
        
        # Process prompt (custom logic here)
        response = f"Processed: {text[:100]}"
        
        return {
            "stop_reason": "end_turn",
            "content": response,
        }

    async def run(self):
        """Run agent (stdio transport)."""
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(
            lambda: protocol,
            sys.stdin,
        )

        while True:
            # Read JSON-RPC request
            line = await reader.readline()
            if not line:
                break

            try:
                request = json.loads(line)
                method = request.get("method", "")
                params = request.get("params", {})
                request_id = request.get("id")

                # Route to handler
                handler_name = f"handle_{method.replace('/', '_')}"
                handler = getattr(self, handler_name, None)

                if handler:
                    result = await handler(params)
                    
                    # Send response
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": result,
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32601,
                            "message": f"Method not found: {method}",
                        },
                    }

                print(json.dumps(response), flush=True)

            except Exception as e:
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": str(e),
                    },
                }
                print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    agent = CustomACPAgent()
    asyncio.run(agent.run())
```

### Step 2: Make Agent Executable

```bash
chmod +x custom-agent.py
sudo ln -s $(pwd)/custom-agent.py /usr/local/bin/custom-agent
```

### Step 3: Configure in Village

```ini
# .village/config
[agent.custom]
type = acp
acp_command = custom-agent
acp_capabilities = filesystem
```

### Step 4: Test Agent

```bash
# Test connection
village acp --client test custom

# Spawn agent
village acp --client spawn custom
```

### Step 5: Use in Workflow

```bash
# Create task for custom agent
village tasks create "Specialized processing" --label custom

# Assign to custom agent
village builder resume --task bd-special --agent custom
```

---

## Summary

| Example | Use Case | Key Features |
|---------|----------|--------------|
| Zed Editor | Editor integration | Real-time notifications, task control |
| JetBrains IDE | IDE integration | File operations, terminal commands |
| Claude Code | Specialized AI | Web access, advanced reasoning |
| Gemini CLI | Research tasks | Broad knowledge, analysis |
| Mixed workflow | Multi-agent | OpenCode + ACP agents |
| Monitoring | Observability | Real-time dashboard |
| Custom agent | Specialization | Custom capabilities |

---

## Next Steps

- **[Integration Guide](ACP_INTEGRATION.md)** - Architecture overview
- **[Configuration](ACP_CONFIGURATION.md)** - Complete config reference
- **[API Reference](ACP_API_REFERENCE.md)** - Detailed API docs
