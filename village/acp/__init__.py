"""ACP integration for Village - Agent Client Protocol support.

This module provides hybrid ACP integration using the official
agent-client-protocol SDK:

- Village core remains custom (locks, worktrees, coordination)
- ACP provides interface layer for ecosystem compatibility
- Enables Village to work with ACP-compatible editors and agents

Modules:
- agent: Village as an ACP agent (for editors like Zed, JetBrains)
- external_client: Client for connecting to ACP agents (Claude Code, etc.)
- bridge: Bridge ACP protocol to Village core operations
"""

from village.acp.agent import VillageACPAgent, run_village_agent
from village.acp.external_client import VillageACPClient, spawn_acp_agent

__all__ = [
    "VillageACPAgent",
    "run_village_agent",
    "VillageACPClient",
    "spawn_acp_agent",
]
