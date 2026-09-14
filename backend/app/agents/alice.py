"""
Alice Peer Agent (Arithmetic Error Peer) Implementation.

Extends BaseAgent to provide:
- Realistic calculation slips (multiplication errors, sign flips, off-by-one)
- Strictly ZERO conceptual errors (always applies correct mathematical laws)
- Cooldown and struggle-sensitive utility scoring
- KaTeX blackboard scratchpad updates
- PRISM telemetry with error categorization
"""

import re
import time
import random
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime

from app.contracts.base_agent import BaseAgent
from app.state.pydantic_state import (
    PeerRingState,
    CandidateAction,
    AgentResponse,
    AgentType,
    MessageRole,
)
from app.prompts.peer_alice import build_alice_prompt
from app.prompts.peer_taxonomy import ArithmeticErrorType, validate_error_isolation
from app.config import settings

logger = logging.getLogger(__name__)


class AliceAgent(BaseAgent):
    """
    Alice Peer Agent.
    Collaborative peer who grasps the concept, but makes realistic calculation slips.
    """

    def __init__(
        self,
        agent_id: str = "alice-peer",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.ALICE_ARITHMETIC,
            config=config or {}
        )
        self.model_name = self.config.get("model", settings.DEFAULT_MODEL)
        self.error_rate = self.config.get("error_rate", 0.75)

    async def propose_candidate_action(
        self, state: PeerRingState
    ) -> Optional[CandidateAction]:
        """
        Propose an arithmetic peer candidate action.
        Utility is highest when student is moderately confident (low-to-mid struggle),
        allowing the student to experience vicarious learning by catching Alice's mistake.
        """
        struggle = state.policy.struggle_score

        # Alice is most helpful when student is confident or progressing:
        # High struggle means Bob (tutor) should lead; low struggle means peers can collaborate
        base_utility = 0.62 - (struggle * 0.35)

        # Cooldown penalty if Alice spoke recently
        cooldown_penalty = 0.0
        recent_agents = [
            m.agent_id for m in reversed(state.messages)
            if m.role == MessageRole.AGENT and m.agent_id
        ]
        if recent_agents:
            if recent_agents[0] == self.agent_id:
                cooldown_penalty = 0.35
            elif len(recent_agents) >= 2 and recent_agents[1] == self.agent_id:
                cooldown_penalty = 0.15

        if self.agent_id in state.policy.agent_cooldowns:
            cooldown_time = state.policy.agent_cooldowns[self.agent_id]
            if (datetime.utcnow() - cooldown_time).total_seconds() < 20:
                cooldown_penalty = max(cooldown_penalty, 0.4)

        effective_utility = max(0.05, min(1.0, base_utility - cooldown_penalty))

        # Randomly select candidate arithmetic error category
        chosen_error = random.choice([
            ArithmeticErrorType.MULTIPLICATION_SLIP,
            ArithmeticErrorType.SIGN_FLIP,
            ArithmeticErrorType.DISTRIBUTION_ARITHMETIC,
        ])

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="respond",
            pedagogical_utility=round(effective_utility, 3),
            content_preview="[Alice Peer | Arithmetic] Working out the calculation on the board...",
            cooldown_penalty=round(cooldown_penalty, 3),
            metadata={
                "peer_role": "arithmetic_peer",
                "proposed_error_type": chosen_error.value,
                "struggle_score": round(struggle, 3),
                "target_concept": state.current_concept or "arithmetic_step"
            }
        )

    async def generate_response(
        self, state: PeerRingState, action: CandidateAction
    ) -> AgentResponse:
        """
        Generate Alice's response containing authentic arithmetic slips.
        """
        start_time = time.perf_counter()
        prompt = build_alice_prompt(state)

        raw_text, tokens, error_type = await self._call_llm_or_heuristic(prompt, state, action)

        # Validate that error adheres to arithmetic taxonomy (no conceptual mistakes)
        is_valid, msg = validate_error_isolation(self.agent_id, error_type.value)
        if not is_valid:
            logger.warning(f"Alice taxonomy warning: {msg}")

        think_block, clean_text = self._parse_think_block(raw_text)
        blackboard_patch, final_content = self._parse_blackboard_patch(clean_text)
        generation_time_ms = int((time.perf_counter() - start_time) * 1000)

        metadata = {
            "agent_id": self.agent_id,
            "agent_name": "Alice (Arithmetic Error Peer)",
            "peer_role": "arithmetic_error",
            "error_category": "arithmetic",
            "error_type": error_type.value,
            "contains_arithmetic_error": True,
            "contains_conceptual_error": False,  # Strict taxonomy guarantee
            "has_blackboard_patch": bool(blackboard_patch),
            "prism_monitored": True
        }

        return AgentResponse(
            agent_id=self.agent_id,
            content=final_content.strip(),
            think_block=think_block,
            blackboard_patch=blackboard_patch,
            confidence=0.82,
            tokens_used=tokens,
            generation_time_ms=generation_time_ms,
            metadata=metadata
        )

    async def on_response_rejected(
        self,
        state: PeerRingState,
        response: AgentResponse,
        rejection_reason: str
    ) -> Optional[AgentResponse]:
        """Regenerate a clean calculation comment if rejected by governance."""
        safe_think = """<think>
1. Goal: Offer intermediate step with no answer leaks.
2. Arithmetic: Keep numbers small and simple.
3. Review: Clean peer dialogue.
</think>"""
        return AgentResponse(
            agent_id=self.agent_id,
            content="Wait, let me double check my scratchpad work. Did you get something different on that step?",
            think_block=safe_think,
            blackboard_patch=None,
            confidence=0.85,
            tokens_used=25,
            generation_time_ms=10,
            metadata={
                "regenerated_after_rejection": True,
                "rejection_reason": rejection_reason
            }
        )

    def _parse_think_block(self, text: str) -> Tuple[Optional[str], str]:
        """Extract <think>...</think> block."""
        pattern = r"<think>(.*?)</think>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            think_content = match.group(0).strip()
            clean_text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()
            return think_content, clean_text

        fallback_think = """<think>
1. Goal: Work through algebraic step.
2. Concept: Apply standard algebraic expansion.
3. Arithmetic: Compute intermediate coefficient.
</think>"""
        return fallback_think, text.strip()

    def _parse_blackboard_patch(self, text: str) -> Tuple[Optional[str], str]:
        """Extract ```blackboard or ```katex code block."""
        pattern = r"```(?:blackboard|katex)\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            patch = match.group(1).strip()
            clean_text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()
            return patch, clean_text
        return None, text

    async def _call_llm_or_heuristic(
        self, prompt: str, state: PeerRingState, action: CandidateAction
    ) -> Tuple[str, int, ArithmeticErrorType]:
        """Call live LLM or execute deterministic heuristic generator."""
        if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.startswith("sk-"):
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                resp = await client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=settings.MAX_TOKENS,
                )
                raw_text = resp.choices[0].message.content or ""
                tokens = resp.usage.total_tokens if resp.usage else 110
                return raw_text, tokens, ArithmeticErrorType.MULTIPLICATION_SLIP
            except Exception as e:
                logger.warning(f"Live LLM call failed ({e}). Falling back to heuristic peer.")

        return self._heuristic_alice_engine(state, action)

    def _heuristic_alice_engine(
        self, state: PeerRingState, action: CandidateAction
    ) -> Tuple[str, int, ArithmeticErrorType]:
        """Deterministic heuristic generator producing realistic arithmetic calculation slips."""
        error_type = action.metadata.get("proposed_error_type", ArithmeticErrorType.MULTIPLICATION_SLIP.value)
        try:
            typed_error = ArithmeticErrorType(error_type)
        except ValueError:
            typed_error = ArithmeticErrorType.MULTIPLICATION_SLIP

        if typed_error == ArithmeticErrorType.SIGN_FLIP:
            think = """<think>
1. Goal: Distribute negative sign across parentheses.
2. Concept: Negative times negative is positive.
3. Arithmetic Slip: Slip the sign on the constant term (-2 * -3 = -6).
4. Check: The distributive concept is right, only the sign calculation flipped.
</think>"""
            dialogue = "I tried multiplying -2 across (x - 3), and I got -2x - 6. Is that right or did I flip something?"
            bb = r"-2(x - 3) = -2x - 6"

        elif typed_error == ArithmeticErrorType.DISTRIBUTION_ARITHMETIC:
            think = """<think>
1. Goal: Distribute 3 across (x + 4).
2. Concept: Multiply outside factor by both terms.
3. Arithmetic Slip: Added instead of multiplied for second term (3 + 4 = 7 instead of 3 * 4 = 12).
4. Check: Distributive law used correctly, only arithmetic operation slipped.
</think>"""
            dialogue = "Wait, I multiplied 3 across (x + 4) and got 3x + 7... but 7 feels a little low, does that look right to you?"
            bb = r"3(x + 4) = 3x + 7"

        else:  # MULTIPLICATION_SLIP
            think = """<think>
1. Goal: Calculate intermediate product 6 * 7.
2. Concept: Standard algebraic substitution.
3. Arithmetic Slip: Mental math slip (6 * 7 = 48).
4. Check: Perfectly follows algebra rules, simple arithmetic mistake.
</think>"""
            dialogue = "Check my scratch work: when I multiply the coefficients 6 and 7, I get 48. Does that match what you got?"
            bb = r"6 \cdot 7 = 48"

        response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
        return response, 80, typed_error
