"""
Curriculum Mastery DAG Manager.

Manages directed acyclic graph (DAG) representation of learning concepts,
evaluates concept unlocking prerequisites, tracks mastery scores using
exponentially weighted updates, and detects topological dependency chains.
"""

import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime
from collections import deque

from app.state.pydantic_state import PeerRingState, CurriculumNode

logger = logging.getLogger(__name__)


class CurriculumDAGManager:
    """
    Manages curriculum graph traversal, mastery calculations,
    and prerequisite validation.
    """

    def __init__(self, default_mastery_threshold: float = 0.7, ema_alpha: float = 0.35):
        self.default_mastery_threshold = default_mastery_threshold
        self.ema_alpha = ema_alpha

    def add_or_update_node(
        self,
        state: PeerRingState,
        concept_id: str,
        name: str,
        description: str = "",
        prerequisites: Optional[List[str]] = None,
        unlocks: Optional[List[str]] = None,
        mastery_score: float = 0.0,
    ) -> CurriculumNode:
        """
        Add or update a concept node in the curriculum DAG.
        """
        prereqs = prerequisites or []
        unlock_list = unlocks or []

        if concept_id in state.curriculum_dag:
            node = state.curriculum_dag[concept_id]
            node.name = name
            node.description = description
            node.prerequisites = prereqs
            node.unlocks = unlock_list
            if mastery_score > 0.0:
                node.mastery_score = max(0.0, min(1.0, mastery_score))
        else:
            node = CurriculumNode(
                concept_id=concept_id,
                name=name,
                description=description,
                prerequisites=prereqs,
                unlocks=unlock_list,
                mastery_score=max(0.0, min(1.0, mastery_score)),
            )
            state.curriculum_dag[concept_id] = node

        # Ensure symmetric unlock relationships in DAG
        for p_id in prereqs:
            if p_id in state.curriculum_dag:
                parent_node = state.curriculum_dag[p_id]
                if concept_id not in parent_node.unlocks:
                    parent_node.unlocks.append(concept_id)

        state.last_updated = datetime.utcnow()
        return node

    def detect_cycles(self, state: PeerRingState) -> bool:
        """
        Check if the curriculum DAG contains any circular dependency cycles.
        Returns True if a cycle exists (invalid DAG), False otherwise.
        """
        visited: Set[str] = set()
        rec_stack: Set[str] = set()

        def dfs(node_id: str) -> bool:
            visited.add(node_id)
            rec_stack.add(node_id)

            node = state.curriculum_dag.get(node_id)
            if node:
                for prereq_id in node.prerequisites:
                    if prereq_id not in visited:
                        if dfs(prereq_id):
                            return True
                    elif prereq_id in rec_stack:
                        return True

            rec_stack.remove(node_id)
            return False

        for c_id in state.curriculum_dag:
            if c_id not in visited:
                if dfs(c_id):
                    return True
        return False

    def is_concept_unlocked(
        self, state: PeerRingState, concept_id: str, threshold: Optional[float] = None
    ) -> bool:
        """
        A concept is unlocked if all its prerequisites have mastery_score >= threshold.
        If it has no prerequisites, it is unlocked by default.
        """
        thresh = threshold if threshold is not None else self.default_mastery_threshold
        node = state.curriculum_dag.get(concept_id)
        if not node:
            return False

        if not node.prerequisites:
            return True

        for prereq_id in node.prerequisites:
            prereq_node = state.curriculum_dag.get(prereq_id)
            if not prereq_node or prereq_node.mastery_score < thresh:
                return False

        return True

    def get_missing_prerequisites(
        self, state: PeerRingState, concept_id: str, threshold: Optional[float] = None
    ) -> List[str]:
        """
        Return direct prerequisites of concept_id whose mastery_score < threshold.
        """
        thresh = threshold if threshold is not None else self.default_mastery_threshold
        node = state.curriculum_dag.get(concept_id)
        if not node or not node.prerequisites:
            return []

        missing = []
        for prereq_id in node.prerequisites:
            prereq_node = state.curriculum_dag.get(prereq_id)
            if not prereq_node or prereq_node.mastery_score < thresh:
                missing.append(prereq_id)

        return missing

    def get_all_unmastered_prerequisites(
        self, state: PeerRingState, concept_id: str, threshold: Optional[float] = None
    ) -> List[str]:
        """
        Recursively collect all unmastered prerequisites in topological dependency order
        (deepest foundational roots first).
        """
        thresh = threshold if threshold is not None else self.default_mastery_threshold
        visited: Set[str] = set()
        unmastered_order: List[str] = []

        def traverse(cid: str):
            node = state.curriculum_dag.get(cid)
            if not node:
                return
            for pid in node.prerequisites:
                if pid not in visited:
                    visited.add(pid)
                    traverse(pid)
                    p_node = state.curriculum_dag.get(pid)
                    if p_node and p_node.mastery_score < thresh:
                        if pid not in unmastered_order:
                            unmastered_order.append(pid)

        traverse(concept_id)
        return unmastered_order

    def get_unlocked_concepts(
        self, state: PeerRingState, threshold: Optional[float] = None
    ) -> List[str]:
        """
        Return all concept IDs that are unlocked and not yet fully mastered.
        """
        thresh = threshold if threshold is not None else self.default_mastery_threshold
        unlocked = []
        for cid, node in state.curriculum_dag.items():
            if self.is_concept_unlocked(state, cid, thresh):
                if node.mastery_score < thresh:
                    unlocked.append(cid)
        return unlocked

    def update_mastery(
        self,
        state: PeerRingState,
        concept_id: str,
        success: bool,
        alpha: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Update the mastery score for a concept using an Exponential Moving Average (EMA)
        that incorporates historical performance while remaining sensitive to recent demonstrations.
        """
        node = state.curriculum_dag.get(concept_id)
        if not node:
            logger.warning(f"Concept '{concept_id}' not found in curriculum DAG")
            return {
                "concept_id": concept_id,
                "mastery_score": 0.0,
                "success": success,
                "prism_event": "CURRICULUM_MASTERY_UPDATE_FAILED",
            }

        prev_score = node.mastery_score
        node.attempts += 1
        if success:
            node.correct_attempts += 1

        rate = self.ema_alpha if alpha is None else alpha
        target = 1.0 if success else 0.0

        if node.attempts == 1:
            # Initial attempt anchors directly
            new_score = target
        else:
            # EMA formula: S_t = (1 - alpha) * S_{t-1} + alpha * target
            new_score = (1.0 - rate) * prev_score + rate * target

        # Bounded between 0.0 and 1.0
        node.mastery_score = max(0.0, min(1.0, round(new_score, 4)))
        node.last_practiced = datetime.utcnow()
        state.last_updated = datetime.utcnow()

        threshold = self.default_mastery_threshold
        is_mastered = node.mastery_score >= threshold
        became_mastered = prev_score < threshold <= node.mastery_score

        telemetry = {
            "concept_id": concept_id,
            "previous_score": prev_score,
            "new_score": node.mastery_score,
            "delta": round(node.mastery_score - prev_score, 4),
            "attempts": node.attempts,
            "correct_attempts": node.correct_attempts,
            "success": success,
            "is_mastered": is_mastered,
            "became_mastered": became_mastered,
            "unlocked_next": node.unlocks if became_mastered else [],
            "prism_event": "CURRICULUM_MASTERY_UPDATED",
        }

        logger.info(
            f"Mastery updated for '{concept_id}': {prev_score:.3f} -> {node.mastery_score:.3f} (success={success})"
        )
        return telemetry
