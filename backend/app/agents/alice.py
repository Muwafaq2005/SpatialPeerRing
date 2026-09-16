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

        # Adaptive Error Budget:
        # 1. If student struggle is high (>= 0.65), peers must NOT confuse student with errors.
        # 2. If Alice made an arithmetic slip in the last 3 agent turns, do NOT repeat back-to-back slips.
        # 3. If fresh session (len <= 2), default to True to allow early diagnostic/testing.
        # 4. Otherwise, inject error with probability self.error_rate (~45%), meaning ~55% clean steps.
        recent_agent_msgs = [m for m in state.messages if m.role == MessageRole.AGENT]
        recent_errors_by_me = [
            m for m in recent_agent_msgs[-3:]
            if m.agent_id == self.agent_id and m.metadata.get("contains_arithmetic_error")
        ]

        if struggle >= 0.65 or recent_errors_by_me:
            should_inject_error = False
        elif len(state.messages) <= 2:
            should_inject_error = True
        else:
            should_inject_error = random.random() < self.error_rate

        # Randomly select candidate arithmetic error category
        chosen_error = random.choice([
            ArithmeticErrorType.MULTIPLICATION_SLIP,
            ArithmeticErrorType.SIGN_FLIP,
            ArithmeticErrorType.DISTRIBUTION_ARITHMETIC,
        ])

        # Select diverse speech act when not injecting an error
        speech_act = "error_slip" if should_inject_error else random.choice([
            "self_correction",
            "clarifying_question",
            "cheer_validation",
            "shared_vulnerability",
        ])

        if should_inject_error:
            preview = "[Alice Peer | Arithmetic Slip] Working out the calculation on the board..."
        elif speech_act == "clarifying_question":
            preview = "[Alice Peer | Question] Asking pod about the next operation..."
        elif speech_act == "cheer_validation":
            preview = "[Alice Peer | Cheer] Validating classmate's work..."
        else:
            preview = "[Alice Peer | Clean Step] Double-checking calculation and offering clean step..."

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="question" if speech_act == "clarifying_question" else "respond",
            pedagogical_utility=round(effective_utility, 3),
            content_preview=preview,
            cooldown_penalty=round(cooldown_penalty, 3),
            metadata={
                "peer_role": "arithmetic_peer",
                "proposed_error_type": chosen_error.value,
                "inject_error": should_inject_error,
                "speech_act": speech_act,
                "struggle_score": round(struggle, 3),
                "target_concept": state.current_concept or "arithmetic_step"
            }
        )

    async def generate_response(
        self, state: PeerRingState, action: CandidateAction
    ) -> AgentResponse:
        """
        Generate Alice's response containing authentic arithmetic slips or clean calculations.
        """
        start_time = time.perf_counter()
        inject_error = action.metadata.get("inject_error", True)
        prompt = build_alice_prompt(state, inject_error=inject_error)

        raw_text, tokens, error_type = await self._call_llm_or_heuristic(prompt, state, action)

        # Validate that error adheres to arithmetic taxonomy (no conceptual mistakes)
        if inject_error:
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
            "contains_arithmetic_error": inject_error,
            "contains_conceptual_error": False,  # Strict taxonomy guarantee
            "is_clean_step": not inject_error,
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
1. Goal: Whoops, my last answer got flagged. Let me just offer to re-check my work.
2. Concept: Keep it simple, just ask if they got something different.
3. Arithmetic: Nothing to calculate here, just backtrack.
</think>"""
        return AgentResponse(
            agent_id=self.agent_id,
            content="Hmm wait, actually let me redo that. I think I messed up somewhere in my scratchwork. Did you get something different for that step?",
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
1. Goal: Okay, working through the next calculation step.
2. Concept: I know which rule to use — it's the right approach.
3. Arithmetic: Let me crunch these numbers... (might slip up here, oops).
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
        groq_key = settings.GROQ_API_KEY or (settings.OPENAI_API_KEY if settings.OPENAI_API_KEY.startswith("gsk_") else "")
        openai_key = settings.OPENAI_API_KEY if settings.OPENAI_API_KEY.startswith("sk-") else ""

        if groq_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(
                    api_key=groq_key,
                    base_url="https://api.groq.com/openai/v1"
                )
                resp = await client.chat.completions.create(
                    model=settings.GROQ_MODEL or "llama-3.3-70b-versatile",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=settings.MAX_TOKENS,
                )
                raw_text = resp.choices[0].message.content or ""
                tokens = resp.usage.total_tokens if resp.usage else 110
                if raw_text:
                    return raw_text, tokens, ArithmeticErrorType.MULTIPLICATION_SLIP
            except Exception as e:
                logger.warning(f"Live Groq LLM call failed ({e}). Falling back to heuristic peer.")

        elif openai_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=openai_key)
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
        """Deterministic heuristic generator producing realistic arithmetic calculation slips or clean steps."""
        inject_error = action.metadata.get("inject_error", True)
        error_type = action.metadata.get("proposed_error_type", ArithmeticErrorType.MULTIPLICATION_SLIP.value)
        try:
            typed_error = ArithmeticErrorType(error_type)
        except ValueError:
            typed_error = ArithmeticErrorType.MULTIPLICATION_SLIP

        # Clean step branch: Alice calculates cleanly, models self-correction, or uses diverse speech acts
        if not inject_error:
            speech_act = action.metadata.get("speech_act", "self_correction")
            if speech_act == "clarifying_question":
                think = """<think>
1. Goal: Ask a clarifying question to the group before rushing into calculation.
2. Concept: Ask whether to distribute outside or simplify inside parentheses first.
3. Review: Collaborative student question, zero arithmetic claims.
</think>"""
                dialogue = "Wait, quick question for the group — do we distribute the outside number first, or should we combine the terms inside the parentheses first? What do you guys think?"
                bb = r"3(2x + 4) \overset{?}{\to} \text{distribute or combine inside?}"
            elif speech_act == "cheer_validation":
                think = """<think>
1. Goal: Validate the student's step and cheer them on.
2. Review: Warm, supportive peer encouragement.
</think>"""
                dialogue = "Oh nice catch! That makes so much more sense than what I was doing earlier. Your steps look super clean!"
                bb = r"\text{Great catch! Moving to next step...}"
            elif speech_act == "shared_vulnerability":
                think = """<think>
1. Goal: Express relatable student vulnerability about this topic.
2. Review: Build peer camaraderie and reduce student math anxiety.
</think>"""
                dialogue = "Honestly, negative signs always trip me up when distributing across parentheses. Glad we're double checking this together!"
                bb = r"\text{Watch out for negative signs!}"
            else:  # self_correction / clean calculation
                think = """<think>
1. Goal: Work out the next step cleanly and carefully.
2. Concept: Distribute -2 across (x - 3).
3. Arithmetic: -2 * x is -2x, and -2 * -3 is definitely +6.
4. Self-Check: Double checked signs! No arithmetic slip this turn.
</think>"""
                dialogue = "Wait, let me double check my arithmetic so I don't mess up the signs like earlier... okay, -2 times -3 is definitely +6! So we get -2x + 6. Nailed it this time! 😅"
                bb = r"-2(x - 3) = -2x + 6"

            response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
            return response, 80, typed_error

        if typed_error == ArithmeticErrorType.SIGN_FLIP:
            think = """<think>
I need to work with negative numbers here. Let me be careful with signs.
</think>"""
            dialogue = "When I work with this negative number, I'm getting confused about whether the result should be positive or negative. Can you check my arithmetic on this step?"
            bb = r"\text{Sign question: } -2(x - 3) = ?"

        elif typed_error == ArithmeticErrorType.DISTRIBUTION_ARITHMETIC:
            think = """<think>
I'm trying to distribute here, but I'm getting a weird number.
</think>"""
            dialogue = "I'm distributing the 3 across (x + 4), but I'm not sure if I'm multiplying correctly. What do you get for 3 times 4?"
            bb = r"3(x + 4) = 3x + ?"

        else:  # MULTIPLICATION_SLIP
            think = """<think>
I need to multiply two numbers here. Let me ask for verification.
</think>"""
            dialogue = "I'm trying to multiply 6 times 7 in my head. I got 48, but I'm not totally confident. Charlie, what do you get?"
            bb = r"6 \cdot 7 = ?"

        response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
        return response, 80, typed_error
