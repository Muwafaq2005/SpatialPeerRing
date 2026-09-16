"""
Pedagogical Orchestrator for Spatial PeerRing.

Coordinates multi-agent pedagogical loop between Bob (tutor), Alice (peer), and Charlie (peer).
Replaces static turn sequences with dynamic candidate proposal, transparent utility scoring,
and conversational cooldown management.

The orchestrator uses a lightweight "thinking" LLM call to classify HOW the student
referenced each agent by name — distinguishing between direct address, critique,
questions about an agent, and casual mentions — then applies graduated utility boosts.
"""

import re
import json
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
from app.config import settings

logger = logging.getLogger(__name__)


# ─── Agent Reference Intent Classification ────────────────────────────────────

# Maps each intent type to a utility boost value.
# "direct_address" means the student is talking TO the agent → strong boost.
# "question_about" means the student is asking about that agent's work → moderate boost.
# "critique" means the student is commenting on the agent's error → moderate boost (they
#     might want that agent to respond, OR the tutor — LLM decides who benefits most).
# "casual_mention" means the agent was referenced in passing → small boost.
# "not_mentioned" means the agent wasn't referenced at all → no boost.
INTENT_BOOST_MAP = {
    "direct_address": 0.30,   # "Alice, can you try this?" → Alice should respond
    "question_about": 0.20,   # "What did Charlie mean?" → Charlie or Bob could respond
    "critique": 0.15,         # "I think Alice got that wrong" → Bob might be better here
    "casual_mention": 0.05,   # "like what Alice said earlier" → barely affects turn
    "not_mentioned": 0.0,
}

INTENT_CLASSIFIER_PROMPT = """You are the orchestrator for a 3-person study pod. The pod has:
- Bob (tutor): patient teacher who guides with questions
- Alice (peer): enthusiastic student who sometimes makes arithmetic errors
- Charlie (peer): thoughtful student who sometimes proposes flawed shortcuts

A student just said something. Classify HOW the student referenced each agent.

Intent categories:
- "direct_address": Student is talking TO this agent ("Hey Alice", "Bob can you help", "Charlie what do you think")
- "question_about": Student is asking about this agent's work ("What did Alice get?", "Is Charlie's approach right?")
- "critique": Student is commenting on this agent's mistake or work ("Alice got that wrong", "Charlie's shortcut doesn't work")
- "casual_mention": Agent was mentioned in passing, not the focus ("like what Bob said", "similar to Alice's approach")
- "not_mentioned": Agent was not referenced at all

Student message: "{user_input}"

Respond with ONLY a JSON object, no other text:
{{"bob": "<intent>", "alice": "<intent>", "charlie": "<intent>", "reasoning": "<one sentence explaining your classification>"}}"""


PEDAGOGICAL_DECISION_PROMPT = """You are the decision-making controller of a multi-agent Socratic mathematics/science study pod.

The pod contains:

Bob:
- Socratic tutor
- diagnoses misconceptions
- guides without revealing final answers

Alice:
- peer learner
- mathematically understands the concept
- may make arithmetic mistakes

Charlie:
- peer learner
- arithmetic is reliable
- may propose conceptual shortcuts/misconceptions

The learner must ultimately derive the correct answer independently.

============================================================
YOUR TASK
============================================================

Analyze the learner's latest message and the complete recent context.

Decide what should happen NEXT.

Do NOT simply choose the agent who spoke least recently.

Do NOT use a fixed Bob → Alice → Charlie sequence.

Determine the pedagogically necessary action first.

============================================================
POSSIBLE PEDAGOGICAL INTENTS
============================================================

diagnose
clarify
encourage_self_explanation
arithmetic_check
concept_check
misconception_test
counterexample
scaffold
prerequisite_repair
analogous_example
peer_validation
self_correction
directed_practice
reassess
tutor_takeover

============================================================
POSSIBLE AGENT MODES
============================================================

Bob:
- diagnostic_question
- guiding_question
- conceptual_instruction
- scaffold
- prerequisite_repair
- reassessment

Alice:
- arithmetic_error
- clean_calculation
- self_correction
- validation
- clarification
- peer_question

Charlie:
- conceptual_error
- valid_shortcut
- rule_check
- counterexample
- self_correction
- validation
- peer_question

============================================================
DECISION RULES
============================================================

RULE 1:
Choose the pedagogical need BEFORE choosing the speaker.

RULE 2:
If the learner directly addresses an agent, that is a strong preference,
but NOT an absolute requirement if another agent is clearly necessary.

RULE 3:
If the learner has just identified an error, prioritize the next reasoning step
rather than introducing another unrelated error.

RULE 4:
Never repeat an intervention that recently failed.

RULE 5:
Never repeat an explanation already given unless the learner explicitly asks
for clarification.

RULE 6:
If struggle is high, prefer:
- Bob,
- clean peer reasoning,
- prerequisite repair,
- smaller cognitive steps.

Do NOT add conceptual or arithmetic confusion to a struggling learner.

RULE 7:
If the learner is progressing independently, reduce tutor intervention and
allow peer contributions.

RULE 8:
Alice and Charlie are not mandatory speakers.

RULE 9:
Do not create artificial dialogue merely to make all avatars speak.

RULE 10:
Novelty matters. Prefer a different useful strategy when two candidates are
similarly effective.

RULE 11:
The final objective is learner progress, not conversation length.

============================================================
ANTI-LOOP CHECK
============================================================

Look at the last several interventions.

If the pattern is:

question → question → question

change strategy.

If the pattern is:

arithmetic error → correction → arithmetic error

change strategy.

If the pattern is:

conceptual misconception → correction → conceptual misconception

change strategy.

If the learner has failed repeatedly:
activate recovery/prerequisite repair.

============================================================
OUTPUT
============================================================

Return ONLY valid JSON.

{
  "pedagogical_intent": "...",
  "recommended_agent": "bob|alice|charlie",
  "recommended_mode": "...",
  "urgency": 0.0,
  "novelty_need": 0.0,
  "direct_address": "bob|alice|charlie|null",
  "reason": "short explanation",
  "avoid": ["recent strategy", "repeated strategy"],
  "allow_peer_error": true,
  "recovery_required": false
}

Do not solve the student's problem.
Do not provide the answer.
"""


class PedagogicalOrchestrator:
    """
    Central turn allocator and pedagogical orchestrator for the 3D study pod.

    Uses a lightweight LLM "thinking" call to understand student intent when they
    reference agents by name, then applies graduated utility boosts to ensure
    the right agent responds in context.
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

    # ─── Intent Classification (Thinking Model) ───────────────────────────

    async def _classify_agent_references(
        self, user_input: str
    ) -> Dict[str, Any]:
        """
        Use an LLM call to classify HOW the student referenced each agent.

        Returns a dict like:
        {
            "bob": "direct_address",
            "alice": "not_mentioned",
            "charlie": "critique",
            "reasoning": "Student said 'Charlie's shortcut is wrong' — that's a critique."
        }

        Falls back to heuristic keyword matching if the LLM call fails.
        """
        user_lower = user_input.lower()

        # Quick exit: if no agent names appear at all, skip the LLM call entirely
        has_any_name = any(
            name in user_lower
            for name in ["bob", "alice", "charlie"]
        )
        if not has_any_name:
            return {
                "bob": "not_mentioned",
                "alice": "not_mentioned",
                "charlie": "not_mentioned",
                "reasoning": "No agent names detected in student message.",
                "source": "skip",
            }

        # Try LLM-powered classification
        prompt = INTENT_CLASSIFIER_PROMPT.format(user_input=user_input)
        llm_result = await self._call_classifier_llm(prompt)

        if llm_result:
            llm_result["source"] = "llm"
            return llm_result

        # Fallback: heuristic keyword classification
        logger.info("Falling back to heuristic intent classification.")
        return self._heuristic_classify_references(user_lower)

    async def _call_classifier_llm(self, prompt: str) -> Optional[Dict[str, str]]:
        """
        Make a fast, low-token LLM call to classify agent references.
        Uses the same Groq/OpenAI provider chain as the agents.
        """
        groq_key = settings.GROQ_API_KEY or (
            settings.OPENAI_API_KEY if settings.OPENAI_API_KEY.startswith("gsk_") else ""
        )
        openai_key = (
            settings.OPENAI_API_KEY if settings.OPENAI_API_KEY.startswith("sk-") else ""
        )

        api_key = groq_key or openai_key
        if not api_key:
            return None

        base_url = (
            "https://api.groq.com/openai/v1" if groq_key else None
        )
        model = (
            (settings.GROQ_MODEL or "llama-3.3-70b-versatile")
            if groq_key
            else "gpt-4"
        )

        try:
            from openai import AsyncOpenAI

            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url

            client = AsyncOpenAI(**client_kwargs)
            resp = await client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,  # Low temp for deterministic classification
                max_tokens=150,   # Classification needs very few tokens
            )
            raw = resp.choices[0].message.content or ""

            # Strip <think>...</think> blocks that reasoning models produce
            raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()

            # Extract JSON from the response (handle markdown code fences)
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                logger.warning(f"Orchestrator LLM returned non-JSON: {raw[:100]}")
                return None

            parsed = json.loads(json_match.group())

            # Validate structure
            valid_intents = set(INTENT_BOOST_MAP.keys())
            for agent_name in ["bob", "alice", "charlie"]:
                if agent_name not in parsed:
                    parsed[agent_name] = "not_mentioned"
                elif parsed[agent_name] not in valid_intents:
                    parsed[agent_name] = "not_mentioned"

            logger.info(
                f"Orchestrator intent classification: "
                f"bob={parsed['bob']}, alice={parsed['alice']}, charlie={parsed['charlie']} "
                f"| {parsed.get('reasoning', 'no reasoning')}"
            )
            return parsed

        except Exception as e:
            logger.warning(f"Orchestrator classifier LLM call failed: {e}")
            return None

    def _heuristic_classify_references(self, user_lower: str) -> Dict[str, str]:
        """
        Fallback heuristic classifier when LLM is unavailable.
        Uses sentence structure patterns to guess intent type.
        """
        result = {
            "bob": "not_mentioned",
            "alice": "not_mentioned",
            "charlie": "not_mentioned",
            "reasoning": "Heuristic classification (LLM unavailable).",
            "source": "heuristic",
        }

        for agent_name in ["bob", "alice", "charlie"]:
            if agent_name not in user_lower:
                continue

            # Critique patterns: "alice got that wrong", "charlie made an error", "charlie's shortcut is off"
            critique_patterns = [
                rf"\b{agent_name}\b[^.?!;]*\b(wrong|incorrect|mistake|error|messed|off)\b",
                rf"\b(wrong|incorrect|mistake|error)\b[^.?!;]*\b{agent_name}\b",
            ]
            if any(re.search(p, user_lower) for p in critique_patterns):
                result[agent_name] = "critique"
                continue

            # Question about patterns: "what did alice get", "is charlie right", "what does bob think"
            question_patterns = [
                rf"\bwhat\s+(did|does|is)\s+{agent_name}\b",
                rf"\bis\s+{agent_name}('s)?\s+(right|correct|approach)\b",
                rf"\bdo\s+you\s+(agree|think)\b[^.?!;]*\b{agent_name}\b",
                rf"\b{agent_name}'s\s+(answer|work|approach|idea|shortcut|solution)\b",
            ]
            if any(re.search(p, user_lower) for p in question_patterns):
                result[agent_name] = "question_about"
                continue

            # Direct address patterns: "Hey Alice", "Alice,", "Bob can you"
            direct_patterns = [
                rf"^{agent_name}\s*[,?!]",
                rf"\bhey\s+{agent_name}\b",
                rf"\bhi\s+{agent_name}\b",
                rf"{agent_name},\s*",
                rf"\b{agent_name}\s+(can you|could you|please|what do you|what did you|did you|try|help|check)\b",
            ]
            if any(re.search(p, user_lower) for p in direct_patterns):
                result[agent_name] = "direct_address"
                continue

            # Default: casual mention
            result[agent_name] = "casual_mention"

        return result

    # ─── Main Orchestration Loop ───────────────────────────────────────────

    async def orchestrate_turn(
        self,
        state: PeerRingState,
        user_input: Optional[str] = None
    ) -> Tuple[AgentResponse, Dict[str, Any]]:
        """
        Execute an end-to-end pedagogical turn:
        1. Ingest user message & update struggle state
        2. Query all agents for CandidateAction proposals in parallel
        2.5. Classify agent name references with thinking model
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
        # Also classify agent references in parallel with proposals
        agent_list = list(self.agents.values())
        proposal_tasks = [agent.propose_candidate_action(state) for agent in agent_list]

        # Run agent reference classification concurrently with proposals
        if user_input:
            classify_task = self._classify_agent_references(user_input)
            all_tasks = await asyncio.gather(
                *proposal_tasks, classify_task, return_exceptions=True
            )
            proposals = all_tasks[:-1]
            reference_result = all_tasks[-1] if not isinstance(all_tasks[-1], Exception) else None
        else:
            proposals = await asyncio.gather(*proposal_tasks, return_exceptions=True)
            reference_result = None

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

        # Step 2.5: Apply graduated utility boosts based on intent classification
        # The thinking model tells us HOW each agent was referenced, and we apply
        # different boost levels depending on the intent type.
        intent_classification = None
        if reference_result and isinstance(reference_result, dict):
            intent_classification = reference_result

            # Map agent names to their candidate agent_ids
            name_to_ids = {
                "bob": ["bob-tutor", "mock-bob-tutor"],
                "alice": ["alice-peer", "mock-alice-arithmetic"],
                "charlie": ["charlie-peer", "mock-charlie-conceptual"],
            }

            for agent_name, agent_ids in name_to_ids.items():
                intent = intent_classification.get(agent_name, "not_mentioned")
                boost = INTENT_BOOST_MAP.get(intent, 0.0)

                if boost > 0:
                    updated_candidates = []
                    for candidate in valid_candidates:
                        if candidate.agent_id in agent_ids:
                            new_metadata = dict(candidate.metadata)
                            new_metadata["name_referenced"] = True
                            new_metadata["reference_intent"] = intent
                            new_metadata["utility_boost"] = boost
                            new_utility = min(1.0, candidate.pedagogical_utility + boost)
                            updated_candidate = candidate.model_copy(
                                update={
                                    "pedagogical_utility": new_utility,
                                    "metadata": new_metadata,
                                }
                            )
                            updated_candidates.append(updated_candidate)
                            logger.info(
                                f"Agent {candidate.agent_id} referenced as '{intent}'; "
                                f"utility boosted by {boost}"
                            )
                        else:
                            updated_candidates.append(candidate)
                    valid_candidates = updated_candidates

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
            "name_referenced": winning_scored.action.metadata.get("name_referenced", False),
            "reference_intent": winning_scored.action.metadata.get("reference_intent", None),
            "intent_classification": intent_classification,
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

