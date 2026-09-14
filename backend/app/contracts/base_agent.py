"""
BaseAgent Abstract Contract
Defines the interface for all PeerRing agents (Bob, Alice, Charlie)
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging

from app.state.pydantic_state import (
    PeerRingState,
    CandidateAction,
    AgentResponse,
    AgentType
)

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all PeerRing agents.

    This contract ensures that usm and muw can develop against a stable interface
    while nad implements the governance layer and usm builds the actual agents.
    """

    def __init__(self, agent_id: str, agent_type: AgentType, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent from AgentType enum
            config: Optional configuration dictionary
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{agent_id}")

    @abstractmethod
    async def propose_candidate_action(self, state: PeerRingState) -> Optional[CandidateAction]:
        """
        Propose a candidate action for the pedagogical orchestrator to evaluate.

        This method should analyze the current state and return a candidate action
        with appropriate pedagogical utility scoring. If the agent determines it
        should not act in this turn, it can return None.

        Args:
            state: Current PeerRingState with dialogue history and curriculum status

        Returns:
            CandidateAction with scoring, or None if agent should not act

        Raises:
            NotImplementedError: Must be implemented by concrete agents
        """
        raise NotImplementedError("Agents must implement propose_candidate_action")

    @abstractmethod
    async def generate_response(
        self,
        state: PeerRingState,
        action: CandidateAction
    ) -> AgentResponse:
        """
        Generate the full agent response for a selected candidate action.

        This method is called after the orchestrator selects this agent's
        candidate action as the winner. It should generate the complete response
        including any think blocks (Pólya deliberation) and blackboard patches.

        Args:
            state: Current PeerRingState
            action: The CandidateAction that was selected by the orchestrator

        Returns:
            Complete AgentResponse with content, think_block, and metadata

        Raises:
            NotImplementedError: Must be implemented by concrete agents
        """
        raise NotImplementedError("Agents must implement generate_response")

    async def on_response_rejected(
        self,
        state: PeerRingState,
        response: AgentResponse,
        rejection_reason: str
    ) -> Optional[AgentResponse]:
        """
        Handle governance rejection and optionally regenerate response.

        This method is called when the leak judge or help judge rejects
        the agent's response. The agent can attempt to regenerate or return
        None to let the PolicyRewriter handle it.

        Args:
            state: Current PeerRingState
            response: The rejected AgentResponse
            rejection_reason: Reason for rejection from governance system

        Returns:
            New AgentResponse attempt, or None to defer to PolicyRewriter
        """
        # Default implementation defers to PolicyRewriter
        self.logger.warning(f"Response rejected: {rejection_reason}")
        return None

    def get_cooldown_seconds(self) -> int:
        """
        Get the cooldown period for this agent type.

        Returns:
            Cooldown in seconds before agent can be selected again
        """
        # Default cooldowns by agent type
        cooldowns = {
            AgentType.BOB_TUTOR: 30,      # Tutor can act more frequently
            AgentType.ALICE_ARITHMETIC: 60,    # Peers have longer cooldowns
            AgentType.CHARLIE_CONCEPTUAL: 60,  # to prevent dominance
        }
        return cooldowns.get(self.agent_type, 45)

    def calculate_pedagogical_utility(self, state: PeerRingState) -> float:
        """
        Calculate base pedagogical utility score for this agent type.

        This is a helper method that concrete agents can override or extend.

        Args:
            state: Current PeerRingState

        Returns:
            Utility score between 0.0 and 1.0
        """
        # Base utility by agent type and current policy state
        if self.agent_type == AgentType.BOB_TUTOR:
            # Tutor more valuable when student is struggling
            base_utility = 0.6 + (state.policy.struggle_score * 0.3)
        elif self.agent_type in [AgentType.ALICE_ARITHMETIC, AgentType.CHARLIE_CONCEPTUAL]:
            # Peers more valuable when student is confident but making mistakes
            base_utility = 0.4 + ((1.0 - state.policy.struggle_score) * 0.4)
        else:
            base_utility = 0.5

        # Check if this agent type spoke recently (lower utility)
        recent_messages = state.get_recent_messages(3)
        if recent_messages:
            recent_speakers = [msg.agent_id for msg in recent_messages if msg.agent_id]
            if self.agent_id in recent_speakers:
                return 0.2

        return min(max(base_utility, 0.0), 1.0)

    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.__class__.__name__}(id={self.agent_id}, type={self.agent_type.value})"

    def __repr__(self) -> str:
        """Detailed string representation of the agent."""
        return f"{self.__class__.__name__}(agent_id='{self.agent_id}', agent_type='{self.agent_type.value}', config={self.config})"