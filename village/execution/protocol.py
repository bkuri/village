"""Agent ↔ execution engine protocol: <plan> and <executed> blocks.

The plan protocol lets agents propose actions as structured JSON inside
``<plan>`` tags. The execution engine validates, executes, and returns
results as ``<executed>`` blocks. This is OPTIONAL — if no ``<plan>`` is
found in agent output, the builder falls back to traditional
``<promise>DONE</promise>`` monitoring.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Markers for agent ↔ execution engine protocol
PLAN_PATTERN = re.compile(r"<plan>(.*?)</plan>", re.DOTALL)
EXECUTED_PATTERN = re.compile(r"<executed>(.*?)</executed>", re.DOTALL)


@dataclass
class PlanAction:
    """A single action proposed by the agent."""

    action: str  # "write" | "bash" | "delete" | "read"
    path: str | None = None
    content: str | None = None
    command: str | None = None
    id: int = 0


@dataclass
class Plan:
    """A complete plan proposed by the agent."""

    actions: list[PlanAction] = field(default_factory=list)
    raw_text: str = ""


@dataclass
class ExecutionResult:
    """Result of executing a single plan action."""

    id: int
    status: str  # "ok" | "blocked" | "error"
    stdout: str = ""
    stderr: str = ""
    reason: str = ""  # populated when blocked


class PlanProtocol:
    """Handles the <plan>/<executed> protocol between agent and engine."""

    @staticmethod
    def parse_plan(text: str) -> Plan | None:
        """Extract the first <plan>...</plan> block from agent output.

        The block must contain valid JSON (a list of action dicts).
        Returns None if no valid plan block is found.

        Args:
            text: Raw agent output to scan for plan blocks.

        Returns:
            A :class:`Plan` with parsed actions, or None if no plan found.
        """
        match = PLAN_PATTERN.search(text)
        if not match:
            return None

        raw = match.group(1).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.debug("Found <plan> block but content is not valid JSON")
            return None

        if not isinstance(data, list):
            logger.debug("Found <plan> block but content is not a list")
            return None

        actions: list[PlanAction] = []
        for i, item in enumerate(data):
            if not isinstance(item, dict):
                continue
            actions.append(
                PlanAction(
                    action=str(item.get("action", "bash")),
                    path=str(item["path"]) if "path" in item else None,
                    content=str(item["content"]) if "content" in item else None,
                    command=str(item["command"]) if "command" in item else None,
                    id=int(item.get("id", i)),
                )
            )

        return Plan(actions=actions, raw_text=raw)

    @staticmethod
    def format_executed(results: list[ExecutionResult]) -> str:
        """Format execution results as an <executed> block for the agent.

        Long stdout/stderr output is truncated to prevent overwhelming the
        agent context window.

        Args:
            results: List of execution results from running plan actions.

        Returns:
            A string containing the wrapped ``<executed>`` block.
        """
        data: list[dict[str, object]] = []
        for r in results:
            entry: dict[str, object] = {"id": r.id, "status": r.status}
            if r.stdout:
                entry["stdout"] = r.stdout[:10000]  # truncate long output
            if r.stderr:
                entry["stderr"] = r.stderr[:5000]
            if r.reason:
                entry["reason"] = r.reason
            data.append(entry)
        return f"<executed>\n{json.dumps(data, indent=2)}\n</executed>"

    @staticmethod
    def format_contract_section(manifest: Any | None = None) -> str:
        """Generate the protocol instructions section for the agent contract.

        Tells the agent how to communicate with the execution engine
        using ``<plan>`` and ``<executed>`` blocks.

        Args:
            manifest: Optional approval manifest (reserved for future use).

        Returns:
            A markdown string containing protocol instructions.
        """
        return """## Execution Protocol

You must communicate all actions through the execution engine. Do NOT execute commands directly.

### How to propose actions

First, think through what needs to be done. Then output a plan:

<plan>
[
  {"action": "write", "path": "src/foo.py", "content": "# code here"},
  {"action": "bash", "command": "pytest tests/test_foo.py -v"}
]
</plan>

Wait for the execution engine to respond with results:

<executed>
[
  {"id": 0, "status": "ok"},
  {"id": 1, "status": "ok", "stdout": "1 passed in 0.5s"}
]
</executed>

Read the results and decide next steps. Repeat until done.

### Supported actions
- **write**: Write content to a file (path + content)
- **bash**: Execute a command (command string)
- **delete**: Delete a file (path)
- **read**: Read a file (path) — auto-approved

### Rules
- Do NOT run git commit/push directly — the engine handles this
- Do NOT run destructive commands without justification
- All files outside allowed paths will be rejected
"""
