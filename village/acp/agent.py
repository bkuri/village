"""Village ACP Agent - Exposes Village via ACP protocol.

Uses official agent-client-protocol SDK to wrap Village core
as an ACP-compliant agent that editors can connect to.
"""

import logging
from typing import Any

from acp import Agent, PromptResponse, text_block

from village.config import Config, get_config
from village.resume import execute_resume

logger = logging.getLogger(__name__)


class VillageACPAgent(Agent):
    """Village as an ACP-compliant agent.
    
    Bridges ACP protocol to Village core operations:
    - ACP sessions → Village tasks
    - ACP prompts → Village resume
    - ACP notifications → Village events
    """
    
    def __init__(self, config: Config | None = None):
        """Initialize Village ACP agent.
        
        Args:
            config: Village config (uses default if not provided)
        """
        super().__init__()
        self.config = config or get_config()
    
    async def prompt(
        self,
        prompt: list[Any],
        session_id: str,
        **kwargs: Any,
    ) -> PromptResponse:
        """Handle ACP session/prompt.
        
        Args:
            prompt: List of content blocks from user
            session_id: ACP session ID (maps to Village task ID)
            **kwargs: Additional ACP parameters
            
        Returns:
            PromptResponse with Village results
        """
        # Extract text from prompt blocks
        user_message = self._extract_text(prompt)
        logger.info(f"ACP prompt for session {session_id}: {user_message[:100]}")
        
        try:
            # Execute Village resume (core operation)
            result = execute_resume(
                task_id=session_id,
                config=self.config,
            )
            
            # Build response
            response_text = f"✓ Task {session_id} completed\n"
            response_text += f"Agent: {result.agent}\n"
            response_text += f"Worktree: {result.worktree_path}\n"
            
            if result.error:
                response_text += f"Error: {result.error}\n"
            
            return PromptResponse(
                stop_reason="end_turn",
                updates=[
                    text_block(response_text),
                ],
            )
        except Exception as e:
            logger.exception(f"Error in ACP prompt: {e}")
            return PromptResponse(
                stop_reason="error",
                updates=[
                    text_block(f"Error: {e}"),
                ],
            )
    
    def _extract_text(self, prompt: list[Any]) -> str:
        """Extract text from prompt blocks.
        
        Args:
            prompt: List of content blocks
            
        Returns:
            Concatenated text
        """
        texts = []
        for block in prompt:
            if hasattr(block, "text"):
                texts.append(block.text)
            elif isinstance(block, dict) and "text" in block:
                texts.append(block["text"])
        return " ".join(texts)


def run_village_agent(config: Config | None = None) -> None:
    """Run Village as an ACP agent.
    
    Entry point for: village acp-server
    
    Args:
        config: Village config (uses default if not provided)
    """
    from acp import run_agent
    
    agent = VillageACPAgent(config)
    run_agent(agent)
