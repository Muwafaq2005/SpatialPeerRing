"""
Bob Socratic Tutor Agent Implementation.

Extends BaseAgent to provide:
- Diagnostic Socratic inquiry with strict non-disclosure
- Pólya 4-step deliberation inside hidden <think> blocks
- Dynamic candidate action proposing with pedagogical utility calculation
- Blackboard patch extraction for KaTeX spatial visualization
- PRISM telemetry metadata integration
- Governance rejection recovery
"""

import re
import time
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
from app.prompts.bob_socratic import (
    build_bob_prompt,
    ASSISTANCE_LADDER_DESCRIPTIONS,
)
from app.config import settings

logger = logging.getLogger(__name__)


class BobAgent(BaseAgent):
    """
    Bob Socratic Tutor.
    Primary teacher agent responsible for diagnostic questioning and guiding the student.
    """

    def __init__(
        self,
        agent_id: str = "bob-tutor",
        config: Optional[Dict[str, Any]] = None
    ):
        super().__init__(
            agent_id=agent_id,
            agent_type=AgentType.BOB_TUTOR,
            config=config or {}
        )
        self.model_name = self.config.get("model", settings.DEFAULT_MODEL)
        self.temperature = self.config.get("temperature", 0.5)

    async def propose_candidate_action(
        self, state: PeerRingState
    ) -> Optional[CandidateAction]:
        """
        Propose a Socratic pedagogical candidate action.
        Evaluates current student struggle, recent dialogue, and policy level.
        """
        # Base utility for Socratic guidance
        base_utility = 0.65

        # Factor 1: Student struggle score (0.0 to 1.0)
        # As struggle increases, Bob's pedagogical duty to intervene increases
        struggle = state.policy.struggle_score
        utility = base_utility + (struggle * 0.25)

        # Factor 2: Assistance level ladder (1 to 6)
        curr_level = state.policy.assistance_level.current_level
        utility += (curr_level - 1) * 0.02

        # Factor 3: Did user ask a direct question or express confusion?
        last_user_message = self._get_latest_user_message(state)
        user_text = (last_user_message.content if last_user_message else "").lower()
        if any(w in user_text for w in ["help", "confused", "stuck", "why", "how", "what", "?"]):
            utility += 0.08

        # Factor 4: Cooldown penalty if Bob spoke very recently
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

        # Check explicit cooldown from policy state
        if self.agent_id in state.policy.agent_cooldowns:
            cooldown_time = state.policy.agent_cooldowns[self.agent_id]
            if (datetime.utcnow() - cooldown_time).total_seconds() < 15:
                cooldown_penalty = max(cooldown_penalty, 0.4)

        effective_utility = max(0.05, min(1.0, utility - cooldown_penalty))

        # Select appropriate action type
        if curr_level >= 4:
            action_type = "hint"
        elif struggle < 0.25 and curr_level <= 2:
            action_type = "challenge"
        else:
            action_type = "question"

        strategy_desc = ASSISTANCE_LADDER_DESCRIPTIONS.get(curr_level, "Socratic Questioning")

        return CandidateAction(
            agent_id=self.agent_id,
            action_type=action_type,
            pedagogical_utility=round(effective_utility, 3),
            content_preview=f"[Bob Socratic Inquiry | Level {curr_level}] Focusing on conceptual grounding...",
            cooldown_penalty=round(cooldown_penalty, 3),
            metadata={
                "strategy": strategy_desc,
                "assistance_level": curr_level,
                "struggle_score": round(struggle, 3),
                "polya_ready": True,
                "target_concept": state.current_concept or "general_inquiry"
            }
        )

    async def generate_response(
        self, state: PeerRingState, action: CandidateAction
    ) -> AgentResponse:
        """
        Generate response with Pólya 4-step deliberation and Socratic inquiry.
        """
        start_time = time.perf_counter()

        # Build context prompt
        prompt = build_bob_prompt(state)

        # Generate output: try real LLM if API key configured, otherwise use heuristic deliberation engine
        raw_text, tokens = await self._call_llm_or_heuristic(prompt, state, action)

        # Parse Pólya think block and clean visible dialogue
        think_block, clean_text = self._parse_polya_deliberation(raw_text)

        # Parse blackboard patch if present
        blackboard_patch, final_content = self._parse_blackboard_patch(clean_text)

        generation_time_ms = int((time.perf_counter() - start_time) * 1000)

        # PRISM telemetry & pedagogical metadata
        metadata = {
            "agent_id": self.agent_id,
            "agent_name": "Bob (Socratic Tutor)",
            "polya_deliberation_captured": bool(think_block),
            "socratic_strategy": action.metadata.get("strategy", "Socratic Questioning"),
            "assistance_level": state.policy.assistance_level.current_level,
            "struggle_score": state.policy.struggle_score,
            "has_blackboard_patch": bool(blackboard_patch),
            "prism_monitored": True
        }

        return AgentResponse(
            agent_id=self.agent_id,
            content=final_content.strip(),
            think_block=think_block,
            blackboard_patch=blackboard_patch,
            confidence=0.92,
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
        """
        Handle rejection by Governance tier (LeakJudge or HelpJudge).
        Regenerates an airtight high-level Socratic question.
        """
        logger.warning(
            f"Bob response rejected by governance: {rejection_reason}. Regenerating safe deflection."
        )

        safe_think = f"""<think>
1. Understand: My previous response got flagged for [{rejection_reason}]. Need to back way up.
2. Plan: Ask something purely reflective — no numbers, no formulas, just big picture.
3. Execute: Get the student to describe the problem in their own words.
4. Review: Nothing mathematical in my response. Clean.
</think>"""

        safe_content = (
            "Hey, let's zoom out for a second. Before we crunch any numbers, "
            "can you tell me in your own words — what's this problem actually asking us to figure out?"
        )

        return AgentResponse(
            agent_id=self.agent_id,
            content=safe_content,
            think_block=safe_think,
            blackboard_patch=None,
            confidence=0.95,
            tokens_used=30,
            generation_time_ms=10,
            metadata={
                "regenerated_after_rejection": True,
                "rejection_reason": rejection_reason,
                "governance_safe_deflection": True
            }
        )

    def _get_latest_user_message(self, state: PeerRingState) -> Optional[DialogueMessage]:
        """Get the most recent message sent by the user."""
        for msg in reversed(state.messages):
            if msg.role == MessageRole.USER:
                return msg
        return None

    def _parse_polya_deliberation(self, text: str) -> Tuple[Optional[str], str]:
        """
        Extract George Pólya's <think>...</think> block from the response.
        Returns (think_block, clean_dialogue).
        """
        pattern = r"<think>(.*?)</think>"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            think_content = match.group(0).strip()
            # Remove think block from visible content
            clean_text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()
            return think_content, clean_text

        # If no think block generated, construct a structured fallback Pólya block
        fallback_think = """<think>
1. Understand: Student is working through the current step. Let me figure out where they are.
2. Plan: Ask a question that makes them think about what they just did, not what comes next.
3. Execute: Keep it conversational — like I'd actually say this out loud.
4. Review: No answer leak, no formula giveaway. Clean.
</think>"""
        return fallback_think, text.strip()

    def _parse_blackboard_patch(self, text: str) -> Tuple[Optional[str], str]:
        """
        Extract blackboard patch from ```blackboard or ```katex code block.
        Returns (blackboard_patch, cleaned_text).
        """
        pattern = r"```(?:blackboard|katex)\s*(.*?)\s*```"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)

        if match:
            patch = match.group(1).strip()
            clean_text = re.sub(pattern, "", text, flags=re.DOTALL | re.IGNORECASE).strip()
            return patch, clean_text

        return None, text

    async def _call_llm_or_heuristic(
        self, prompt: str, state: PeerRingState, action: CandidateAction
    ) -> Tuple[str, int]:
        """
        Calls live LLM if API key is present, otherwise executes deterministic
        Socratic heuristic reasoning engine for offline/test reliability.
        """
        # Check Groq API key first, then fallback to OpenAI API key
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
                    temperature=self.temperature,
                    max_tokens=settings.MAX_TOKENS,
                )
                raw_text = resp.choices[0].message.content or ""
                tokens = resp.usage.total_tokens if resp.usage else 120
                return raw_text, tokens
            except Exception as e:
                logger.warning(f"Live Groq LLM call failed ({e}). Falling back to Socratic heuristic engine.")

        elif openai_key:
            try:
                from openai import AsyncOpenAI
                client = AsyncOpenAI(api_key=openai_key)
                resp = await client.chat.completions.create(
                    model=self.model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=settings.MAX_TOKENS,
                )
                raw_text = resp.choices[0].message.content or ""
                tokens = resp.usage.total_tokens if resp.usage else 120
                return raw_text, tokens
            except Exception as e:
                logger.warning(f"Live LLM call failed ({e}). Falling back to Socratic heuristic engine.")

        # Deterministic Socratic Heuristic Engine
        return self._heuristic_socratic_engine(state, action)

    def _heuristic_socratic_engine(
        self, state: PeerRingState, action: CandidateAction
    ) -> Tuple[str, int]:
        """
        Intelligent Socratic generation engine simulating George Pólya's 4-step deliberation.
        Produces non-disclosing Socratic responses keyed to the active Assistance Level.
        """
        level = state.policy.assistance_level.current_level
        struggle = state.policy.struggle_score
        active_concept = state.current_concept or "concept"

        last_user = self._get_latest_user_message(state)
        user_content = last_user.content if last_user else "I'm not sure how to solve this."

        # Check if the student mentioned any agent by name
        user_lower = user_content.lower()
        mentions_alice = any(w in user_lower for w in ["alice", "alice's", "alice,"])
        mentions_charlie = any(w in user_lower for w in ["charlie", "charlie's", "charlie,"])
        mentions_bob = any(w in user_lower for w in ["bob", "bob,", "hey bob"])

        # Deliberation steps
        polya_deliberation = f"""<think>
1. Understand the Problem:
   - Student said: "{user_content}"
   - They're working on: {active_concept} (struggle: {struggle:.2f})
   - Agent mentions: {'Alice referenced' if mentions_alice else 'no Alice ref'}, {'Charlie referenced' if mentions_charlie else 'no Charlie ref'}, {'talking to me directly' if mentions_bob else 'not addressing me by name'}
   - I need to figure out if they're stuck, making progress, or just checking in.
2. Devise a Plan:
   - Assistance Level {level}/6 — {'light touch, let them explore' if level <= 2 else 'they need more scaffolding' if level <= 4 else 'okay, time for more direct support'}.
   - {'Student mentioned Alice — I should acknowledge her work.' if mentions_alice else ''}
   - {'Student mentioned Charlie — I should engage with his idea.' if mentions_charlie else ''}
   - Zero answer disclosure. Always.
3. Execute the Plan:
   - Ask something that makes them THINK, not just calculate.
4. Review & Governance Self-Check:
   - Am I giving away the answer? No.
   - Does this sound like something I'd actually say in a real tutoring session? Yes.
</think>"""

        # Build natural dialogue based on context and Assistance Level
        if mentions_alice and level <= 3:
            visible_dialogue = (
                "Good eye looking at Alice's work! Before we move on, "
                "what specifically caught your attention about her approach? "
                "Was it the setup or the calculation part?"
            )
            bb_patch = None
        elif mentions_charlie and level <= 3:
            visible_dialogue = (
                "Yeah, Charlie's idea is interesting, right? It sounds like it should work. "
                "But here's a good habit — can you test it with a simple example to see if the shortcut actually holds up?"
            )
            bb_patch = None
        elif mentions_bob:
            visible_dialogue = (
                "Yeah, I'm right here! So tell me — what part of this is giving you the most trouble? "
                "Is it the setup, or is it once you start solving that things get fuzzy?"
            )
            bb_patch = None
        elif level == 1:
            visible_dialogue = (
                "Okay, I like where your head's at. Before we dive into any math, "
                "what's the very first thing this problem is asking us to find?"
            )
            bb_patch = None
        elif level == 2:
            visible_dialogue = (
                "Take another look at the numbers here. Do you notice anything that stays the same, "
                "or any pattern in how things change from one step to the next?"
            )
            bb_patch = None
        elif level == 3:
            visible_dialogue = (
                "Okay so we've got these terms grouped together. If we want to get our unknown by itself, "
                "what could we do to both sides to start simplifying things?"
            )
            bb_patch = r"\text{Focus: } a \cdot (b + c) = \text{?}"
        elif level == 4:
            visible_dialogue = (
                "Let me show you something similar but simpler. If we had 2(x + 3), we'd distribute the 2 to both "
                "terms inside — so 2x + 6. See that structure? Now, how would you apply that same idea to our problem?"
            )
            bb_patch = r"2 \cdot (x + 3) = 2x + 6"
        elif level == 5:
            visible_dialogue = (
                "Alright, let's take this one tiny step at a time. Just focus on the left side for now — "
                "if you expand what's in the parentheses, what terms do you get? Don't worry about the rest yet."
            )
            bb_patch = r"\text{Step 1: Expand } (\dots) \implies \text{?}"
        else:  # Level 6
            visible_dialogue = (
                "Okay, here's the key idea: when you distribute a number across a sum, you have to multiply it by "
                "every single term inside the brackets. Not just the first one — all of them. "
                "Try writing out just that multiplication step on the board."
            )
            bb_patch = r"k \cdot (A + B) = kA + kB"

        response_body = f"{polya_deliberation}\n\n{visible_dialogue}"
        if bb_patch:
            response_body += f"\n\n```blackboard\n{bb_patch}\n```"

        return response_body, 85
