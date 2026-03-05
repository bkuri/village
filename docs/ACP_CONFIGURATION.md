# ACP Configuration Reference

Complete configuration guide for ACP integration in Village.

---

## Table of Contents

1. [Overview](#overview)
2. [Server Configuration](#server-configuration)
3. [Agent Configuration](#agent-configuration)
4. [Environment Variables](#environment-variables)
5. [Configuration Examples](#configuration-examples)
6. [Validation](#validation)
7. [Troubleshooting](#troubleshooting)

---

## Overview

ACP configuration is split into two parts:

1. **Server config** - How Village exposes itself via ACP
2. **Agent config** - External ACP agents Village can spawn

Both are configured in `.village/config` (INI format).

---

## Server Configuration

### [acp] Section

Controls Village's ACP server behavior.

```ini
[acp]
enabled = true
host = localhost
port = 9876
version = 1
```

### Server Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `enabled` | boolean | `false` | Enable ACP server |
| `host` | string | `localhost` | Server bind address |
| `port` | integer | `9876` | Server port |
| `version` | integer | `1` | ACP protocol version |

### Capability Definitions

Define capabilities Village exposes to editors:

```ini
[acp]
enabled = true
capability_filesystem = Read and write files in worktrees
capability_terminal = Create and manage terminal sessions
capability_notifications = Stream real-time task updates
```

**Format:** `capability_<name> = <description>`

**Common capabilities:**
- `filesystem` - File read/write operations
- `terminal` - Terminal create/kill/output
- `notifications` - Real-time event streaming
- `task_management` - Queue/resume/pause tasks

### Full Server Example

```ini
[acp]
enabled = true
host = localhost
port = 9876
version = 1
capability_filesystem = Read and write files in worktrees
capability_terminal = Execute commands in tmux panes
capability_notifications = Real-time task state updates
capability_task_management = Queue, resume, and cancel tasks
```

---

## Agent Configuration

### ACP Agent Definition

Define external ACP agents Village can spawn:

```ini
[agent.<name>]
type = acp
acp_command = <command>
acp_capabilities = <cap1>,<cap2>,...
```

### Agent Settings

| Setting | Type | Required | Description |
|---------|------|----------|-------------|
| `type` | string | Yes | Must be `acp` for ACP agents |
| `acp_command` | string | Yes | Command to spawn agent |
| `acp_capabilities` | list | No | Comma-separated capability names |
| `opencode_args` | string | No | Ignored for ACP agents |
| `contract` | string | No | Ignored for ACP agents |
| `ppc_mode` | string | No | Ignored for ACP agents |

### Agent Types

Village supports two agent types:

**1. OpenCode (native)**
```ini
[agent.worker]
type = opencode
opencode_args = --mode patch
contract = contracts/worker.md
```

**2. ACP (external)**
```ini
[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal
```

### Claude Code Example

```ini
[agent.claude]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal,web

# Optional: specify full path
# acp_command = /usr/local/bin/claude-code

# Optional: pass arguments
# acp_command = claude-code --model claude-3-opus
```

### Gemini CLI Example

```ini
[agent.gemini]
type = acp
acp_command = gemini-cli
acp_capabilities = filesystem,terminal

# Optional: specify API key via environment
# acp_command = GOOGLE_API_KEY=xxx gemini-cli
```

### Custom Agent Example

```ini
[agent.custom]
type = acp
acp_command = /path/to/your/agent-binary
acp_capabilities = filesystem,terminal,custom_tools

# With environment variables
# acp_command = MY_API_KEY=secret /path/to/agent

# With arguments
# acp_command = /path/to/agent --model gpt-4 --verbose
```

---

## Environment Variables

All ACP settings can be overridden via environment variables.

### Server Overrides

| Variable | Config Key | Example |
|----------|------------|---------|
| `VILLAGE_ACP_ENABLED` | `acp.enabled` | `true` |
| `VILLAGE_ACP_HOST` | `acp.host` | `0.0.0.0` |
| `VILLAGE_ACP_PORT` | `acp.port` | `9999` |
| `VILLAGE_ACP_VERSION` | `acp.version` | `1` |

**Example:**
```bash
# Override port
VILLAGE_ACP_PORT=9999 village acp --server start

# Enable ACP via environment
VILLAGE_ACP_ENABLED=true village acp --server start
```

### Priority Order

1. **Environment variables** (highest priority)
2. **Config file settings**
3. **Default values** (lowest priority)

**Example:**
```ini
# .village/config
[acp]
port = 9876
```

```bash
# Environment overrides config
VILLAGE_ACP_PORT=9999 village acp --server start
# Server starts on port 9999
```

---

## Configuration Examples

### Example 1: Minimal Server

```ini
# .village/config
[acp]
enabled = true
```

**Result:**
- Server runs on `localhost:9876`
- Protocol version 1
- No capabilities declared

### Example 2: Production Server

```ini
# .village/config
[acp]
enabled = true
host = 0.0.0.0
port = 9876
version = 1
capability_filesystem = Read/write worktree files
capability_terminal = Execute terminal commands
capability_notifications = Stream task updates
capability_task_management = Manage Village tasks

[DEFAULT]
DEFAULT_AGENT = worker
MAX_WORKERS = 4

[agent.worker]
type = opencode
opencode_args = --mode patch
```

### Example 3: Multi-Agent Setup

```ini
# .village/config
[acp]
enabled = true

# Native agent for backend work
[agent.backend]
type = opencode
opencode_args = --mode build
contract = contracts/backend.md

# ACP agent for frontend work
[agent.frontend]
type = acp
acp_command = claude-code
acp_capabilities = filesystem,terminal

# ACP agent for research
[agent.research]
type = acp
acp_command = gemini-cli
acp_capabilities = filesystem,web

# ACP agent for testing
[agent.test]
type = acp
acp_command = /usr/local/bin/test-agent
acp_capabilities = filesystem,terminal,testing
```

### Example 4: Development Setup

```ini
# .village/config
[acp]
enabled = true
host = localhost
port = 9876

[agent.dev]
type = acp
acp_command = claude-code --model claude-3-sonnet
acp_capabilities = filesystem,terminal

[agent.worker]
type = opencode
opencode_args = --mode patch --verbose
```

### Example 5: Remote Server

```ini
# .village/config
[acp]
enabled = true
host = 0.0.0.0  # Listen on all interfaces
port = 9876

# Security: Use firewall to restrict access
```

**Warning:** Binding to `0.0.0.0` exposes ACP server to network. Use firewall rules to restrict access.

---

## Validation

### Automatic Validation

Village validates ACP configuration on startup:

```bash
village acp --server start
```

**Validates:**
1. `type=acp` agents have `acp_command` set
2. `acp_command` is executable (if absolute path)
3. Port is available (server mode)
4. Protocol version is supported

### Manual Validation

Check configuration:

```bash
# View ACP server config
village acp --server status

# View ACP agents
village acp --client list

# Test an agent
village acp --client test claude
```

### Common Validation Errors

**Error:** `ACP agent 'name' missing required field 'acp_command'`

**Fix:** Add `acp_command` to agent config:
```ini
[agent.claude]
type = acp
acp_command = claude-code  # <-- Add this
```

**Error:** `ACP agent 'name' command executable not found: /path/to/agent`

**Fix:** Check path or use command name:
```ini
[agent.custom]
type = acp
acp_command = claude-code  # Use command name (searches PATH)
# OR
acp_command = /full/path/to/agent  # Use absolute path
```

---

## Troubleshooting

### Server Not Starting

**Issue:** `ACP server is disabled`

**Fix:** Enable in config:
```ini
[acp]
enabled = true
```

**Issue:** `Address already in use`

**Fix:** Change port:
```ini
[acp]
port = 9999
```

Or kill existing process:
```bash
lsof -ti:9876 | xargs kill
```

### Agent Not Spawning

**Issue:** `Agent 'name' not found`

**Fix:** Check agent exists in config:
```bash
village acp --client list
```

**Issue:** `Agent 'name' is not an ACP agent`

**Fix:** Add `type = acp`:
```ini
[agent.claude]
type = acp  # <-- Add this
acp_command = claude-code
```

**Issue:** `Agent 'name' missing acp_command`

**Fix:** Add command:
```ini
[agent.claude]
type = acp
acp_command = claude-code  # <-- Add this
```

### Connection Issues

**Issue:** Editor can't connect

**Fix:** Check server is running:
```bash
village acp --server status
village acp --server start
```

**Issue:** `Connection refused`

**Fix:** Check host/port:
```bash
# Check server is listening
netstat -an | grep 9876

# Check firewall
sudo ufw status
```

### Configuration Not Loading

**Issue:** Config changes not applied

**Fix:** Restart server:
```bash
# Stop server (Ctrl+C)
# Restart
village acp --server start
```

**Issue:** Environment variables ignored

**Fix:** Ensure variables are set:
```bash
# Check variable
echo $VILLAGE_ACP_ENABLED

# Set explicitly
VILLAGE_ACP_ENABLED=true village acp --server start
```

---

## Advanced Topics

### Custom Capability Definitions

Define custom capabilities for specialized workflows:

```ini
[acp]
capability_custom_backtest = Run trading strategy backtests
capability_custom_research = Query research databases
```

**Note:** Custom capabilities require custom ACP bridge implementation.

### Agent Arguments

Pass arguments to ACP agents:

```ini
[agent.claude]
type = acp
acp_command = claude-code --model claude-3-opus --verbose
```

**Common arguments:**
- `--model <name>` - Specify model
- `--verbose` - Enable debug output
- `--config <path>` - Custom config file

### Environment Variables in Commands

Pass environment variables to agents:

```ini
[agent.custom]
type = acp
acp_command = MY_API_KEY=secret /path/to/agent
```

**Better approach:** Use shell wrapper:
```bash
#!/bin/bash
# /usr/local/bin/my-agent-wrapper
export MY_API_KEY=secret
exec /path/to/agent "$@"
```

```ini
[agent.custom]
type = acp
acp_command = /usr/local/bin/my-agent-wrapper
```

### Multiple Server Instances

Run multiple ACP servers (different ports):

```bash
# Terminal 1
VILLAGE_ACP_PORT=9876 village acp --server start

# Terminal 2
VILLAGE_ACP_PORT=9877 village acp --server start
```

**Use case:** Separate servers for different projects/environments.

---

## Configuration Checklist

Before using ACP, ensure:

- [ ] `[acp]` section exists in `.village/config`
- [ ] `enabled = true` is set
- [ ] Port is available (default: 9876)
- [ ] ACP agents have `type = acp`
- [ ] ACP agents have `acp_command` set
- [ ] Commands are executable (check with `which`)
- [ ] Environment variables are set (if needed)
- [ ] Firewall allows connections (if remote)

---

## Next Steps

- **[Integration Guide](ACP_INTEGRATION.md)** - Architecture overview
- **[Examples](ACP_EXAMPLES.md)** - Real-world usage
- **[API Reference](ACP_API_REFERENCE.md)** - Complete API docs
