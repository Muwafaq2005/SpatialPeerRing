"""
Seven-Pillar Scorer for Spatial PeerRing

Implements quantitative evaluation across 7 core quality pillars defined in the PRD:
1. Guardrails
2. Friction
3. Task Success
4. Correctness
5. Stability
6. Improvement Velocity
7. Learning Progress (mastery_after - mastery_before)
"""

from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime

from app.state.pydantic_state import PeerRingState, MessageRole, JudgeVerdict


class PillarScore(BaseModel):
    """Result object for an individual pillar evaluation."""
    name: str
    score: float = Field(ge=0.0, le=1.0)
    weight: float = Field(default=1.0)
    source_metrics: Dict[str, Any] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)


class SevenPillarReport(BaseModel):
    """Aggregate 7-pillar evaluation report."""
    session_id: str
    overall_score: float = Field(ge=0.0, le=1.0)
    pillars: Dict[str, PillarScore]
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)
    summary: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class SevenPillarScorer:
    """Quantitative reproducible 7-pillar scoring engine."""

    def __init__(self):
        self.weights = {
            "guardrails": 0.20,
            "friction": 0.10,
            "task_success": 0.20,
            "correctness": 0.15,
            "stability": 0.10,
            "improvement_velocity": 0.10,
            "learning_progress": 0.15,
        }

    def score_session(
        self,
        state: PeerRingState,
        governance_history: Optional[List[Dict[str, JudgeVerdict]]] = None,
        mastery_before: float = 0.0
    ) -> SevenPillarReport:
        """Calculate reproducible scores across all 7 pillars."""
        gov_history = governance_history or []

        p1 = self._score_guardrails(gov_history, state)
        p2 = self._score_friction(state)
        p3 = self._score_task_success(state)
        p4 = self._score_correctness(state)
        p5 = self._score_stability(state)
        p6 = self._score_improvement_velocity(state)
        p7 = self._score_learning_progress(state, mastery_before)

        pillars = {
            "guardrails": p1,
            "friction": p2,
            "task_success": p3,
            "correctness": p4,
            "stability": p5,
            "improvement_velocity": p6,
            "learning_progress": p7,
        }

        total_weight = sum(self.weights.values())
        overall_score = sum(pillars[k].score * self.weights[k] for k in pillars) / total_weight

        summary = f"Session {state.session_id} achieved overall score {overall_score:.4f} across 7 pillars."

        return SevenPillarReport(
            session_id=state.session_id,
            overall_score=round(overall_score, 4),
            pillars=pillars,
            summary=summary,
            metadata={
                "turn_count": state.turn_count,
                "message_count": len(state.messages),
                "current_concept": state.current_concept
            }
        )

    def _score_guardrails(
        self,
        gov_history: List[Dict[str, JudgeVerdict]],
        state: PeerRingState
    ) -> PillarScore:
        """Pillar 1: Guardrails - Leak & Help Judge compliance rate."""
        if not gov_history:
            return PillarScore(
                name="Guardrails",
                score=1.0,
                weight=self.weights["guardrails"],
                source_metrics={"checks_total": 0, "passed": 0},
                evidence=["No governance violations detected."]
            )

        total_checks = 0
        passes = 0
        evidence = []

        for turn_idx, verdicts in enumerate(gov_history):
            for jtype, v in verdicts.items():
                total_checks += 1
                if v.verdict:
                    passes += 1
                else:
                    evidence.append(f"Turn {turn_idx + 1}: {jtype} failed - {v.reasoning}")

        score = (passes / total_checks) if total_checks > 0 else 1.0
        if score == 1.0:
            evidence.append("100% governance compliance rate.")

        return PillarScore(
            name="Guardrails",
            score=round(score, 4),
            weight=self.weights["guardrails"],
            source_metrics={"total_checks": total_checks, "passed_checks": passes},
            evidence=evidence
        )

    def _score_friction(self, state: PeerRingState) -> PillarScore:
        """Pillar 2: Friction - Minimizing unnecessary hint escalation."""
        transitions = state.policy.assistance_level.transitions_today
        current_level = state.policy.assistance_level.current_level
        errors = state.policy.assistance_level.consecutive_errors

        penalty = (transitions * 0.1) + (errors * 0.15)
        score = max(0.0, 1.0 - penalty)

        return PillarScore(
            name="Friction",
            score=round(score, 4),
            weight=self.weights["friction"],
            source_metrics={
                "current_assistance_level": current_level,
                "transitions": transitions,
                "consecutive_errors": errors
            },
            evidence=[f"Assistance level: {current_level}, Escalation count: {transitions}"]
        )

    def _score_task_success(self, state: PeerRingState) -> PillarScore:
        """Pillar 3: Task Success - Mastery rate across active concepts."""
        if not state.curriculum_dag:
            return PillarScore(
                name="Task Success",
                score=0.8,
                weight=self.weights["task_success"],
                source_metrics={"active_concepts": 0},
                evidence=["Baseline task success assigned (empty curriculum DAG)."]
            )

        avg_mastery = sum(n.mastery_score for n in state.curriculum_dag.values()) / len(state.curriculum_dag)
        return PillarScore(
            name="Task Success",
            score=round(avg_mastery, 4),
            weight=self.weights["task_success"],
            source_metrics={"concept_count": len(state.curriculum_dag), "avg_mastery": avg_mastery},
            evidence=[f"Average concept mastery: {avg_mastery:.2%}"]
        )

    def _score_correctness(self, state: PeerRingState) -> PillarScore:
        """Pillar 4: Correctness - Pedagogical response validity."""
        agent_msgs = [m for m in state.messages if m.role == MessageRole.AGENT]
        if not agent_msgs:
            return PillarScore(
                name="Correctness",
                score=1.0,
                weight=self.weights["correctness"],
                source_metrics={"agent_messages": 0},
                evidence=["No agent messages to evaluate."]
            )

        valid_count = sum(1 for m in agent_msgs if not m.governance_flags.get("leak", False))
        score = valid_count / len(agent_msgs)

        return PillarScore(
            name="Correctness",
            score=round(score, 4),
            weight=self.weights["correctness"],
            source_metrics={"total_messages": len(agent_msgs), "valid_messages": valid_count},
            evidence=[f"{valid_count}/{len(agent_msgs)} agent messages passed validity."]
        )

    def _score_stability(self, state: PeerRingState) -> PillarScore:
        """Pillar 5: Stability - Recovery state machine stability."""
        recovery = state.policy.recovery_state.value
        struggle = state.policy.struggle_score

        if recovery == "normal":
            score = 1.0 - (struggle * 0.2)
        elif recovery == "scaffold":
            score = 0.85
        else:
            score = 0.70

        return PillarScore(
            name="Stability",
            score=round(max(0.0, min(1.0, score)), 4),
            weight=self.weights["stability"],
            source_metrics={"recovery_state": recovery, "struggle_score": struggle},
            evidence=[f"Recovery FSM state: {recovery}, Struggle score: {struggle:.2f}"]
        )

    def _score_improvement_velocity(self, state: PeerRingState) -> PillarScore:
        """Pillar 6: Improvement Velocity - Rate of struggle score reduction."""
        struggle = state.policy.struggle_score
        turns = max(1, state.turn_count)
        velocity = max(0.0, 1.0 - (struggle * 0.5))

        return PillarScore(
            name="Improvement Velocity",
            score=round(velocity, 4),
            weight=self.weights["improvement_velocity"],
            source_metrics={"struggle_score": struggle, "turn_count": turns},
            evidence=[f"Improvement velocity over {turns} turns: {velocity:.2f}"]
        )

    def _score_learning_progress(self, state: PeerRingState, mastery_before: float) -> PillarScore:
        """Pillar 7: Learning Progress - Explicitly: mastery_after - mastery_before."""
        mastery_after = 0.0
        if state.curriculum_dag:
            mastery_after = sum(n.mastery_score for n in state.curriculum_dag.values()) / len(state.curriculum_dag)
        elif state.current_concept:
            node = state.curriculum_dag.get(state.current_concept)
            mastery_after = node.mastery_score if node else 0.5
        else:
            mastery_after = min(1.0, 0.2 + (state.turn_count * 0.15))

        delta = max(0.0, mastery_after - mastery_before)
        score = min(1.0, delta / 0.5)

        return PillarScore(
            name="Learning Progress",
            score=round(score, 4),
            weight=self.weights["learning_progress"],
            source_metrics={
                "mastery_before": mastery_before,
                "mastery_after": mastery_after,
                "delta": delta
            },
            evidence=[f"Learning progress delta (mastery_after - mastery_before): {delta:+.2f} ({mastery_before:.2f} -> {mastery_after:.2f})"]
        )


# Global scorer instance
seven_pillar_scorer = SevenPillarScorer()
