"""
Pedagogical Orchestrator for Spatial PeerRing.

Coordinates multi-agent pedagogical loop between Bob (tutor), Alice (peer), and Charlie (peer).
Replaces static turn sequences with dynamic candidate proposal, transparent utility scoring,
and conversational cooldown management.
"""

import asyncio
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from app.contracts.base_agent import BaseAgent
from app.agents.bob import BobAgent
from app.agents.alice import AliceAgent
from app.agents.charlie import CharlieAgent
from app.agents.candidate_scorer import CandidateScorer, ScoredCandidate
from app.state.pydantic_state import (
    PeerRingState,
    CandidateAction,
    AgentResponse,
    DialogueMessage,
    MessageRole,
)

logger = logging.getLogger(__name__)


class PedagogicalOrchestrator:
    """
    Central turn allocator and pedagogical orchestrator for the 3D study pod.
    """

    def __init__(
        self,
        agents: Optional[Dict[str, BaseAgent]] = None,
        scorer: Optional[CandidateScorer] = None,
    ):
        """
        Initialize orchestrator with agents and candidate scorer.
        """
        if agents is not None:
            self.agents = agents
        else:
            bob = BobAgent()
            alice = AliceAgent()
            charlie = CharlieAgent()
            self.agents = {
                bob.agent_id: bob,
                alice.agent_id: alice,
                charlie.agent_id: charlie,
            }

        self.scorer = scorer or CandidateScorer()

    async def orchestrate_turn(
        self,
        state: PeerRingState,
        user_input: Optional[str] = None
    ) -> Tuple[AgentResponse, Dict[str, Any]]:
        """
        Execute an end-to-end pedagogical turn:
        1. Ingest user message & update struggle state
        2. Query all agents for CandidateAction proposals in parallel
        3. Score candidates with CandidateScorer
        4. Select winning speaker and generate response with <think> deliberation
        5. Update cooldowns and append dialogue message to state
        """
        turn_start = time.perf_counter()

        # Step 1: Ingest user input if provided
        if user_input:
            user_msg = DialogueMessage(
                role=MessageRole.USER,
                content=user_input,
                timestamp=datetime.utcnow()
            )
            state.add_message(user_msg)
            # Recompute struggle score
            state.calculate_struggle_score()

        # Step 2: Concurrently collect proposals from all agents
        agent_list = list(self.agents.values())
        proposal_tasks = [agent.propose_candidate_action(state) for agent in agent_list]
        proposals = await asyncio.gather(*proposal_tasks, return_exceptions=True)

        valid_candidates: List[CandidateAction] = []
        for agent, proposal in zip(agent_list, proposals):
            if isinstance(proposal, Exception):
                logger.error(f"Error getting proposal from {agent.agent_id}: {proposal}")
            elif isinstance(proposal, CandidateAction):
                valid_candidates.append(proposal)

        # Fallback if no agents proposed
        if not valid_candidates:
            logger.warning("No agents proposed an action; falling back to default Bob proposal.")
            bob_agent = self.agents.get("bob-tutor") or self.agents.get("mock-bob-tutor") or agent_list[0]
            valid_candidates.append(
                CandidateAction(
                    agent_id=bob_agent.agent_id,
                    action_type="question",
                    pedagogical_utility=0.75,
                    content_preview="[Fallback] How are you feeling about this problem?",
                    metadata={"fallback": True}
                )
            )

        # Step 3: Score all candidates
        scored_candidates: List[ScoredCandidate] = self.scorer.score_candidates(
            valid_candidates, state
        )
        winning_scored = scored_candidates[0]
        winner_id = winning_scored.agent_id
        winning_agent = self.agents.get(winner_id)

        if not winning_agent:
            # Fallback to first available agent if key mismatch
            winning_agent = agent_list[0]
            winner_id = winning_agent.agent_id

        # Step 4: Generate response from winning agent
        response = await winning_agent.generate_response(state, winning_scored.action)

        # Step 5: Update state policy cooldowns and active speaker
        now = datetime.utcnow()
        state.policy.agent_cooldowns[winner_id] = now
        state.policy.last_active_agent = winner_id

        turn_duration_ms = int((time.perf_counter() - turn_start) * 1000)

        # Step 6: Assemble PRISM orchestration telemetry
        orchestration_telemetry = {
            "winner_id": winner_id,
            "winner_score": winning_scored.final_score,
            "winning_action_type": winning_scored.action.action_type,
            "all_candidate_scores": {
                sc.agent_id: sc.final_score for sc in scored_candidates
            },
            "scoring_rationales": {
                sc.agent_id: sc.rationale for sc in scored_candidates
            },
            "struggle_score_at_turn": state.policy.struggle_score,
            "assistance_level_at_turn": state.policy.assistance_level.current_level,
            "turn_number": state.turn_count + 1,
            "orchestration_duration_ms": turn_duration_ms,
            "prism_event": "ORCHESTRATOR_SPEAKER_SELECTED"
        }

        # Step 7: Record response in state dialogue history
        agent_msg = DialogueMessage(
            role=MessageRole.AGENT,
            agent_id=winner_id,
            content=response.content,
            think_block=response.think_block,
            blackboard_patch=response.blackboard_patch,
            timestamp=now,
            metadata={
                **response.metadata,
                "orchestration": orchestration_telemetry
            }
        )
        state.add_message(agent_msg)

        return response, orchestration_telemetry

    def get_agent(self, agent_id: str) -> Optional[BaseAgent]:
        """Retrieve registered agent by ID."""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """List IDs of all registered agents."""
        return list(self.agents.keys())
