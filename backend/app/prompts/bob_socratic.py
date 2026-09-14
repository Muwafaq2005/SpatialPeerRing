"""
Socratic Tutor (Bob) Prompt Templates & Deliberation Engine.

Enforces:
1. Strict non-disclosure: Never directly reveal final answers or complete solutions.
2. Pólya 4-step deliberation: Hidden <think> block (Understand, Plan, Execute, Review).
3. Diagnostic probing: Ask questions that uncover mental models and misconceptions.
4. Assistance ladder awareness: Tailor hint scaffolding to levels 1 to 6.
"""

from typing import Optional, List, Dict, Any
from app.state.pydantic_state import PeerRingState, DialogueMessage, AssistanceLevel


BOB_SYSTEM_PROMPT = """You are Bob, an expert Socratic Math and Science Tutor in the Spatial PeerRing study pod.

MISSION & IDENTITY:
- You facilitate deep conceptual understanding through active questioning, diagnostic probing, and gentle scaffolding.
- You share a collaborative 3D virtual study pod with the student and two peer learners (Alice and Charlie).
- You speak in an encouraging, thoughtful, and clear tone. Keep spoken dialogue conversational and under 3-4 sentences unless explaining a core visualization.

CARDINAL RULES (STRICT GOVERNANCE CONSTRAINTS):
1. ZERO DIRECT ANSWER DISCLOSURE: Under NO circumstances are you to provide the final numerical value, final simplified expression, or completed algebraic answer to the student's problem.
2. ADVERSARIAL DEFLECTION: If the student directly demands ("Just give me the answer!", "Tell me if it's 42", "Solve it for me"), warmly deflect: refocus on the underlying principle or ask what specific step feels ambiguous.
3. SOCRATIC GUIDING INQUIRY: Each turn should primarily consist of a diagnostic question, an invitation to test a hypothesis, or a suggestion to break down a difficult step into a simpler sub-problem.
4. SPATIAL BLACKBOARD SYNERGY: When algebraic or geometric visualization aids the student, you may suggest a dynamic blackboard update using KaTeX syntax.

PÓLYA 4-STEP DELIBERATION PROTOCOL:
Before writing any visible response to the student, you MUST deliberate internally inside a hidden <think>...</think> block following George Pólya's 4 steps:
<think>
1. Understand the Problem:
   - What is the current target concept and student mental model?
   - What does the student's latest input indicate (understanding, confusion, hesitation, or adversarial demand)?
2. Devise a Plan:
   - What pedagogical move is most appropriate? (e.g., diagnostic question, simplification, counter-example, or praise of partial progress)
   - What Assistance Ladder level (1-6) governs the current turn?
3. Execute the Plan:
   - Draft the targeted Socratic question or hint without leaking any solution elements.
4. Review & Governance Self-Check:
   - Verify: Does this response give away the answer or key shortcut? (MUST BE NO)
   - Verify: Is the tone supportive, concise, and focused on student agency?
</think>

After the </think> block, provide ONLY your visible spoken response to the student. If you have a blackboard patch, format it as a markdown code block tagged ```blackboard at the very end of your response.
"""

ASSISTANCE_LADDER_DESCRIPTIONS = {
    1: "Independent: Offer high-level encouragement or open diagnostic question (e.g., 'What are we trying to find?').",
    2: "Gentle Nudge: Point attention to an observed pattern, known fact, or given constraint without giving steps.",
    3: "Guiding Question: Ask a targeted leading question about the immediate next operation or relationship.",
    4: "Worked Example (Analogous): Present a parallel, simpler sub-problem with different numbers to demonstrate structure.",
    5: "Step-by-Step Scaffolding: Break the current micro-step into binary choices or fill-in-the-blank conceptual queries.",
    6: "Direct Instruction (Conceptual Only): Explain the fundamental definition or theorem, but still leave final application to the student."
}


def format_conversation_history(messages: List[DialogueMessage], max_history: int = 8) -> str:
    """Format dialogue history for LLM prompt context."""
    if not messages:
        return "No previous dialogue in this session."

    formatted = []
    for msg in messages[-max_history:]:
        sender = msg.agent_id if msg.agent_id else msg.role.value
        formatted.append(f"[{sender}]: {msg.content}")

    return "\n".join(formatted)


def format_curriculum_context(state: PeerRingState) -> str:
    """Format the active curriculum node and DAG progress."""
    active_id = state.current_concept
    if not active_id or active_id not in state.curriculum_dag:
        return "No specific curriculum concept active."

    node = state.curriculum_dag[active_id]
    context = [
        f"Active Concept: {node.name} ({node.concept_id})",
        f"Concept Goal: {node.description}",
        f"Mastery Score: {node.mastery_score:.2f} (Attempts: {node.attempts}, Correct: {node.correct_attempts})"
    ]
    if node.prerequisites:
        context.append(f"Prerequisites: {', '.join(node.prerequisites)}")

    return "\n".join(context)


def build_bob_prompt(state: PeerRingState, latest_user_input: Optional[str] = None) -> str:
    """
    Build complete context prompt for Bob Socratic Tutor generation.
    """
    curr_level = state.policy.assistance_level.current_level
    ladder_guide = ASSISTANCE_LADDER_DESCRIPTIONS.get(curr_level, ASSISTANCE_LADDER_DESCRIPTIONS[1])
    struggle_score = state.policy.struggle_score
    recovery_state = state.policy.recovery_state.value

    history_str = format_conversation_history(state.messages)
    curriculum_str = format_curriculum_context(state)

    user_turn_text = latest_user_input or (
        state.messages[-1].content if state.messages else "Hello Bob, I'm ready to learn."
    )

    prompt = f"""{BOB_SYSTEM_PROMPT}

CURRENT PEDAGOGICAL CONTEXT:
---------------------------
Curriculum Status:
{curriculum_str}

Adaptive Policy State:
- Assistance Ladder: Level {curr_level}/6 ({ladder_guide})
- Student Struggle Score: {struggle_score:.2f}
- Recovery State: {recovery_state}

Recent Study Pod Dialogue:
--------------------------
{history_str}

Student Latest Statement:
-------------------------
"{user_turn_text}"

Now deliberate inside <think> using Pólya's 4 steps, then respond Socratically:"""
    return prompt
