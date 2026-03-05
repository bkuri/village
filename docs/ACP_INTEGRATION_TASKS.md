# ACP Integration Tasks

**Epic**: bd-4uv - ACP Integration Epic

**Strategy**: Hybrid approach - Village core remains custom, ACP provides interface layer

**Total Estimated Effort**: 4,080 minutes (68 hours / ~2 weeks with parallel development)

---

## Task Breakdown by Phase

### Phase 1: Foundation (Week 1)
**Can be developed in parallel** - No interdependencies

| Task ID | Task | Estimate | Assignable To | Status |
|---------|------|----------|---------------|--------|
| bd-4uv.1 | ACP Server Infrastructure | 8h | Backend Developer A | Open |
| bd-4uv.2 | ACP Client Infrastructure | 6h | Backend Developer B | Open |
| bd-4uv.3 | Transport Layer | 4h | Backend Developer C | Open |

**Parallelization**: 3 developers can work simultaneously

---

### Phase 2: Integration (Week 1-2)
**Depends on Phase 1 completion**

| Task ID | Task | Estimate | Depends On | Assignable To | Status |
|---------|------|----------|------------|---------------|--------|
| bd-4uv.4 | ACP Bridge Core | 8h | bd-4uv.1, bd-4uv.2, bd-4uv.3 | Senior Backend Dev | Open |
| bd-4uv.5 | Session Lifecycle Methods | 6h | bd-4uv.4 | Backend Developer A | Open |
| bd-4uv.6 | File System API | 5h | bd-4uv.4 | Backend Developer B | Open |
| bd-4uv.7 | Terminal API | 5h | bd-4uv.4 | Backend Developer C | Open |
| bd-4uv.8 | Notification Streaming | 6h | bd-4uv.4 | Backend Developer A | Open |

**Parallelization**: After bridge core is complete, 4 integration tasks can proceed in parallel

---

### Phase 3: Configuration & CLI (Week 2)
**Depends on Integration tasks**

| Task ID | Task | Estimate | Depends On | Assignable To | Status |
|---------|------|----------|------------|---------------|--------|
| bd-4uv.9 | Configuration Support | 3h | bd-4uv.4 | Backend Developer B | Open |
| bd-4uv.10 | CLI Commands | 4h | bd-4uv.1, bd-4uv.2, bd-4uv.4 | Backend Developer C | Open |

**Parallelization**: These 2 tasks can run in parallel

---

### Phase 4: Quality Assurance (Week 2-3)
**Depends on all integration tasks**

| Task ID | Task | Estimate | Depends On | Assignable To | Status |
|---------|------|----------|------------|---------------|--------|
| bd-4uv.11 | Testing Suite | 8h | bd-4uv.5, bd-4uv.6, bd-4uv.7, bd-4uv.8 | QA Engineer + Dev | Open |
| bd-4uv.12 | Documentation | 6h | All previous tasks | Technical Writer | Open |

**Parallelization**: Testing and documentation can proceed in parallel

---

## Parallel Development Strategy

### Maximum Parallelization (3-4 developers)

**Week 1:**
- Developer A: bd-4uv.1 (Server) → bd-4uv.5 (Session)
- Developer B: bd-4uv.2 (Client) → bd-4uv.6 (Filesystem)
- Developer C: bd-4uv.3 (Transport) → bd-4uv.7 (Terminal)
- Senior Dev: bd-4uv.4 (Bridge) → bd-4uv.8 (Notifications)

**Week 2:**
- Developer A: bd-4uv.8 (Notifications) → bd-4uv.11 (Testing)
- Developer B: bd-4uv.9 (Config) → bd-4uv.11 (Testing)
- Developer C: bd-4uv.10 (CLI) → bd-4uv.12 (Docs)
- Technical Writer: bd-4uv.12 (Docs)

**Week 3:**
- All: Integration testing, bug fixes, documentation polish

---

## Dependency Graph

```
Phase 1 (Parallel):
  bd-4uv.1 (Server)
  bd-4uv.2 (Client)  
  bd-4uv.3 (Transport)
        ↓
Phase 2 (Sequential → Parallel):
  bd-4uv.4 (Bridge Core)
        ↓
  bd-4uv.5 (Session) ──────┐
  bd-4uv.6 (Filesystem) ───┤
  bd-4uv.7 (Terminal) ─────┤
  bd-4uv.8 (Notifications)─┤
                            ↓
Phase 3 (Parallel):
  bd-4uv.9 (Config) ────────┤
  bd-4uv.10 (CLI) ──────────┤
                            ↓
Phase 4 (Parallel):
  bd-4uv.11 (Testing) ──────┤
  bd-4uv.12 (Documentation)─┘
```

---

## Critical Path

**Shortest possible timeline**: 2.5 weeks

1. Week 1: Foundation (bd-4uv.1, bd-4uv.2, bd-4uv.3) - **3 days**
2. Week 1-2: Bridge Core (bd-4uv.4) - **2 days**
3. Week 2: Integration (bd-4uv.5-8) - **4 days** (parallel)
4. Week 2: Config + CLI (bd-4uv.9, bd-4uv.10) - **2 days** (parallel)
5. Week 3: Testing + Docs (bd-4uv.11, bd-4uv.12) - **3 days** (parallel)

---

## Team Size Recommendations

### Small Team (2 developers)
- **Timeline**: 3-4 weeks
- **Approach**: Sequential phases, minimal parallelization
- **Risk**: Lower (fewer integration points)

### Medium Team (3-4 developers)
- **Timeline**: 2-3 weeks
- **Approach**: Full parallelization in phases 1-2
- **Risk**: Medium (more integration points)

### Large Team (5+ developers)
- **Timeline**: 2 weeks
- **Approach**: Maximum parallelization, pair programming on complex tasks
- **Risk**: Higher (many integration points, need strong coordination)

---

## Task Details

### bd-4uv.1 - ACP Server Infrastructure
**Estimate**: 8 hours
**Priority**: P2
**Labels**: acp, foundation, server

**Deliverables**:
- village/acp/server.py with ACPServer class
- JSON-RPC 2.0 compliant request/response handling
- Method registry with async handlers
- Error handling with proper error codes
- Support for notifications (no response expected)

**Acceptance Criteria**:
- Server handles initialize method correctly
- Server routes methods to registered handlers
- Server returns proper JSON-RPC error responses
- Server supports concurrent requests
- Unit tests pass with >90% coverage

---

### bd-4uv.2 - ACP Client Infrastructure
**Estimate**: 6 hours
**Priority**: P2
**Labels**: acp, foundation, client

**Deliverables**:
- village/acp/client.py with ACPClient class
- Subprocess management for local agents
- JSON-RPC request/response over stdio
- Agent initialization handshake
- Session management (new/load/prompt)

**Acceptance Criteria**:
- Client can connect to ACP-compliant agent
- Client handles initialize handshake
- Client can send session/prompt and receive response
- Client manages agent subprocess lifecycle
- Graceful shutdown on client disconnect
- Unit tests with mock agents

---

### bd-4uv.3 - Transport Layer
**Estimate**: 4 hours
**Priority**: P2
**Labels**: acp, foundation, transport

**Deliverables**:
- village/acp/transport.py with Transport base class
- StdioTransport for subprocess communication
- HTTPTransport for remote agents
- WebSocketTransport for real-time streaming
- Async read/write interfaces

**Acceptance Criteria**:
- All transports implement common interface
- StdioTransport works with subprocess pipes
- HTTPTransport supports request/response
- WebSocketTransport supports bidirectional streaming
- Connection lifecycle management (connect/disconnect)
- Unit tests for each transport type

---

### bd-4uv.4 - ACP Bridge Core
**Estimate**: 8 hours
**Priority**: P2
**Labels**: acp, integration, bridge
**Dependencies**: bd-4uv.1, bd-4uv.2, bd-4uv.3

**Deliverables**:
- village/acp/bridge.py with ACPBridge class
- Session-to-task mapping logic
- State transition bridging
- Event-to-notification conversion
- Error translation (Village errors → ACP errors)
- Integration with Village core modules

**Acceptance Criteria**:
- Bridge creates Village task for ACP session/new
- Bridge executes Village resume for ACP session/prompt
- Bridge converts Village events to ACP notifications
- Bridge validates ACP params against Village constraints
- Bridge handles Village errors gracefully
- Integration tests with mock Village core

---

### bd-4uv.5 - Session Lifecycle Methods
**Estimate**: 6 hours
**Priority**: P2
**Labels**: acp, integration, session
**Dependencies**: bd-4uv.4

**Deliverables**:
- ACPBridge.handle_initialize()
- ACPBridge.handle_session_new()
- ACPBridge.handle_session_load()
- ACPBridge.handle_session_prompt()
- ACPBridge.handle_session_cancel()
- Integration with TaskStateMachine

**Acceptance Criteria**:
- initialize returns Village capabilities
- session/new creates Village task in QUEUED state
- session/load resumes existing task
- session/prompt executes Village resume
- session/cancel transitions task to PAUSED
- All methods return ACP-compliant responses
- Unit tests with mock state machine

---

### bd-4uv.6 - File System API
**Estimate**: 5 hours
**Priority**: P2
**Labels**: acp, integration, filesystem
**Dependencies**: bd-4uv.4

**Deliverables**:
- ACPBridge.handle_fs_read_text_file()
- ACPBridge.handle_fs_write_text_file()
- Path validation (must be in worktree)
- Atomic write implementation
- Event logging for file changes

**Acceptance Criteria**:
- read returns file content from worktree
- write performs atomic write to worktree
- Path validation rejects non-worktree paths
- File changes logged to Village event log
- Proper error handling for missing files
- Unit tests with temp worktrees

---

### bd-4uv.7 - Terminal API
**Estimate**: 5 hours
**Priority**: P2
**Labels**: acp, integration, terminal
**Dependencies**: bd-4uv.4

**Deliverables**:
- ACPBridge.handle_terminal_create()
- ACPBridge.handle_terminal_output()
- ACPBridge.handle_terminal_kill()
- Terminal ID to tmux pane ID mapping
- Command execution in tmux panes
- Output capture from tmux panes

**Acceptance Criteria**:
- create spawns command in new tmux pane
- output captures pane output correctly
- kill terminates tmux pane
- Terminal IDs map to pane IDs
- Proper error handling for tmux failures
- Unit tests with mock tmux

---

### bd-4uv.8 - Notification Streaming
**Estimate**: 6 hours
**Priority**: P2
**Labels**: acp, integration, notifications
**Dependencies**: bd-4uv.4

**Deliverables**:
- ACPBridge._event_to_notification() converter
- Notification streaming infrastructure
- Event subscription mechanism
- Support for all Village event types
- Integration with ACP transport layer

**Acceptance Criteria**:
- State transitions → state_change notifications
- File modifications → file_change notifications
- Conflicts → conflict_detected notifications
- Notifications streamed in real-time
- Proper notification format per ACP spec
- Integration tests with event generators

---

### bd-4uv.9 - Configuration Support
**Estimate**: 3 hours
**Priority**: P2
**Labels**: acp, config
**Dependencies**: bd-4uv.4

**Deliverables**:
- Config parsing for [acp] section
- Agent definition with type=acp
- Server host/port configuration
- Capability mappings for agents
- Config validation

**Acceptance Criteria**:
- Parse [acp] server config (host, port, enabled)
- Parse agent definitions with type=acp
- Validate ACP agent configurations
- Load capabilities from config
- Backward compatible with existing config
- Unit tests for config parsing

---

### bd-4uv.10 - CLI Commands
**Estimate**: 4 hours
**Priority**: P2
**Labels**: acp, cli
**Dependencies**: bd-4uv.1, bd-4uv.2, bd-4uv.4

**Deliverables**:
- village acp-server start command
- village acp-server stop command
- village acp-server status command
- village acp-agent list command
- village acp-agent spawn command
- Integration with Click CLI

**Acceptance Criteria**:
- acp-server start launches ACP server
- acp-server stop gracefully shuts down server
- acp-server status shows server state
- acp-agent list shows configured agents
- acp-agent spawn starts specific agent
- All commands work with --json flag
- Integration tests for CLI commands

---

### bd-4uv.11 - Testing Suite
**Estimate**: 8 hours
**Priority**: P2
**Labels**: acp, testing
**Dependencies**: bd-4uv.5, bd-4uv.6, bd-4uv.7, bd-4uv.8

**Deliverables**:
- tests/test_acp_server.py
- tests/test_acp_client.py
- tests/test_acp_bridge.py
- tests/test_acp_integration.py
- Mock ACP server for testing
- Mock ACP client for testing
- Test fixtures and utilities

**Acceptance Criteria**:
- Unit tests for all bridge methods (>90% coverage)
- Integration tests for full ACP flows
- Mock server/client for isolated testing
- Tests run in CI/CD pipeline
- All tests pass with pytest
- Performance benchmarks included

---

### bd-4uv.12 - Documentation
**Estimate**: 6 hours
**Priority**: P2
**Labels**: acp, docs
**Dependencies**: All previous tasks

**Deliverables**:
- docs/ACP_INTEGRATION.md
- docs/ACP_CONFIGURATION.md
- docs/ACP_EXAMPLES.md
- docs/ACP_API_REFERENCE.md
- Update README.md with ACP section
- Add ACP to AGENTS.md

**Acceptance Criteria**:
- Architecture overview explains hybrid approach
- Configuration guide covers all ACP settings
- Workflow examples show end-to-end usage
- API reference documents all ACP methods
- Examples tested and verified
- Documentation reviewed and polished

---

## Getting Started

### For Developers

1. **Claim a task**: 
   ```bash
   bd edit <task-id> --assignee "your-name"
   ```

2. **Check dependencies**:
   ```bash
   bd show <task-id>
   ```

3. **Start working**:
   ```bash
   git checkout -b acp-<task-name>
   ```

4. **Update progress**:
   ```bash
   bd set-state <task-id> in-progress
   ```

### For Project Managers

1. **View all tasks**:
   ```bash
   bd list --parent bd-4uv
   ```

2. **Check readiness**:
   ```bash
   bd ready
   ```

3. **View dependency graph**:
   ```bash
   bd graph bd-4uv
   ```

---

## Success Metrics

- [ ] All 12 tasks completed
- [ ] ACP server running and accessible
- [ ] Village works from Zed editor via ACP
- [ ] Village can orchestrate Claude Code via ACP
- [ ] All tests passing with >90% coverage
- [ ] Documentation complete and reviewed
- [ ] Zero regressions in Village core functionality

---

## Next Steps

1. Assign tasks to developers
2. Set up parallel development branches
3. Establish daily sync meetings for integration points
4. Create shared test fixtures and mocks
5. Set up CI/CD pipeline for ACP tests

---

## Questions?

Contact the epic owner or use:
```bash
bd comments bd-4uv
```
