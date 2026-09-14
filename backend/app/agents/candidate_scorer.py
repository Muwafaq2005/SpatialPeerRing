"""
Candidate Scorer for Pedagogical Orchestrator.

Implements dynamic scoring formula:
FinalScore = (RawUtility * StruggleWeight) * (1.0 - CooldownPenalty)

Adjusts weights dynamically based on:
- Student struggle score and active Assistance Level
- Agent type (tutor vs. peer)
- Conversational flow and anti-monopolization guardrails
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.state.pydantic_state import PeerRingState, CandidateAction, AgentType, MessageRole


class ScoredCandidate(BaseModel):
    """Scored candidate action with transparent evaluation metrics."""
    model_config = ConfigDict(frozen=True)

    agent_id: str
    action: CandidateAction
    raw_utility: float
    struggle_weight: float
    cooldown_penalty: float
    final_score: float
    rationale: str


class CandidateScorer:
    """
    Dynamic candidate scorer for the study pod orchestrator.
    Determines which agent action provides the highest pedagogical value.
    """

    def __init__(self, cooldown_duration_sec: float = 20.0):
        self.cooldown_duration_sec = cooldown_duration_sec

    def score_candidates(
        self,
        candidates: List[CandidateAction],
        state: PeerRingState
    ) -> List[ScoredCandidate]:
        """
        Score and rank a list of candidate actions from highest to lowest score.
        """
        scored = [self.score_candidate(cand, state) for cand in candidates]
        # Sort descending by final score
        return sorted(scored, key=lambda s: s.final_score, reverse=True)

    def score_candidate(
        self,
        candidate: CandidateAction,
        state: PeerRingState
    ) -> ScoredCandidate:
        """
        Score an individual candidate action in the context of the current state.
        """
        agent_id = candidate.agent_id
        raw_utility = candidate.pedagogical_utility
        struggle = state.policy.struggle_score
        curr_level = state.policy.assistance_level.current_level

        # 1. Calculate Struggle & Pedagogical Weight
        struggle_weight = self._compute_struggle_weight(agent_id, struggle, curr_level)

        # 2. Calculate Conversational Cooldown & Monopolization Penalty
        cooldown_penalty = self._compute_cooldown_penalty(agent_id, candidate, state)

        # 3. Compute Final Score
        # Formula: (raw_utility * struggle_weight) * (1.0 - cooldown_penalty)
        weighted_utility = raw_utility * struggle_weight
        final_score = max(0.0, weighted_utility * (1.0 - cooldown_penalty))
        final_score = round(min(final_score, 1.0), 3)

        rationale = (
            f"RawUtility={raw_utility:.2f}, "
            f"StruggleWeight={struggle_weight:.2f} (struggle={struggle:.2f}, lvl={curr_level}), "
            f"CooldownPenalty={cooldown_penalty:.2f} -> FinalScore={final_score:.3f}"
        )

        return ScoredCandidate(
            agent_id=agent_id,
            action=candidate,
            raw_utility=raw_utility,
            struggle_weight=round(struggle_weight, 3),
            cooldown_penalty=round(cooldown_penalty, 3),
            final_score=final_score,
            rationale=rationale
        )

    def _compute_struggle_weight(
        self, agent_id: str, struggle: float, assistance_level: int
    ) -> float:
        """Determine pedagogical priority based on student struggle."""
        is_tutor = (agent_id in ["bob-tutor", "mock-bob-tutor"])

        if is_tutor:
            # When student struggles heavily, Bob's pedagogical intervention is essential
            if struggle >= 0.70 or assistance_level >= 5:
                return 1.30
            elif struggle >= 0.35 or assistance_level >= 3:
                return 1.10
            else:
                # Student doing fine; let peers participate
                return 0.90
        else:
            # For peer agents (Alice, Charlie):
            if struggle >= 0.70 or assistance_level >= 5:
                # Suppress peer mistakes when student is overwhelmed
                return 0.45
            elif struggle >= 0.35:
                return 0.95
            else:
                # Low struggle -> boost peer collaboration & error-spotting
                return 1.25

    def _compute_cooldown_penalty(
        self, agent_id: str, candidate: CandidateAction, state: PeerRingState
    ) -> float:
        """Calculate combined cooldown penalty from turn history and timestamps."""
        penalty = candidate.cooldown_penalty

        # Check turn history for consecutive speech (anti-monopolization)
        recent_agents = [
            msg.agent_id for msg in reversed(state.messages)
            if msg.role == MessageRole.AGENT and msg.agent_id
        ]

        if recent_agents:
            # Spoke last 2 turns in a row -> strictly forbidden from speaking a 3rd consecutive time
            if len(recent_agents) >= 2 and recent_agents[0] == agent_id and recent_agents[1] == agent_id:
                return 1.0

            # Spoke last turn -> heavy cooldown penalty
            if recent_agents[0] == agent_id:
                penalty = max(penalty, 0.45)

        # If agent hasn't spoken in last 2 turns, clear any timestamp penalty
        if recent_agents and len(recent_agents) >= 2 and agent_id not in recent_agents[:2]:
            return 0.0

        # Check timestamp-based cooldown from policy state
        if agent_id in state.policy.agent_cooldowns:
            last_spoken_time = state.policy.agent_cooldowns[agent_id]
            elapsed_sec = (datetime.utcnow() - last_spoken_time).total_seconds()
            if elapsed_sec < self.cooldown_duration_sec:
                # Linear cooldown decay over time
                time_penalty = 0.4 * (1.0 - (elapsed_sec / self.cooldown_duration_sec))
                penalty = max(penalty, time_penalty)

        return min(penalty, 1.0)
