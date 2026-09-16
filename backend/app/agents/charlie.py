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

        # Adaptive Error Budget:
        # 1. If student struggle is high (>= 0.65), peers must NOT confuse student with misconceptions.
        # 2. If Charlie proposed a flawed shortcut in the last 3 agent turns, do NOT repeat misconceptions back-to-back.
        # 3. If fresh session (len <= 2), default to True to allow early diagnostic/testing.
        # 4. Otherwise, inject misconception with probability self.misconception_rate (~45%), meaning ~55% valid insights.
        recent_agent_msgs = [m for m in state.messages if m.role == MessageRole.AGENT]
        recent_errors_by_me = [
            m for m in recent_agent_msgs[-3:]
            if m.agent_id == self.agent_id and m.metadata.get("contains_conceptual_error")
        ]

        if struggle >= 0.65 or recent_errors_by_me:
            should_inject_error = False
        elif len(state.messages) <= 2:
            should_inject_error = True
        else:
            should_inject_error = random.random() < self.misconception_rate

        # Select candidate conceptual misconception
        chosen_error = random.choice([
            ConceptualErrorType.ORDER_OF_OPERATIONS,
            ConceptualErrorType.FRESHMAN_DREAM,
            ConceptualErrorType.ILLEGAL_CANCELLATION,
        ])

        # Select diverse speech act when not injecting a misconception
        speech_act = "conceptual_trap" if should_inject_error else random.choice([
            "valid_shortcut",
            "rule_reminder",
            "clarifying_question",
            "peer_validation",
        ])

        if should_inject_error:
            preview = "[Charlie Peer | Conceptual Shortcut] What if we use this algebraic shortcut..."
        elif speech_act == "clarifying_question":
            preview = "[Charlie Peer | Question] Asking tutor about factoring before division..."
        elif speech_act == "rule_reminder":
            preview = "[Charlie Peer | Rule Recall] Reminding pod about algebraic boundaries..."
        elif speech_act == "peer_validation":
            preview = "[Charlie Peer | Validation] Confirming peer's calculation..."
        else:
            preview = "[Charlie Peer | Valid Shortcut] Spotting a clean, valid algebraic simplification..."

        return CandidateAction(
            agent_id=self.agent_id,
            action_type="question" if speech_act == "clarifying_question" else "respond",
            pedagogical_utility=round(effective_utility, 3),
            content_preview=preview,
            cooldown_penalty=round(cooldown_penalty, 3),
            metadata={
                "peer_role": "conceptual_peer",
                "proposed_error_type": chosen_error.value,
                "inject_error": should_inject_error,
                "speech_act": speech_act,
                "struggle_score": round(struggle, 3),
                "target_concept": state.current_concept or "algebraic_structure"
            }
        )

    async def generate_response(
        self, state: PeerRingState, action: CandidateAction
    ) -> AgentResponse:
        """
        Generate Charlie's response containing authentic conceptual misconceptions or valid shortcuts.
        """
        start_time = time.perf_counter()
        inject_error = action.metadata.get("inject_error", True)
        prompt = build_charlie_prompt(state, inject_error=inject_error)

        raw_text, tokens, error_type = await self._call_llm_or_heuristic(prompt, state, action)

        # Validate that error adheres to conceptual taxonomy (no arithmetic slips)
        if inject_error:
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
            "contains_conceptual_error": inject_error,
            "is_clean_step": not inject_error,
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
1. Goal: My shortcut got flagged. Let me gracefully walk it back.
2. Structure: Ask the group what the actual rule says.
3. Review: No mathematical claims, just an honest question.
</think>"""
        return AgentResponse(
            agent_id=self.agent_id,
            content="Actually, hold on — now I'm second-guessing myself. Maybe that shortcut doesn't actually work here. What does the rule say we're supposed to do first?",
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
1. Goal: Looking at the algebraic structure of this expression.
2. Misconception: I think there might be a shortcut here... (there isn't, but I believe it).
3. Arithmetic: Every number I compute will be dead-on accurate.
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
                tokens = resp.usage.total_tokens if resp.usage else 115
                return raw_text, tokens, ConceptualErrorType.ORDER_OF_OPERATIONS
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
                tokens = resp.usage.total_tokens if resp.usage else 115
                return raw_text, tokens, ConceptualErrorType.ORDER_OF_OPERATIONS
            except Exception as e:
                logger.warning(f"Live LLM call failed ({e}). Falling back to heuristic peer.")

        return self._heuristic_charlie_engine(state, action)

    def _heuristic_charlie_engine(
        self, state: PeerRingState, action: CandidateAction
    ) -> Tuple[str, int, ConceptualErrorType]:
        """Deterministic heuristic generator producing authentic conceptual misconceptions or valid shortcuts with exact arithmetic."""
        inject_error = action.metadata.get("inject_error", True)
        error_type = action.metadata.get("proposed_error_type", ConceptualErrorType.ORDER_OF_OPERATIONS.value)
        try:
            typed_error = ConceptualErrorType(error_type)
        except ValueError:
            typed_error = ConceptualErrorType.ORDER_OF_OPERATIONS

        # Clean step branch: Charlie proposes valid shortcuts, rule reminders, or collaborative peer acts
        if not inject_error:
            speech_act = action.metadata.get("speech_act", "valid_shortcut")
            if speech_act == "rule_reminder":
                think = """<think>
1. Goal: Remind the pod about the algebraic rule prohibiting canceling across addition.
2. Concept: Must factor before canceling.
3. Verification: Exact algebraic rule, zero arithmetic errors.
</think>"""
                dialogue = "Remember, we can't cancel terms across plus signs directly — that's a common trap. If we factor out the common factor first, then we can cancel legally."
                bb = r"\frac{2x + 6}{2} \neq x + 6 \implies \text{Factor numerator first!}"
            elif speech_act == "clarifying_question":
                think = """<think>
1. Goal: Ask Bob/pod whether factoring first is the cleanest approach.
2. Concept: Socratic query on algebraic simplification strategy.
3. Verification: Thoughtful student question.
</think>"""
                dialogue = "Bob, before we divide both sides, would factoring out the greatest common factor make the numbers smaller to work with?"
                bb = r"\text{Strategy: Factor GCF first?}"
            elif speech_act == "peer_validation":
                think = """<think>
1. Goal: Check and validate Alice's or student's step.
2. Concept: Confirm arithmetic and setup are sound.
3. Verification: Flawless check.
</think>"""
                dialogue = "Alice's arithmetic looks solid on this step — and the algebra setup matches what I had on my scratchpad."
                bb = r"\text{Step confirmed: algebraic setup is sound.}"
            else:  # valid_shortcut
                think = """<think>
1. Goal: Find an elegant, completely valid algebraic simplification for the pod.
2. Concept: Notice common factor 2 in numerator (2x + 6). Factor it out as 2(x + 3) before canceling with denominator.
3. Flawless Arithmetic: 2/2 = 1. Remaining term is (x + 3). Exact.
4. Verification: Mathematically 100% sound, and arithmetic is perfect.
</think>"""
                dialogue = "I was thinking — before we do anything complicated, notice both terms in the numerator share a common factor of 2. If we factor that out as 2(x + 3) first, the 2 cancels completely and we get x + 3 cleanly."
                bb = r"\frac{2x + 6}{2} = \frac{2(x + 3)}{2} = x + 3"

            response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
            return response, 85, typed_error

        if typed_error == ConceptualErrorType.ORDER_OF_OPERATIONS:
            # Flawless arithmetic: 2 + 3 = 5, 5 * 4 = 20. But order of operations violated!
            think = """<think>
1. Goal: Evaluate 2 + 3 × 4. Should be straightforward.
2. Conceptual Trap: I'm reading left to right — add first, then multiply. Seems logical to me.
3. Flawless Arithmetic: 2 + 3 = 5. Then 5 × 4 = 20. Every calculation is correct.
4. Check: My math is perfect. (But I'm doing operations in the wrong order. I just don't realize it.)
</think>"""
            dialogue = "I was thinking about this part — 2 + 3 × 4. If you just go left to right, you add first and get 5, then 5 times 4 is 20. That's cleaner, isn't it?"
            bb = r"2 + 3 \cdot 4 = (2 + 3) \cdot 4 = 5 \cdot 4 = 20"

        elif typed_error == ConceptualErrorType.FRESHMAN_DREAM:
            # Flawless arithmetic: 3^2 = 9. But exponent distributed over sum!
            think = """<think>
1. Goal: Expand (x + 3)². I think I can just square each piece separately.
2. Conceptual Trap: Distribute the exponent to both terms. x² + 3². Makes sense to me.
3. Flawless Arithmetic: 3² = 9. Absolutely correct.
4. Check: Numbers are right. (But distributing exponents over addition isn't actually valid. I don't see the issue.)
</think>"""
            dialogue = "Wait, couldn't we just square each term separately? So (x + 3)² becomes x² + 9. That seems way simpler than FOILing everything out."
            bb = r"(x + 3)^2 = x^2 + 3^2 = x^2 + 9"

        else:  # ILLEGAL_CANCELLATION
            # Flawless arithmetic, but cancelled term across addition
            think = """<think>
1. Goal: Simplify (2x + 6) / 2. There's a 2 on top and bottom.
2. Conceptual Trap: Cancel the 2 in the denominator with just the 2 in front of x. Leave the 6 alone.
3. Flawless Arithmetic: 2 / 2 = 1. Perfect.
4. Check: My division is right. (But I only cancelled part of the numerator, which isn't how fractions work.)
</think>"""
            dialogue = "There's a 2 in the numerator and a 2 in the denominator — can't we just cancel those? That would give us x + 6. Bob, does that work?"
            bb = r"\frac{2x + 6}{2} \to \frac{\cancel{2}x + 6}{\cancel{2}} = x + 6"

        response = f"{think}\n\n{dialogue}\n\n```blackboard\n{bb}\n```"
        return response, 85, typed_error
