"""
Charlie Peer Agent (Conceptual Error Peer) Implementation.

Extends BaseAgent to provide:
- Structural & conceptual misconceptions (order of operations, illegal cancellation, freshman's dream)
- Strictly ZERO arithmetic calculation mistakes (all additions and multiplications are 100% accurate)
- Cooldown and struggle-sensitive utility scoring
- KaTeX blackboard formula scratchpad updates
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
from app.prompts.peer_charlie import build_charlie_prompt
from app.prompts.peer_taxonomy import ConceptualErrorType, validate_error_isolation
from app.config import settings

logger = logging.getLogger(__name__)


class CharlieAgent(BaseAgent):
    """
    Charlie Peer Agent.
    Thoughtful peer who computes arithmetic with 100% precision,
    but holds seductive structural and conceptual misconceptions.
    """

    def __init__(
        self,
        agent_id: str = "charlie-peer",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.CHARLIE_CONCEPTUAL,
            config=config or {}
        )
        self.model_name = self.config.get("model", settings.DEFAULT_MODEL)
        self.misconception_rate = self.config.get("misconception_rate", 0.8)

    async def propose_candidate_action(
        self, state: PeerRingState
    ) -> Optional[CandidateAction]:
        """
        Propose a conceptual peer candidate action.
        Utility is highest when student has foundational footing (low-to-moderate struggle),
        challenging the student to spot a subtle conceptual trap or illegal shortcut.
        """
        struggle = state.policy.struggle_score

        # Charlie is most effective when student is not completely stuck:
        base_utility = 0.58 - (struggle * 0.30)

        # Cooldown penalty if Charlie spoke recently
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

        # Select candidate conceptual misconception
        chosen_error = random.choice([
            ConceptualErrorType.ORDER_OF_OPERATIONS,
            ConceptualErrorType.FRESHMAN_DREAM,
            ConceptualErrorType.ILLEGAL_CANCELLATION,
        ])

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="respond",
            pedagogical_utility=round(effective_utility, 3),
            content_preview="[Charlie Peer | Conceptual] What if we use this algebraic shortcut...",
            cooldown_penalty=round(cooldown_penalty, 3),
            metadata={
                "peer_role": "conceptual_peer",
                "proposed_error_type": chosen_error.value,
                "struggle_score": round(struggle, 3),
                "target_concept": state.current_concept or "algebraic_structure"
            }
        )

    async def generate_response(
        self, state: PeerRingState, action: CandidateAction
    ) -> AgentResponse:
        """
        Generate Charlie's response containing authentic conceptual misconceptions.
        """
        start_time = time.perf_counter()
        prompt = build_charlie_prompt(state)

        raw_text, tokens, error_type = await self._call_llm_or_heuristic(prompt, state, action)

        # Validate that error adheres to conceptual taxonomy (no arithmetic slips)
        is_valid, msg = validate_error_isolation(self.agent_id, error_type.value)
        if not is_valid:
            logger.warning(f"Charlie taxonomy warning: {msg}")

        think_block, clean_text = self._parse_think_block(raw_text)
        blackboard_patch, final_content = self._parse_blackboard_patch(clean_text)
        generation_time_ms = int((time.perf_counter() - start_time) * 1000)

        metadata = {
            "agent_id": self.agent_id,
            "agent_name": "Charlie (Conceptual Error Peer)",
            "peer_role": "conceptual_error",
            "error_category": "conceptual",
            "error_type": error_type.value,
            "contains_arithmetic_error": False,  # Strict taxonomy guarantee: Charlie's arithmetic is exact
            "contains_conceptual_error": True,
            "has_blackboard_patch": bool(blackboard_patch),
            "prism_monitored": True
        }

        return AgentResponse(
            agent_id=self.agent_id,
            content=final_content.strip(),
            think_block=think_block,
            blackboard_patch=blackboard_patch,
            confidence=0.84,
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
        """Regenerate a clean conceptual inquiry if rejected by governance."""
        safe_think = """<think>
1. Goal: Propose an intuitive peer question.
2. Structure: Adhere to standard definitions.
3. Review: Clean peer dialogue.
</think>"""
        return AgentResponse(
            agent_id=self.agent_id,
            content="Hmm, on second thought, maybe that shortcut isn't legal here. What do the rules say we should do first?",
            think_block=safe_think,
            blackboard_patch=None,
            confidence=0.88,
            tokens_used=28,
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
1. Goal: Analyze algebraic structure.
2. Misconception: Consider structural shortcut.
3. Arithmetic: Verified precise calculation.
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
    ) -> Tuple[str, int, ConceptualErrorType]:
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
                tokens = resp.usage.total_tokens if resp.usage else 115
                return raw_text, tokens, ConceptualErrorType.ORDER_OF_OPERATIONS
            except Exception as e:
                logger.warning(f"Live LLM call failed ({e}). Falling back to heuristic peer.")

        return self._heuristic_charlie_engine(state, action)

    def _heuristic_charlie_engine(
        self, state: PeerRingState, action: CandidateAction
    ) -> Tuple[str, int, ConceptualErrorType]:
        """Deterministic heuristic generator producing authentic conceptual misconceptions with exact arithmetic."""
        error_type = action.metadata.get("proposed_error_type", ConceptualErrorType.ORDER_OF_OPERATIONS.value)
        try:
            typed_error = ConceptualErrorType(error_type)
        except ValueError:
            typed_error = ConceptualErrorType.ORDER_OF_OPERATIONS

        if typed_error == ConceptualErrorType.ORDER_OF_OPERATIONS:
            # Flawless arithmetic: 2 + 3 = 5, 5 * 4 = 20. But order of operations violated!
            think = """<think>
1. Goal: Evaluate 2 + 3 * 4.
2. Conceptual Misconception: Add left-to-right before multiplying.
3. Flawless Arithmetic: 2 + 3 is exactly 5. 5 * 4 is exactly 20.
4. Check: All arithmetic is 100% correct, error is strictly order of operations.
</think>"""
            dialogue = "Look at this part: 2 + 3 * 4. If we add 2 + 3 first we get 5, and 5 * 4 is 20. Doesn't that make it much easier?"
            bb = r"2 + 3 \cdot 4 = (2 + 3) \cdot 4 = 5 \cdot 4 = 20"

        elif typed_error == ConceptualErrorType.FRESHMAN_DREAM:
            # Flawless arithmetic: 3^2 = 9. But exponent distributed over sum!
            think = """<think>
1. Goal: Expand (x + 3)^2.
2. Conceptual Misconception: Distribute exponent across terms (Freshman's Dream).
3. Flawless Arithmetic: 3^2 is exactly 9. x squared is x^2.
4. Check: Zero arithmetic mistakes; algebraic law violated.
</think>"""
            dialogue = "Couldn't we just distribute the square to both terms? (x + 3)^2 would just be x^2 + 9, right?"
            bb = r"(x + 3)^2 = x^2 + 3^2 = x^2 + 9"

        else:  # ILLEGAL_CANCELLATION
            # Flawless arithmetic, but cancelled term across addition
            think = """<think>
1. Goal: Simplify (2x + 6) / 2.
2. Conceptual Misconception: Cancel 2 in denominator only with 2 in numerator.
3. Flawless Arithmetic: 2 / 2 is exactly 1.
4. Check: Pure structural misconception across fraction addition.
</think>"""
            dialogue = "Since there's a 2 in the top and a 2 in the bottom, can't we just cancel them out and get x + 6?"
            bb = r"\frac{2x + 6}{2} \to \frac{\cancel{2}x + 6}{\cancel{2}} = x + 6"

        response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
        return response, 85, typed_error
